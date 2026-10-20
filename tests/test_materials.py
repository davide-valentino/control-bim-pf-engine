import json

from tests.helpers import run_script


def test_material_assignment(canonical_workspace):
    # Run the material assignment script inside an isolated workspace
    result = run_script("material_assignment.py", canonical_workspace)
    assert result.returncode == 0, f"Material assignment failed: {result.stderr}"

    output_path = canonical_workspace / ".output" / "materials.json"
    assert output_path.exists(), "materials.json not found after running assignment"

    with open(output_path) as f:
        data = json.load(f)

    # Validate rooms
    assert "rooms" in data, "Missing 'rooms' key"
    assert len(data["rooms"]) == 1, f"Expected 1 room, got {len(data['rooms'])}"
    room = data["rooms"][0]
    assert "material" in room, "Room missing material assignment"
    assert room["material"]["name"] == "Drywall 12mm", f"Unexpected wall material: {room['material']}"
    assert "cost_per_m2" in room["material"], "Wall material missing cost_per_m2"
    assert room["materials"]["floors"]["name"] == "Ceramic Tile", "Room missing floor material"

    # Validate openings (one clustered door)
    assert "doors" in data, "Missing 'doors' key"
    assert len(data["doors"]) == 1, f"Expected 1 door, got {len(data['doors'])}"
    door = data["doors"][0]
    assert door["type"] == "door", f"Unexpected opening type: {door['type']}"
    assert "material" in door, "Door missing material assignment"
    assert door["material"]["name"] == "Oak Door", f"Unexpected door material: {door['material']}"
    assert "cost_per_unit" in door["material"], "Door material missing cost_per_unit"

    # Validate rate provenance metadata
    assert data["metadata"]["currency"], "Missing currency metadata"
    assert data["metadata"]["as_of"], "Missing as_of metadata"
    assert "placeholder" in data["metadata"]["source"].lower(), "Missing placeholder rate warning"
