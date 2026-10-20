import json

from tests.helpers import run_script


def test_report_breakdown(canonical_workspace):
    result = run_script("report_generator.py", canonical_workspace)
    assert result.returncode == 0, f"Report generator failed: {result.stderr}"

    output_path = canonical_workspace / ".output" / "report.json"
    assert output_path.exists(), "report.json not found after running generator"

    with open(output_path) as f:
        data = json.load(f)

    assert "summary" in data, "Missing 'summary' section"
    summary = data["summary"]
    assert "materials_breakdown" in summary, "Missing 'materials_breakdown' in summary"

    breakdown = summary["materials_breakdown"]

    assert "Drywall 12mm" in breakdown, "Drywall 12mm missing from breakdown"
    assert "Ceramic Tile" in breakdown, "Ceramic Tile missing from breakdown"
    assert "Oak Door" in breakdown, "Oak Door missing from breakdown"

    drywall = breakdown["Drywall 12mm"]
    assert drywall["type"] == "wall", f"Unexpected type for Drywall: {drywall['type']}"
    assert abs(drywall["area_m2"] - 54.0) < 1e-6, f"Unexpected drywall area: {drywall['area_m2']}"
    assert abs(drywall["cost"] - 810.0) < 1e-6, f"Unexpected drywall cost: {drywall['cost']}"

    floor = breakdown["Ceramic Tile"]
    assert floor["type"] == "floor", f"Unexpected type for Ceramic Tile: {floor['type']}"
    assert abs(floor["area_m2"] - 20.0) < 1e-6, f"Unexpected floor area: {floor['area_m2']}"
    assert abs(floor["cost"] - 500.0) < 1e-6, f"Unexpected floor cost: {floor['cost']}"

    oak_door = breakdown["Oak Door"]
    assert oak_door["type"] == "door", f"Unexpected type for Oak Door: {oak_door['type']}"
    assert oak_door["count"] == 1, f"Unexpected door count: {oak_door['count']}"
    assert abs(oak_door["cost"] - 120.0) < 1e-6, f"Unexpected door cost: {oak_door['cost']}"
