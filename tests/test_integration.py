import json

from tests.helpers import run_script


def test_parser_integration(canonical_workspace):
    # Run the parser script inside an isolated workspace
    result = run_script("parse_dxf.py", canonical_workspace)
    assert result.returncode == 0, f"Parser failed: {result.stderr}"

    output_path = canonical_workspace / ".output" / "raw_geometry.json"
    assert output_path.exists(), "raw_geometry.json not found after running parser"

    with open(output_path) as f:
        data = json.load(f)

    # Expected walls and door coordinates
    expected_walls = [
        {"start": [0.0, 0.0], "end": [5000.0, 0.0]},
        {"start": [5000.0, 0.0], "end": [5000.0, 4000.0]},
        {"start": [5000.0, 4000.0], "end": [0.0, 4000.0]},
        {"start": [0.0, 4000.0], "end": [0.0, 0.0]},
    ]
    expected_door = {"start": [1000.0, 0.0], "end": [1900.0, 0.0], "layer": "A-DOOR"}

    # Validate walls
    assert data["walls"] == expected_walls, f"Walls mismatch: expected {expected_walls}, got {data['walls']}"

    # Validate doors
    assert data["doors"] == [expected_door], f"Door mismatch: expected {[expected_door]}, got {data['doors']}"
