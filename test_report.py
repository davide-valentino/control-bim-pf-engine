import subprocess
import json
import os


def test_report_generator():
    # Run the report generator script to regenerate output
    result = subprocess.run(["python", "report_generator.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Report generator failed: {result.stderr}"

    # Ensure output file exists
    output_path = os.path.join(".output", "report.json")
    assert os.path.exists(output_path), "report.json not found after running generator"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Validate keys
    for key in ["raw_geometry", "semantic", "materials", "costs"]:
        assert key in data, f"Missing section: {key}"
        assert data[key] is not None, f"Section {key} is empty"

    # Validate nested content
    assert "walls" in data["raw_geometry"], "Raw geometry missing walls"
    assert "rooms" in data["semantic"], "Semantic missing rooms"
    assert "rooms" in data["materials"], "Materials missing rooms"
    assert "items" in data["costs"], "Costs missing items"
