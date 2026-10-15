import subprocess
import json
import sys
import os

def run_unittest_suite(repo_dir):
    """
    Executes Python's built-in unittest framework on a target directory 
    and captures stdout, stderr, and pass/fail status.
    """
    print(f"Executing tests in directory: {repo_dir}")
    if not os.path.exists(repo_dir):
        return {
            "passed": False,
            "stdout": "",
            "stderr": f"Directory not found: {repo_dir}"
        }

    try:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", repo_dir],
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "passed": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "stdout": "",
            "stderr": "Test execution timed out after 30 seconds."
        }
    except Exception as e:
        return {
            "passed": False,
            "stdout": "",
            "stderr": str(e)
        }

def compare_test_runs(baseline_res, migrated_res):
    """
    Compares baseline vs migrated test results to identify compatibility gaps.
    """
    gaps = []
    
    if baseline_res["passed"] and not migrated_res["passed"]:
        gaps.append("Regression: Baseline tests passed, but tests failed after applying migration patch.")
    elif not baseline_res["passed"] and not migrated_res["passed"]:
        gaps.append("Pre-existing failure: Baseline repo tests were already failing prior to migration.")

    stderr_combined = migrated_res.get("stderr", "")
    if "ImportError" in stderr_combined or "ModuleNotFoundError" in stderr_combined:
        gaps.append("Missing Dependency: Proposed replacement package is not installed in the environment.")
    if "AttributeError" in stderr_combined:
        gaps.append("API Mismatch: Code calls a function or attribute that does not exist in the replacement package.")
    if "TypeError" in stderr_combined:
        gaps.append("Signature Mismatch: Function argument signature changed in replacement package.")

    return {
        "baseline_passed": baseline_res["passed"],
        "migrated_passed": migrated_res["passed"],
        "compatibility_gaps": gaps,
        "raw_logs": {
            "baseline_stderr": baseline_res.get("stderr", ""),
            "migrated_stderr": migrated_res.get("stderr", "")
        }
    }

if __name__ == "__main__":
    print("=== Sandbox Test Runner (Real Execution Engine) ===")
    
    target_repo = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    baseline_output = run_unittest_suite(target_repo)
    
    print("\n--- Baseline Run Output ---")
    print(f"Passed: {baseline_output['passed']}")
    print(f"Logs: {baseline_output['stderr'].strip() or 'No errors'}")