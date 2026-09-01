import subprocess
import json
import os


def test_report_rooms_breakdown():
    # Run the report generator script to regenerate output
    result = subprocess.run(["python", "report_generator.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Report generator failed: {result.stderr}"

    # Ensure output file exists
    output_path = os.path.join(".output", "report.json")
    assert os.path.exists(output_path), "report.json not found after running generator"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Validate rooms_breakdown section
    assert "summary" in data, "Missing 'summary' section"
    summary = data["summary"]
    assert "rooms_breakdown" in summary, "Missing 'rooms_breakdown' in summary"

    rooms_breakdown = summary["rooms_breakdown"]
    assert isinstance(rooms_breakdown, list), "rooms_breakdown should be a list"
    assert len(rooms_breakdown) == 1, f"Expected 1 room, found {len(rooms_breakdown)}"

    room = rooms_breakdown[0]
    assert room["room_id"] == 1, f"Unexpected room_id: {room['room_id']}"
    assert abs(room["area_m2"] - 20.0) < 1e-6, f"Unexpected room area: {room['area_m2']}"
    assert "materials" in room, "Missing materials section in room breakdown"

    wall = room["materials"]["wall"]
    door = room["materials"]["door"]

    # Validate wall material
    assert wall["material"] == "Drywall 12mm", f"Unexpected wall material: {wall['material']}"
    assert abs(wall["area_m2"] - 20.0) < 1e-6, f"Unexpected wall area: {wall['area_m2']}"
    assert abs(wall["cost"] - 300.0) < 1e-6, f"Unexpected wall cost: {wall['cost']}"

    # Validate door material
    assert door["material"] == "Oak Door", f"Unexpected door material: {door['material']}"
    assert door["count"] == 1, f"Unexpected door count: {door['count']}"
    assert abs(door["cost"] - 120.0) < 1e-6, f"Unexpected door cost: {door['cost']}"

    # Validate total cost
    assert abs(room["total_cost"] - 420.0) < 1e-6, f"Unexpected room total cost: {room['total_cost']}"
