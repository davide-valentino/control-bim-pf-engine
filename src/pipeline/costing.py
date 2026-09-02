"""Costing and BOM estimation stage."""
import json
import os
from src.geometry import polygon_area


def load_materials(path=".output/materials.json"):
    """Load materials JSON data."""
    with open(path) as f:
        return json.load(f)


def estimate_cost(data):
    """Calculate cost for each room and door element."""
    total_cost = 0.0
    items = []

    # Walls
    for idx, room in enumerate(data.get("rooms", []), start=1):
        boundary = room["boundary"]
        area_mm2 = polygon_area(boundary)
        area_m2 = area_mm2 / 1_000_000.0
        cost = area_m2 * room["material"]["cost_per_m2"]
        item = {
            "type": "wall",
            "room_id": room.get("room_id", idx),
            "material": room["material"]["name"],
            "area_m2": area_m2,
            "cost": cost
        }
        if "name" in room:
            item["room_name"] = room["name"]
        items.append(item)
        total_cost += cost

    # Doors
    for door in data.get("doors", []):
        cost = door["material"]["cost_per_unit"]
        items.append({
            "type": "door",
            "material": door["material"]["name"],
            "count": 1,
            "cost": cost
        })
        total_cost += cost

    return {"items": items, "total_cost": total_cost}


def run_cost_estimation(input_path=".output/materials.json", output_path=".output/costs.json"):
    """Execute cost estimation stage."""
    data = load_materials(input_path)
    estimation = estimate_cost(data)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(estimation, f, indent=2)
        print(f"Cost estimation complete. Output written to {output_path}")
    return estimation


if __name__ == "__main__":
    run_cost_estimation()
