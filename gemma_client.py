import concurrent.futures
import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from ai_engine.mock_fallback import get_mock_migration_plan
from ai_engine.prompts import SYSTEM_INSTRUCTION, build_migration_prompt
from ai_engine.schemas import (
    GemmaStructuredOutput,
    MigrationPlan,
    ModelMetadata,
    ScanResult,
)

logger = logging.getLogger(__name__)

MODEL_ID = "gemma-4-26b-a4b-it"
REQUEST_TIMEOUT_SEC = 60


def _load_api_key() -> str | None:
    """Loads .env from project root or ai_engine/ directory."""
    root_env = Path(__file__).resolve().parent.parent / ".env"
    local_env = Path(__file__).resolve().parent / ".env"
    if root_env.exists():
        load_dotenv(dotenv_path=root_env, override=True)
    if local_env.exists():
        load_dotenv(dotenv_path=local_env, override=True)

    for key_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMMA_API_KEY"):
        val = os.getenv(key_name)
        if val and val.strip():
            return val.strip().strip('"').strip("'")
    return None


def _clean_json_text(raw_text: str) -> str:
    """Strips Gemma 4 thought channels and markdown fences, returning only the JSON object."""
    text = raw_text.strip()

    # Strip Gemma 4 native thought channel tags if present
    if "<channel|>" in text:
        text = text.split("<channel|>")[-1].strip()
    if "</thought>" in text:
        text = text.split("</thought>")[-1].strip()

    # Strip markdown code fences
    if "```" in text:
        for block in text.split("```"):
            candidate = block.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                return candidate

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1:
        text = text[first_brace : last_brace + 1]
    return text.strip()


def _call_via_sdk(api_key: str, full_prompt: str) -> str:
    """Attempt 1: Call gemma-4-26b-a4b-it via official google-genai SDK on Gemini Developer API."""
    # Ensure environment variables don't accidentally force Vertex AI routing
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

    client = genai.Client(
        api_key=api_key,
        vertexai=False,
        http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_SEC * 1000),
    )

    config_kwargs = {
        "system_instruction": SYSTEM_INSTRUCTION,
        "temperature": 0.1,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    }

    # Set thinking_level="minimal" if supported by installed google-genai version
    try:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="minimal")
    except Exception:
        pass

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=full_prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    # Extract only non-thought text parts so internal reasoning braces aren't parsed as JSON
    output_chunks = []
    if getattr(response, "candidates", None):
        for candidate in response.candidates:
            if getattr(candidate, "content", None) and getattr(candidate.content, "parts", None):
                for part in candidate.content.parts:
                    if not getattr(part, "thought", False) and getattr(part, "text", None):
                        output_chunks.append(part.text)

    if output_chunks:
        return "\n".join(output_chunks)
    return response.text or ""


def _call_via_rest(api_key: str, full_prompt: str) -> str:
    """Attempt 2: Direct REST call to generativelanguage.googleapis.com for AQ. key compatibility."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent"
    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": full_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "thinkingConfig": {
                "thinkingLevel": "MINIMAL"
            },
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as http_err:
        err_body = http_err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {http_err.code}: {err_body}") from http_err

    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    non_thought_texts = [
        p.get("text", "") for p in parts if not p.get("thought", False) and p.get("text")
    ]
    return "\n".join(non_thought_texts)


def generate_migration_plan(
    scan_result: ScanResult,
    use_mock: bool = False,
    max_retries: int = 2,
) -> MigrationPlan:
    """
    Calls gemma-4-26b-a4b-it on the Gemini Developer API and validates output with Pydantic.
    Automatically falls back to deterministic mock mode only if offline or all attempts fail.
    """
    force_mock = use_mock or os.getenv("USE_MOCK_AI", "false").lower() == "true"
    api_key = _load_api_key()

    if force_mock or not api_key:
        reason = "USE_MOCK_AI=true / --mock" if force_mock else "GEMINI_API_KEY not set"
        logger.warning(f"Using Mock Fallback mode ({reason}).")
        return get_mock_migration_plan(scan_result)

    base_prompt = build_migration_prompt(scan_result)
    schema_json = json.dumps(GemmaStructuredOutput.model_json_schema(), indent=2)
    full_prompt = (
        f"{base_prompt}\n\n"
        "OUTPUT FORMAT REQUIREMENT:\n"
        "Respond ONLY with a valid JSON object matching this exact JSON Schema "
        "(top-level key MUST be 'migrations'):\n"
        f"{schema_json}"
    )

    for attempt in range(1, max_retries + 1):
        mode_label = "Google GenAI SDK" if attempt == 1 else "Direct Gemini REST API"
        caller_fn = _call_via_sdk if attempt == 1 else _call_via_rest

        logger.info(
            f"Calling {MODEL_ID} via {mode_label} "
            f"(Attempt {attempt}/{max_retries}, timeout={REQUEST_TIMEOUT_SEC}s)..."
        )
        start_time = time.time()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(caller_fn, api_key, full_prompt)
                raw_text = future.result(timeout=REQUEST_TIMEOUT_SEC)

            elapsed = round(time.time() - start_time, 2)
            logger.info(f"Received response from {MODEL_ID} in {elapsed}s. Validating JSON schema...")

            cleaned_json = _clean_json_text(raw_text)
            structured_data = GemmaStructuredOutput.model_validate_json(cleaned_json)

            logger.info("Live Gemma 4 output passed Pydantic & AST syntax validation!")
            return MigrationPlan(
                model_metadata=ModelMetadata(
                    model_name="Gemma 4",
                    model_version=MODEL_ID,
                    access_method="Google GenAI SDK / Hosted Gemini API",
                    terms_url="https://ai.google.dev/gemma/terms",
                ),
                migrations=structured_data.migrations,
            )

        except concurrent.futures.TimeoutError:
            logger.error(f"Attempt {attempt} ({mode_label}) timed out after {REQUEST_TIMEOUT_SEC}s.")
        except ValidationError as exc:
            logger.error(f"Attempt {attempt} ({mode_label}) failed Pydantic validation: {exc}")
        except Exception as exc:
            logger.error(f"Attempt {attempt} ({mode_label}) failed: {exc}")

        if attempt == max_retries:
            logger.warning(
                "All live Gemma 4 attempts exhausted. Falling back to Mock Migration Plan."
            )
            return get_mock_migration_plan(scan_result)

    return get_mock_migration_plan(scan_result)