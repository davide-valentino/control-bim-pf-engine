import subprocess
import json
import os
import sys


def test_report_breakdown():
    # Run the report generator script to regenerate output
    result = subprocess.run([sys.executable, "report_generator.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Report generator failed: {result.stderr}"

    # Ensure output file exists
    output_path = os.path.join(".output", "report.json")
    assert os.path.exists(output_path), "report.json not found after running generator"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Validate materials_breakdown section
    assert "summary" in data, "Missing 'summary' section"
    summary = data["summary"]
    assert "materials_breakdown" in summary, "Missing 'materials_breakdown' in summary"

    breakdown = summary["materials_breakdown"]

    # Expected materials
    assert "Drywall 12mm" in breakdown, "Drywall 12mm missing from breakdown"
    assert "Oak Door" in breakdown, "Oak Door missing from breakdown"

    drywall = breakdown["Drywall 12mm"]
    oak_door = breakdown["Oak Door"]

    # Validate drywall entry
    assert drywall["type"] == "wall", f"Unexpected type for Drywall: {drywall['type']}"
    assert abs(drywall["area_m2"] - 20.0) < 1e-6, f"Unexpected drywall area: {drywall['area_m2']}"
    assert abs(drywall["cost"] - 300.0) < 1e-6, f"Unexpected drywall cost: {drywall['cost']}"

    # Validate oak door entry
    assert oak_door["type"] == "door", f"Unexpected type for Oak Door: {oak_door['type']}"
    assert oak_door["count"] == 1, f"Unexpected door count: {oak_door['count']}"
    assert abs(oak_door["cost"] - 120.0) < 1e-6, f"Unexpected door cost: {oak_door['cost']}"
