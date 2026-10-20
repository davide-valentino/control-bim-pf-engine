import json

from tests.helpers import run_script


def test_report_generator(canonical_workspace):
    result = run_script("report_generator.py", canonical_workspace)
    assert result.returncode == 0, f"Report generator failed: {result.stderr}"

    output_path = canonical_workspace / ".output" / "report.json"
    assert output_path.exists(), "report.json not found after running generator"

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
