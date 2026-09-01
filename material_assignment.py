import json
import os

# Hardcoded material catalog
MATERIAL_CATALOG = {
    "wall": {"name": "Drywall 12mm", "cost_per_m2": 15.0},
    "door": {"name": "Oak Door", "cost_per_unit": 120.0}
}


def load_semantic(path=".output/semantic.json"):
    with open(path) as f:
        return json.load(f)


def assign_materials(data):
    enriched_rooms = []
    for room in data["rooms"]:
        room_info = {
            "boundary": room["boundary"],
            "material": MATERIAL_CATALOG["wall"]
        }
        if "name" in room:
            room_info["name"] = room["name"]
        enriched_rooms.append(room_info)
    enriched_doors = []
    for door in data["doors"]:
        enriched_doors.append({
            "geometry": door,
            "material": MATERIAL_CATALOG["door"]
        })
    return {"rooms": enriched_rooms, "doors": enriched_doors}


if __name__ == "__main__":
    data = load_semantic()
    enriched = assign_materials(data)
    os.makedirs(".output", exist_ok=True)
    with open(".output/materials.json", "w") as f:
        json.dump(enriched, f, indent=2)
    print("Material assignment complete. Output written to .output/materials.json")