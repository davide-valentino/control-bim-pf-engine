import json

from tests.helpers import run_script


def test_report_summary(canonical_workspace):
    result = run_script("report_generator.py", canonical_workspace)
    assert result.returncode == 0, f"Report generator failed: {result.stderr}"

    output_path = canonical_workspace / ".output" / "report.json"
    assert output_path.exists(), "report.json not found after running generator"

    with open(output_path) as f:
        data = json.load(f)

    assert "summary" in data, "Missing 'summary' section"
    summary = data["summary"]

    expected_rooms = 1
    expected_doors = 1
    expected_windows = 0
    expected_wall_area = 54.0  # 18 m perimeter * 3 m height
    expected_floor_area = 20.0
    expected_total_cost = 1430.0  # 810 wall + 500 floor + 120 door

    assert summary["rooms"] == expected_rooms, f"Unexpected rooms count: {summary['rooms']}"
    assert summary["doors"] == expected_doors, f"Unexpected doors count: {summary['doors']}"
    assert summary["windows"] == expected_windows, f"Unexpected windows count: {summary['windows']}"
    assert abs(summary["wall_area_m2"] - expected_wall_area) < 1e-6, f"Unexpected wall area: {summary['wall_area_m2']}"
    assert abs(summary["floor_area_m2"] - expected_floor_area) < 1e-6, f"Unexpected floor area: {summary['floor_area_m2']}"
    assert abs(summary["total_cost"] - expected_total_cost) < 1e-6, f"Unexpected total cost: {summary['total_cost']}"

    # Rate provenance is carried into the consolidated report
    assert summary["currency"] == "USD"
    assert summary["as_of"]
    assert "placeholder" in summary["rate_source"].lower()
