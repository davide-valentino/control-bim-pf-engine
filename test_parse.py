import json
import os


def test_raw_geometry_structure_and_coordinates():
    # Ensure output file exists
    output_path = os.path.join(".output", "raw_geometry.json")
    assert os.path.exists(output_path), "raw_geometry.json not found"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Validate keys
    assert "walls" in data, "Missing 'walls' key"
    assert "doors" in data, "Missing 'doors' key"

    # Expected walls and door coordinates
    expected_walls = [
        {"start": [0.0, 0.0], "end": [5000.0, 0.0]},
        {"start": [5000.0, 0.0], "end": [5000.0, 4000.0]},
        {"start": [5000.0, 4000.0], "end": [0.0, 4000.0]},
        {"start": [0.0, 4000.0], "end": [0.0, 0.0]},
    ]
    expected_door = {"start": [1000.0, 0.0], "end": [1900.0, 0.0]}

    # Validate walls
    assert len(data["walls"]) == len(expected_walls), f"Expected {len(expected_walls)} walls, got {len(data['walls'])}"
    for wall, expected in zip(data["walls"], expected_walls):
        assert wall == expected, f"Wall mismatch: expected {expected}, got {wall}"

    # Validate doors
    assert len(data["doors"]) == 1, f"Expected 1 door, got {len(data['doors'])}"
    assert data["doors"][0] == expected_door, f"Door mismatch: expected {expected_door}, got {data['doors'][0]}"

    # Validate labels
    assert "labels" in data, "Missing 'labels' key"
    assert len(data["labels"]) == 1, f"Expected 1 label, got {len(data['labels'])}"
    assert data["labels"][0] == {"text": "Living Room", "position": [2500.0, 2000.0]}
