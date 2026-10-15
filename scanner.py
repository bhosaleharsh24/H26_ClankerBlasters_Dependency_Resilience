import ast
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
import requests

PACKAGE_IMPORT_MAP = {
    "pycrypto": ["Crypto"],
    "pycryptodome": ["Crypto"],
    "pillow": ["PIL"],
    "beautifulsoup4": ["bs4"],
    "scikit-learn": ["sklearn"],
    "pyyaml": ["yaml"],
}

def parse_requirements(req_file: Path) -> list[dict]:
    dependencies = []
    if not req_file.exists():
        print(f"[!] No requirements.txt found at {req_file}")
        return dependencies

    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            dependencies.append({"name": name.strip(), "version": version.strip()})
        else:
            dependencies.append({"name": line, "version": "latest"})
    return dependencies

def check_package_risk(pkg_name: str, version: str) -> dict:
    days_since_release = 0
    is_deprecated = False
    cve_ids = []

    try:
        pypi_url = f"https://pypi.org/pypi/{pkg_name}/json"
        resp = requests.get(pypi_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            releases = data.get("releases", {})
            latest_ver = data.get("info", {}).get("version", version)
            files = releases.get(version) or releases.get(latest_ver) or []
            if files and "upload_time_iso_8601" in files[0]:
                upload_str = files[0]["upload_time_iso_8601"].replace("Z", "+00:00")
                upload_dt = datetime.fromisoformat(upload_str)
                days_since_release = (datetime.now(timezone.utc) - upload_dt).days

            classifiers = data.get("info", {}).get("classifiers", [])
            if any("Inactive" in c or "Deprecated" in c for c in classifiers):
                is_deprecated = True
    except Exception as e:
        print(f"[!] Warning: Could not reach PyPI for {pkg_name}: {e}")

    try:
        osv_url = "https://api.osv.dev/v1/query"
        payload = {"package": {"name": pkg_name, "ecosystem": "PyPI"}}
        if version != "latest":
            payload["version"] = version
        resp = requests.post(osv_url, json=payload, timeout=5)
        if resp.status_code == 200:
            vulns = resp.json().get("vulns", [])
            for v in vulns:
                cve_ids.append(v.get("id"))
    except Exception as e:
        print(f"[!] Warning: Could not reach OSV.dev for {pkg_name}: {e}")

    is_risky = (days_since_release > 730) or is_deprecated or (len(cve_ids) > 0)

    if len(cve_ids) > 0 and days_since_release > 730:
        risk_level = "CRITICAL"
        summary = f"Unmaintained for {days_since_release} days with {len(cve_ids)} known security vulnerabilities."
    elif len(cve_ids) > 0:
        risk_level = "HIGH"
        summary = f"Contains {len(cve_ids)} known security vulnerabilities."
    elif days_since_release > 730 or is_deprecated:
        risk_level = "MEDIUM"
        summary = f"Stale/abandoned package ({days_since_release} days since last release)."
    else:
        risk_level = "LOW"
        summary = "Healthy package."

    return {
        "is_risky": is_risky,
        "risk_indicators": {
            "days_since_last_release": days_since_release,
            "is_deprecated": is_deprecated or (days_since_release > 1800),
            "known_vulnerabilities_count": len(cve_ids),
            "cve_ids": cve_ids[:5],
            "risk_level": risk_level,
            "risk_summary": summary,
        },
    }

def find_usages_in_repo(repo_path: Path, pkg_name: str) -> list[dict]:
    possible_module_names = PACKAGE_IMPORT_MAP.get(
        pkg_name.lower(), [pkg_name.lower().replace("-", "_")]
    )
    usages = []
    usage_counter = 1

    for py_file in repo_path.rglob("*.py"):
        if any(part.startswith(".") or part in ("venv", "__pycache__") for part in py_file.parts):
            continue

        source_text = py_file.read_text(encoding="utf-8")
        source_lines = source_text.splitlines()

        try:
            tree = ast.parse(source_text, filename=str(py_file))
        except SyntaxError:
            continue

        imported_aliases = set()
        import_statements = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod in possible_module_names:
                        local_name = alias.asname or root_mod
                        imported_aliases.add(local_name)
                        import_statements.append(source_lines[node.lineno - 1].strip())

            elif isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in possible_module_names:
                    for alias in node.names:
                        local_name = alias.asname or alias.name
                        imported_aliases.add(local_name)
                    import_statements.append(source_lines[node.lineno - 1].strip())

        if not imported_aliases:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                called_symbols = []
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute) and isinstance(child.func.value, ast.Name):
                            if child.func.value.id in imported_aliases:
                                called_symbols.append(f"{child.func.value.id}.{child.func.attr}")
                        elif isinstance(child.func, ast.Name) and child.func.id in imported_aliases:
                            called_symbols.append(child.func.id)

                if called_symbols:
                    start_line = node.lineno
                    end_line = getattr(node, "end_lineno", start_line + 5)
                    snippet_lines = import_statements + [""] + source_lines[start_line - 1 : end_line]

                    usages.append({
                        "usage_id": f"usage_{usage_counter:03d}",
                        "file_path": str(py_file.relative_to(repo_path)).replace("\\", "/"),
                        "line_start": start_line,
                        "line_end": end_line,
                        "imported_statement": import_statements[0] if import_statements else "",
                        "called_symbols": list(set(called_symbols)),
                        "code_snippet": "\n".join(snippet_lines),
                    })
                    usage_counter += 1

    return usages

def scan_repository(target_dir: str, output_file: str):
    repo_path = Path(target_dir).resolve()
    req_file = repo_path / "requirements.txt"

    print(f"[*] Scanning repository: {repo_path.name} ...")
    deps = parse_requirements(req_file)
    at_risk_list = []

    for dep in deps:
        name, version = dep["name"], dep["version"]
        print(f"    -> Checking {name}=={version} against PyPI and OSV.dev...")
        risk_data = check_package_risk(name, version)

        if risk_data["is_risky"]:
            print(f"       [!] RISK DETECTED ({risk_data['risk_indicators']['risk_level']}): Finding code usages...")
            usages = find_usages_in_repo(repo_path, name)
            at_risk_list.append({
                "package_name": name,
                "installed_version": version,
                "manifest_file": "requirements.txt",
                "risk_indicators": risk_data["risk_indicators"],
                "usage_locations": usages,
            })
        else:
            print(f"       [OK] {name} looks healthy.")

    final_report = {
        "schema_version": "1.0",
        "data_classification": "OBSERVED_AND_VERIFIED",
        "repository_name": repo_path.name,
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "at_risk_dependencies": at_risk_list,
    }

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    print(f"\n[+] Scan complete! Saved verified report to: {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Member 2: Dependency Risk & AST Scanner")
    parser.add_argument("--repo", default="demo_target_repo", help="Path to target repo")
    parser.add_argument("--output", default="shared_data/1_scan_result.json", help="Output JSON path")
    args = parser.parse_args()
    scan_repository(args.repo, args.output)