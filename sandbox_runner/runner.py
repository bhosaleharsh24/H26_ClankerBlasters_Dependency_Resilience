import subprocess
import json
import sys
import os

def run_tests_in_env(repo_dir):
    """
    Executes pytest in a specified directory and captures test output.
    """
    print(f"Running tests in: {repo_dir}")
    try:
        # Run pytest and capture output
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover"],
            cwd=repo_dir,
            capture_output=True,
            text=True
        )
        return {
            "passed": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {
            "passed": False,
            "stdout": "",
            "stderr": str(e)
        }

def compare_test_runs(baseline_results, migrated_results):
    """
    Compares before and after test results to identify compatibility gaps.
    """
    gaps = []
    if baseline_results["passed"] and not migrated_results["passed"]:
        gaps.append("Regression detected: Baseline tests passed, but migrated code failed tests.")
        if "AttributeError" in migrated_results["stderr"]:
            gaps.append("API Mismatch: Deprecated or renamed function/attribute called.")
            
    return {
        "baseline_passed": baseline_results["passed"],
        "migrated_passed": migrated_results["passed"],
        "compatibility_gaps": gaps
    }

if __name__ == "__main__":
    print("=== Sandbox Test Runner initialized ===")
    # Simulation for quick testing
    dummy_baseline = {"passed": True, "stdout": "2 tests passed", "stderr": ""}
    dummy_migrated = {"passed": True, "stdout": "2 tests passed", "stderr": ""}
    
    diff = compare_test_runs(dummy_baseline, dummy_migrated)
    print("Test Comparison Matrix:", json.dumps(diff, indent=2))