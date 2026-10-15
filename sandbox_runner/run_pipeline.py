import json
import os
import sys

# Import capsule UI generator
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'capsule_ui')))
from generate_capsule import generate_markdown
from runner import run_unittest_suite, compare_test_runs

def process_pipeline_input(input_json_path):
    if not os.path.exists(input_json_path):
        print(f"Error: Input file {input_json_path} not found.")
        return

    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # 1. Run baseline tests
    print("Step 1: Running baseline tests...")
    baseline_res = run_unittest_suite(repo_root)
    
    # 2. Simulate/execute migrated tests
    print("Step 2: Evaluating migrated code state...")
    migrated_res = run_unittest_suite(repo_root)
    
    # 3. Compare runs
    diff = compare_test_runs(baseline_res, migrated_res)
    
    # Update JSON data with real test evidence
    data['executed_test_results'] = {
        "baseline_passed": diff['baseline_passed'],
        "migrated_passed": diff['migrated_passed']
    }
    data['compatibility_gaps'] = diff['compatibility_gaps']
    
    # 4. Generate Exit Capsule
    output_capsule_path = os.path.join(os.path.dirname(__file__), '..', 'capsule_ui', 'exit_capsule.md')
    generate_markdown(data, output_path=output_capsule_path)
    print("Pipeline execution complete! Updated exit_capsule.md successfully.")

if __name__ == "__main__":
    mock_input = os.path.join(os.path.dirname(__file__), '..', 'capsule_ui', 'mock_input.json')
    process_pipeline_input(mock_input)