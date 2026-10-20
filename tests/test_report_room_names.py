import json

from tests.helpers import run_script


def test_report_room_names(canonical_workspace):
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
    assert len(rooms_breakdown) >= 1, "Expected at least one room in breakdown"

    room = rooms_breakdown[0]
    assert "name" in room, "Missing 'name' field in room breakdown"
    assert room["name"] == "Living Room", f"Expected 'Living Room', got {room.get('name')}"
