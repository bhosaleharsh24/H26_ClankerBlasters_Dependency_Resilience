from ai_engine.schemas import (
    CodePatch,
    MigrationItem,
    MigrationPlan,
    ModelMetadata,
    ProposedReplacement,
    ScanResult,
    SuggestedTest,
)

def get_mock_migration_plan(scan_result: ScanResult) -> MigrationPlan:
    """Generates a deterministic, schema-valid MigrationPlan for offline/fallback testing."""
    migrations = []

    for dep in scan_result.at_risk_dependencies:
        pkg = dep.package_name.lower()

        if pkg == "pycrypto":
            patches = [
                CodePatch(
                    usage_id=loc.usage_id,
                    file_path=loc.file_path,
                    original_snippet=loc.code_snippet,
                    migrated_snippet=loc.code_snippet,
                )
                for loc in dep.usage_locations
            ]
            migrations.append(
                MigrationItem(
                    original_package=dep.package_name,
                    proposed_replacement=ProposedReplacement(
                        package_name="pycryptodome",
                        recommended_version="3.20.0",
                        rationale=(
                            "Drop-in maintained fork of PyCrypto that patches known CVEs/GHSAs "
                            "while keeping Crypto.* namespace compatibility."
                        ),
                    ),
                    migration_steps=[
                        f"Remove {dep.package_name}=={dep.installed_version} from {dep.manifest_file}",
                        f"Add pycryptodome==3.20.0 to {dep.manifest_file}",
                    ],
                    code_patches=patches,
                    suggested_tests=[
                        SuggestedTest(
                            test_name="test_encrypt_token_roundtrip",
                            target_file="tests/test_crypto_migration.py",
                            test_code=(
                                "from app.crypto_utils import encrypt_token\n\n"
                                "def test_encrypt_token_deterministic():\n"
                                "    key = b'16byte_secretkey'\n"
                                "    payload = b'16byte_test_data'\n"
                                "    result = encrypt_token(payload, key)\n"
                                "    assert isinstance(result, bytes)"
                            ),
                        )
                    ],
                    open_concerns_and_limitations=[
                        "ECB mode (AES.MODE_ECB) is cryptographically weak; consider upgrading to AES.MODE_GCM."
                    ],
                )
            )

        elif pkg == "requests":
            patches = [
                CodePatch(
                    usage_id=loc.usage_id,
                    file_path=loc.file_path,
                    original_snippet=loc.code_snippet,
                    migrated_snippet=loc.code_snippet,
                )
                for loc in dep.usage_locations
            ]
            migrations.append(
                MigrationItem(
                    original_package=dep.package_name,
                    proposed_replacement=ProposedReplacement(
                        package_name="requests",
                        recommended_version="2.32.4",
                        rationale=(
                            "In-place upgrade to patched release addressing GHSA-9wx4-h78v-vm56 "
                            "and GHSA-9hjg-9r4m-mvj7 without breaking API compatibility."
                        ),
                    ),
                    migration_steps=[
                        f"Update {dep.package_name}=={dep.installed_version} to requests==2.32.4 in {dep.manifest_file}"
                    ],
                    code_patches=patches,
                    suggested_tests=[
                        SuggestedTest(
                            test_name="test_requests_session_initialization",
                            target_file="tests/test_requests_migration.py",
                            test_code=(
                                "import requests\n\n"
                                "def test_requests_session_initialization():\n"
                                "    session = requests.Session()\n"
                                "    assert session is not None\n"
                                "    session.close()"
                            ),
                        )
                    ],
                    open_concerns_and_limitations=[
                        "No direct AST usage locations were detected in the repository; verify transitive usages."
                    ],
                )
            )

        else:
            # Fallback for any other package: if not deprecated, bump version; if deprecated, suggest replacement
            replacement_pkg = dep.package_name if not dep.risk_indicators.is_deprecated else f"{dep.package_name}-ng"
            patches = [
                CodePatch(
                    usage_id=loc.usage_id,
                    file_path=loc.file_path,
                    original_snippet=loc.code_snippet,
                    migrated_snippet=loc.code_snippet,
                )
                for loc in dep.usage_locations
            ]
            migrations.append(
                MigrationItem(
                    original_package=dep.package_name,
                    proposed_replacement=ProposedReplacement(
                        package_name=replacement_pkg,
                        recommended_version="latest",
                        rationale="Mock fallback replacement generated in offline mode.",
                    ),
                    migration_steps=[
                        f"Replace {dep.package_name}=={dep.installed_version} with {replacement_pkg} in {dep.manifest_file}"
                    ],
                    code_patches=patches,
                    suggested_tests=[],
                    open_concerns_and_limitations=[
                        "Generated via Mock Fallback mode; verify replacement package manually."
                    ],
                )
            )

    return MigrationPlan(
        model_metadata=ModelMetadata(
            access_method="Mock Fallback Mode (Offline / Deterministic)"
        ),
        migrations=migrations,
    )
