import subprocess
import json
import os


def test_report_summary():
    # Run the report generator script to regenerate output
    result = subprocess.run(["python", "report_generator.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Report generator failed: {result.stderr}"

    # Ensure output file exists
    output_path = os.path.join(".output", "report.json")
    assert os.path.exists(output_path), "report.json not found after running generator"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Validate summary section
    assert "summary" in data, "Missing 'summary' section"
    summary = data["summary"]

    # Expected values
    expected_rooms = 1
    expected_doors = 1
    expected_wall_area = 20.0
    expected_total_cost = 420.0

    assert summary["rooms"] == expected_rooms, f"Unexpected rooms count: {summary['rooms']}"
    assert summary["doors"] == expected_doors, f"Unexpected doors count: {summary['doors']}"
    assert abs(summary["wall_area_m2"] - expected_wall_area) < 1e-6, f"Unexpected wall area: {summary['wall_area_m2']}"
    assert abs(summary["total_cost"] - expected_total_cost) < 1e-6, f"Unexpected total cost: {summary['total_cost']}"
