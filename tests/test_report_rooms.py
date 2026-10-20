import json

from tests.helpers import run_script


def test_report_rooms_breakdown(canonical_workspace):
    result = run_script("report_generator.py", canonical_workspace)
    assert result.returncode == 0, f"Report generator failed: {result.stderr}"

    output_path = canonical_workspace / ".output" / "report.json"
    assert output_path.exists(), "report.json not found after running generator"

    with open(output_path) as f:
        data = json.load(f)

    assert "summary" in data, "Missing 'summary' section"
    summary = data["summary"]
    assert "rooms_breakdown" in summary, "Missing 'rooms_breakdown' in summary"

    rooms_breakdown = summary["rooms_breakdown"]
    assert isinstance(rooms_breakdown, list), "rooms_breakdown should be a list"
    assert len(rooms_breakdown) == 1, f"Expected 1 room, found {len(rooms_breakdown)}"

    room = rooms_breakdown[0]
    assert room["room_id"] == 1, f"Unexpected room_id: {room['room_id']}"
    assert abs(room["area_m2"] - 20.0) < 1e-6, f"Unexpected room area: {room['area_m2']}"

    wall = room["materials"]["wall"]
    floor = room["materials"]["floor"]
    door = room["materials"]["door"]

    # Wall quantity is perimeter x height, not floor area
    assert wall["material"] == "Drywall 12mm", f"Unexpected wall material: {wall['material']}"
    assert abs(wall["area_m2"] - 54.0) < 1e-6, f"Unexpected wall area: {wall['area_m2']}"
    assert abs(wall["cost"] - 810.0) < 1e-6, f"Unexpected wall cost: {wall['cost']}"

    assert floor["material"] == "Ceramic Tile", f"Unexpected floor material: {floor['material']}"
    assert abs(floor["area_m2"] - 20.0) < 1e-6, f"Unexpected floor area: {floor['area_m2']}"
    assert abs(floor["cost"] - 500.0) < 1e-6, f"Unexpected floor cost: {floor['cost']}"

    assert door["material"] == "Oak Door", f"Unexpected door material: {door['material']}"
    assert door["count"] == 1, f"Unexpected door count: {door['count']}"
    assert abs(door["cost"] - 120.0) < 1e-6, f"Unexpected door cost: {door['cost']}"

    # 810 wall + 500 floor + 120 door
    assert abs(room["total_cost"] - 1430.0) < 1e-6, f"Unexpected room total cost: {room['total_cost']}"
