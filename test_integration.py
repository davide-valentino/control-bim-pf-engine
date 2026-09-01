import subprocess
import json
import os


def test_parser_integration():
    # Run the parser script to regenerate output
    result = subprocess.run(["python", "parse_dxf.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Parser failed: {result.stderr}"

    # Ensure output file exists
    output_path = os.path.join(".output", "raw_geometry.json")
    assert os.path.exists(output_path), "raw_geometry.json not found after running parser"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Expected walls and door coordinates
    expected_walls = [
        {"start": [0.0, 0.0], "end": [5000.0, 0.0]},
        {"start": [5000.0, 0.0], "end": [5000.0, 4000.0]},
        {"start": [5000.0, 4000.0], "end": [0.0, 4000.0]},
        {"start": [0.0, 4000.0], "end": [0.0, 0.0]},
    ]
    expected_door = {"start": [1000.0, 0.0], "end": [1900.0, 0.0]}

    # Validate walls
    assert data["walls"] == expected_walls, f"Walls mismatch: expected {expected_walls}, got {data['walls']}"

    # Validate doors
    assert data["doors"] == [expected_door], f"Door mismatch: expected {[expected_door]}, got {data['doors']}"
