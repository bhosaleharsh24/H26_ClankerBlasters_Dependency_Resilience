import ast
from typing import List, Literal
from pydantic import BaseModel, Field, field_validator

# ==========================================
# INPUT CONTRACT: 1_scan_result.json (Member 2)
# ==========================================

class RiskIndicators(BaseModel):
    days_since_last_release: int
    is_deprecated: bool
    known_vulnerabilities_count: int
    cve_ids: List[str]
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_summary: str


class UsageLocation(BaseModel):
    usage_id: str
    file_path: str
    line_start: int
    line_end: int
    imported_statement: str
    called_symbols: List[str]
    code_snippet: str

    @field_validator("code_snippet", mode="before")
    @classmethod
    def clean_nbsp_in_scan_snippet(cls, v: str) -> str:
        return v.replace("\u00a0", " ") if isinstance(v, str) else v


class AtRiskDependency(BaseModel):
    package_name: str
    installed_version: str
    manifest_file: str
    risk_indicators: RiskIndicators
    usage_locations: List[UsageLocation]


class ScanResult(BaseModel):
    schema_version: str = "1.0"
    data_classification: Literal["OBSERVED_AND_VERIFIED"] = "OBSERVED_AND_VERIFIED"
    repository_name: str
    scanned_at: str
    at_risk_dependencies: List[AtRiskDependency]


# ==========================================
# OUTPUT CONTRACT: 2_migration_plan.json (Member 1)
# ==========================================

class ProposedReplacement(BaseModel):
    package_name: str = Field(
        description="The modern, actively maintained replacement PyPI package name (or same package name if upgrading version in-place)."
    )
    recommended_version: str = Field(
        description="Pinned semantic version recommended for the package (e.g., 3.20.0 or 2.32.4)."
    )
    rationale: str = Field(
        description="Concise technical justification referencing CVEs/GHSAs patched and API compatibility."
    )


class CodePatch(BaseModel):
    usage_id: str = Field(
        description="Must exactly match the usage_id from the input scan result."
    )
    file_path: str = Field(
        description="Must exactly match the file_path from the input scan result."
    )
    original_snippet: str = Field(
        description="Exact copy of the original code_snippet from the scan result."
    )
    migrated_snippet: str = Field(
        description="Updated Python code snippet compatible with the replacement package."
    )

    @field_validator("original_snippet", "migrated_snippet", mode="before")
    @classmethod
    def clean_nbsp_in_patch(cls, v: str) -> str:
        return v.replace("\u00a0", " ") if isinstance(v, str) else v

    @field_validator("migrated_snippet")
    @classmethod
    def validate_python_syntax(cls, v: str) -> str:
        try:
            ast.parse(v)
        except SyntaxError as e:
            raise ValueError(f"migrated_snippet contains invalid Python syntax: {e}")
        return v


class SuggestedTest(BaseModel):
    test_name: str = Field(
        description="Pytest function name starting with test_."
    )
    target_file: str = Field(
        description="Relative path for the generated pytest file, e.g., tests/test_crypto_migration.py."
    )
    test_code: str = Field(
        description="Complete, self-contained, executable pytest code verifying the migrated snippet."
    )

    @field_validator("test_code", mode="before")
    @classmethod
    def clean_nbsp_in_test(cls, v: str) -> str:
        return v.replace("\u00a0", " ") if isinstance(v, str) else v

    @field_validator("test_code")
    @classmethod
    def validate_test_syntax(cls, v: str) -> str:
        try:
            ast.parse(v)
        except SyntaxError as e:
            raise ValueError(f"test_code contains invalid Python syntax: {e}")
        return v


class MigrationItem(BaseModel):
    original_package: str = Field(
        description="Name of the at-risk package being replaced or upgraded."
    )
    proposed_replacement: ProposedReplacement
    migration_steps: List[str] = Field(
        description="Ordered, actionable steps to update manifest files and install dependencies."
    )
    code_patches: List[CodePatch]
    suggested_tests: List[SuggestedTest]
    open_concerns_and_limitations: List[str] = Field(
        description="Security caveats, algorithmic weaknesses (e.g., ECB mode), or edge cases requiring human review."
    )


class GemmaStructuredOutput(BaseModel):
    """Schema passed to Gemma 4 for structured JSON generation."""
    migrations: List[MigrationItem]


class ModelMetadata(BaseModel):
    model_name: str = "Gemma 4"
    model_version: str = "gemma-4-26b-a4b-it"
    access_method: str = "Google GenAI SDK / Hosted Gemini API"
    terms_url: str = "https://ai.google.dev/gemma/terms"


class MigrationPlan(BaseModel):
    """Final envelope written to shared_data/2_migration_plan.json."""
    schema_version: str = "1.0"
    data_classification: Literal["AI_GENERATED_UNVERIFIED"] = "AI_GENERATED_UNVERIFIED"
    model_metadata: ModelMetadata = Field(default_factory=ModelMetadata)
    migrations: List[MigrationItem]