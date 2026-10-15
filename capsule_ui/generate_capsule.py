import json
import os

def generate_markdown(data, output_path="exit_capsule.md"):
    dep = data.get("dependency_details", {})
    
    md = f"# 📦 Dependency Exit Capsule\n\n"
    md += f"**Target Dependency:** `{dep.get('name', 'N/A')}` v`{dep.get('version', 'N/A')}`  \n"
    md += f"**Proposed Replacement:** `{data.get('proposed_replacement', 'N/A')}`\n\n"
    md += "---\n\n"
    
    # 1. OBSERVED EVIDENCE (Facts)
    md += "## 🔍 Verified Evidence (Observed via Static Analysis & Execution)\n\n"
    
    md += "### 🛑 Risk Indicators\n"
    for risk in data.get("risk_indicators", []):
        md += f"- {risk}\n"
        
    md += "\n### 📍 Usage Locations\n"
    for loc in data.get("usage_locations", []):
        md += f"- `{loc.get('file')}` (Line {loc.get('line')})\n"
        
    md += "\n### 🧪 Test Execution Results\n"
    results = data.get("executed_test_results", {})
    baseline = "✅ PASSED" if results.get("baseline_passed") else "❌ FAILED"
    migrated = "✅ PASSED" if results.get("migrated_passed") else "❌ FAILED"
    md += f"- **Baseline Tests (Original Code):** {baseline}\n"
    md += f"- **Migrated Tests (With Replacement):** {migrated}\n"
    
    md += "\n### ⚠️ Compatibility Gaps Identified\n"
    gaps = data.get("compatibility_gaps", [])
    if gaps:
        for gap in gaps:
            md += f"- {gap}\n"
    else:
        md += "- No breaking compatibility gaps observed.\n"
        
    md += "\n---\n\n"
    
    # 2. AI RECOMMENDATIONS (Separated clearly as per hackathon requirements)
    md += "## 🤖 Gemma 4 Recommendations (Unverified AI Guidance)\n\n"
    
    md += "### 🛠️ Migration Steps\n"
    for i, step in enumerate(data.get("migration_steps", []), 1):
        md += f"{i}. {step}\n"
        
    md += "\n### ❓ Open Concerns & Limitations\n"
    concerns = data.get("open_concerns", [])
    if concerns:
        for concern in concerns:
            md += f"- {concern}\n"
    else:
        md += "- None logged.\n"
        
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
        
    print(f"Success! Dependency Exit Capsule generated at: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    if os.path.exists("mock_input.json"):
        with open("mock_input.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        generate_markdown(data)
    else:
        print("Error: mock_input.json not found!")