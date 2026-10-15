import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

from ai_engine.gemma_client import generate_migration_plan
from ai_engine.schemas import ScanResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def run_pipeline(input_path: Path, output_path: Path, use_mock: bool = False) -> None:
    load_dotenv()

    if not input_path.exists():
        raise FileNotFoundError(f"Input scan file not found: {input_path}")

    # 1. Read & validate Member 2's scan result
    raw_scan = input_path.read_text(encoding="utf-8")
    scan_result = ScanResult.model_validate_json(raw_scan)
    logger.info(
        f"Validated 1_scan_result.json for repo '{scan_result.repository_name}' "
        f"({len(scan_result.at_risk_dependencies)} at-risk dependencies found)."
    )

    # 2. Generate migration plan via Gemma 4 (or mock fallback)
    migration_plan = generate_migration_plan(scan_result, use_mock=use_mock)

    # 3. Write validated 2_migration_plan.json for Member 3
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        migration_plan.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info(f"Successfully wrote migration plan to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Gemma 4 Dependency Migration Engine")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("shared_data/1_scan_result.json"),
        help="Path to Member 2's 1_scan_result.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("shared_data/2_migration_plan.json"),
        help="Path to output 2_migration_plan.json for Member 3",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force deterministic mock fallback without calling the API",
    )
    args = parser.parse_args()
    run_pipeline(args.input, args.output, use_mock=args.mock)
