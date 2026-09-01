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

    return {
        "rooms": total_rooms,
        "doors": total_doors,
        "wall_area_m2": total_area_m2,
        "total_cost": total_cost
    }

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
