"""Summary aggregation module for BOM reports."""
from src.geometry import polygon_area
from src.breakdown import generate_rooms_breakdown


def generate_summary(report):
    """Aggregate overall summary including counts, areas, costs, and breakdowns."""
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
