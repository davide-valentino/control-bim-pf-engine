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
    assert room["name"] == "Living Room", f"Expected 'Living Room', got {room.get('name')}"
