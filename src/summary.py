"""Summary aggregation module for BOM reports."""
from src.breakdown import generate_rooms_breakdown


def generate_summary(report):
    """Aggregate overall summary including counts, areas, costs, and breakdowns."""
    semantic = report.get("semantic") or {}
    rooms = semantic.get("rooms", [])

    costs = report.get("costs") or {}
    items = costs.get("items", [])
    total_cost = costs.get("total_cost", 0.0)

    wall_items = [item for item in items if item["type"] == "wall"]
    floor_items = [item for item in items if item["type"] == "floor"]
    door_items = [item for item in items if item["type"] == "door"]
    window_items = [item for item in items if item["type"] == "window"]

    wall_area_m2 = sum(item.get("area_m2", 0.0) for item in wall_items)
    floor_area_m2 = sum(item.get("area_m2", 0.0) for item in floor_items)
    door_count = sum(item.get("count", 1) for item in door_items)
    window_count = sum(item.get("count", 1) for item in window_items)

    # Material breakdown from costs items
    breakdown = {}
    for item in items:
        material = item["material"]
        if material not in breakdown:
            breakdown[material] = {"type": item["type"], "area_m2": 0.0, "count": 0, "cost": 0.0}
        breakdown[material]["cost"] += item["cost"]
        if item["type"] in ("wall", "floor", "window"):
            breakdown[material]["area_m2"] += item.get("area_m2", 0.0)
        if item["type"] in ("door", "window"):
            breakdown[material]["count"] += item.get("count", 1)

    summary = {
        "rooms": len(rooms),
        "doors": door_count,
        "windows": window_count,
        "wall_area_m2": wall_area_m2,
        "floor_area_m2": floor_area_m2,
        "total_cost": total_cost,
        "currency": costs.get("currency"),
        "as_of": costs.get("as_of"),
        "rate_source": costs.get("rate_source"),
        "materials_breakdown": breakdown,
        "rooms_breakdown": generate_rooms_breakdown(report),
    }

    return summary
