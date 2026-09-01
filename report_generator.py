import json
import os

def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def polygon_area(boundary):
    area = 0.0
    n = len(boundary)
    for i in range(n-1):
        x1, y1 = boundary[i]
        x2, y2 = boundary[i+1]
        area += x1*y2 - x2*y1
    return abs(area) / 2.0  # mm^2

def generate_rooms_breakdown(report):
    rooms_breakdown = []
    semantic = report.get("semantic") or {}
    rooms = semantic.get("rooms", [])
    doors = semantic.get("doors", [])
    costs = report.get("costs") or {}

    for idx, room in enumerate(rooms, start=1):
        boundary = room.get("boundary", [])
        area_m2 = 0.0
        if boundary:
            area_mm2 = polygon_area(boundary)
            area_m2 = area_mm2 / 1_000_000.0

        # Room name from semantic stage
        room_name = room.get("name", f"Room {idx}")

        # Find wall material cost
        wall_item = next((i for i in costs.get("items", []) if i["type"] == "wall"), None)
        wall_cost = wall_item["cost"] if wall_item else 0.0
        wall_material = wall_item["material"] if wall_item else None

        # Find door material cost
        door_item = next((i for i in costs.get("items", []) if i["type"] == "door"), None)
        door_cost = door_item["cost"] if door_item else 0.0
        door_material = door_item["material"] if door_item else None
        door_count = door_item["count"] if door_item else 0

        rooms_breakdown.append({
            "room_id": idx,
            "name": room_name,
            "area_m2": area_m2,
            "materials": {
                "wall": {"material": wall_material, "area_m2": area_m2, "cost": wall_cost},
                "door": {"material": door_material, "count": door_count, "cost": door_cost}
            },
            "total_cost": wall_cost + door_cost
        })

    return rooms_breakdown

def generate_summary(report):
    semantic = report.get("semantic") or {}
    rooms = semantic.get("rooms", [])
    doors = semantic.get("doors", [])
    total_rooms = len(rooms)
    total_doors = len(doors)

    # Compute wall area
    total_area_m2 = 0.0
    for room in rooms:
        boundary = room.get("boundary", [])
        if boundary:
            area_mm2 = polygon_area(boundary)
            total_area_m2 += area_mm2 / 1_000_000.0

    # Total cost from costs.json
    costs = report.get("costs") or {}
    total_cost = costs.get("total_cost", 0.0)

    # Material breakdown from costs items
    breakdown = {}
    for item in costs.get("items", []):
        mat = item["material"]
        if mat not in breakdown:
            breakdown[mat] = {"type": item["type"], "area_m2": 0.0, "count": 0, "cost": 0.0}
        breakdown[mat]["cost"] += item["cost"]
        if item["type"] == "wall":
            breakdown[mat]["area_m2"] += item.get("area_m2", 0.0)
        elif item["type"] == "door":
            breakdown[mat]["count"] += item.get("count", 0)

    summary = {
        "rooms": total_rooms,
        "doors": total_doors,
        "wall_area_m2": total_area_m2,
        "total_cost": total_cost,
        "materials_breakdown": breakdown,
        "rooms_breakdown": generate_rooms_breakdown(report)
    }

    return summary

def generate_report():
    report = {
        "raw_geometry": load_json(".output/raw_geometry.json"),
        "semantic": load_json(".output/semantic.json"),
        "materials": load_json(".output/materials.json"),
        "costs": load_json(".output/costs.json"),
    }
    report["summary"] = generate_summary(report)
    return report

if __name__ == "__main__":
    report = generate_report()
    os.makedirs(".output", exist_ok=True)
    with open(".output/report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("Report generation complete. Output written to .output/report.json")
