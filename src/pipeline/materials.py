"""Material assignment stage."""
import json
import os

# Hardcoded material catalog
MATERIAL_CATALOG = {
    "wall": {"name": "Drywall 12mm", "cost_per_m2": 15.0},
    "door": {"name": "Oak Door", "cost_per_unit": 120.0}
}


def load_semantic(path=".output/semantic.json"):
    """Load semantic JSON data."""
    with open(path) as f:
        return json.load(f)


def assign_materials(data):
    """Assign catalog materials to rooms and doors."""
    enriched_rooms = []
    for room in data.get("rooms", []):
        room_info = {
            "room_id": room.get("room_id"),
            "boundary": room["boundary"],
            "material": MATERIAL_CATALOG["wall"]
        }
        if "name" in room:
            room_info["name"] = room["name"]
        enriched_rooms.append(room_info)

    enriched_doors = []
    for door in data.get("doors", []):
        enriched_doors.append({
            "geometry": door,
            "material": MATERIAL_CATALOG["door"]
        })

    return {"rooms": enriched_rooms, "doors": enriched_doors}


def run_material_assignment(input_path=".output/semantic.json", output_path=".output/materials.json"):
    """Execute material assignment stage."""
    data = load_semantic(input_path)
    enriched = assign_materials(data)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(enriched, f, indent=2)
        print(f"Material assignment complete. Output written to {output_path}")
    return enriched


if __name__ == "__main__":
    run_material_assignment()
