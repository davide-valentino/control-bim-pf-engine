import subprocess
import json
import os
import sys


def test_material_assignment():
    # Run the material assignment script to regenerate output
    result = subprocess.run([sys.executable, "material_assignment.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Material assignment failed: {result.stderr}"

    # Ensure output file exists
    output_path = os.path.join(".output", "materials.json")
    assert os.path.exists(output_path), "materials.json not found after running assignment"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Validate rooms
    assert "rooms" in data, "Missing 'rooms' key"
    assert len(data["rooms"]) == 1, f"Expected 1 room, got {len(data['rooms'])}"
    room = data["rooms"][0]
    assert "material" in room, "Room missing material assignment"
    assert room["material"]["name"] == "Drywall 12mm", f"Unexpected wall material: {room['material']}"
    assert "cost_per_m2" in room["material"], "Wall material missing cost_per_m2"

    # Validate doors
    assert "doors" in data, "Missing 'doors' key"
    assert len(data["doors"]) == 1, f"Expected 1 door, got {len(data['doors'])}"
    door = data["doors"][0]
    assert "material" in door, "Door missing material assignment"
    assert door["material"]["name"] == "Oak Door", f"Unexpected door material: {door['material']}"
    assert "cost_per_unit" in door["material"], "Door material missing cost_per_unit"
