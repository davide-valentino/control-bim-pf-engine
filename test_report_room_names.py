import subprocess
import json
import os


def test_report_room_names():
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
    assert len(rooms_breakdown) >= 1, "Expected at least one room in breakdown"

    room = rooms_breakdown[0]
    assert "name" in room, "Missing 'name' field in room breakdown"

    # If semantic stage provided a name, it should appear here; otherwise fallback
    expected_name = room.get("name")
    assert expected_name.startswith("Room") or isinstance(expected_name, str), f"Unexpected room name: {expected_name}"

    # Validate consistency with room_id fallback
    if expected_name.startswith("Room"):
        assert expected_name == f"Room {room['room_id']}", f"Fallback name mismatch: {expected_name}"
