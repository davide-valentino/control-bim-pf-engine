import json
import os


def test_raw_geometry_structure():
    # Ensure output file exists
    output_path = os.path.join(".output", "raw_geometry.json")
    assert os.path.exists(output_path), "raw_geometry.json not found"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Validate keys
    assert "walls" in data, "Missing 'walls' key"
    assert "doors" in data, "Missing 'doors' key"

    # Validate walls
    assert len(data["walls"]) == 4, f"Expected 4 walls, got {len(data['walls'])}"
    for wall in data["walls"]:
        assert "start" in wall and "end" in wall, "Wall missing start/end"
        assert len(wall["start"]) == 2 and len(wall["end"]) == 2, "Wall coordinates invalid"

    # Validate doors
    assert len(data["doors"]) == 1, f"Expected 1 door, got {len(data['doors'])}"
    door = data["doors"][0]
    assert "start" in door and "end" in door, "Door missing start/end"
    assert len(door["start"]) == 2 and len(door["end"]) == 2, "Door coordinates invalid"
