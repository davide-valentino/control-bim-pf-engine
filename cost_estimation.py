import json
import os


def load_materials(path=".output/materials.json"):
    with open(path) as f:
        return json.load(f)


def polygon_area(boundary):
    # Shoelace formula for polygon area
    area = 0.0
    n = len(boundary)
    for i in range(n-1):
        x1, y1 = boundary[i]
        x2, y2 = boundary[i+1]
        area += x1*y2 - x2*y1
    return abs(area) / 2.0  # in mm^2


def estimate_cost(data):
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


if __name__ == "__main__":
    data = load_materials()
    estimation = estimate_cost(data)
    os.makedirs(".output", exist_ok=True)
    with open(".output/costs.json", "w") as f:
        json.dump(estimation, f, indent=2)
    print("Cost estimation complete. Output written to .output/costs.json")