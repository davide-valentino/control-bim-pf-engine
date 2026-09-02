"""Room breakdown generation logic."""
from src.geometry import polygon_area


def generate_rooms_breakdown(report):
    """Generate detailed per-room material and cost breakdown."""
    rooms_breakdown = []
    semantic = report.get("semantic") or {}
    rooms = semantic.get("rooms", [])
    doors = semantic.get("doors", [])
    costs = report.get("costs") or {}

    wall_items = [i for i in costs.get("items", []) if i["type"] == "wall"]
    door_items = [i for i in costs.get("items", []) if i["type"] == "door"]

    for idx, room in enumerate(rooms, start=1):
        boundary = room.get("boundary", [])
        area_m2 = 0.0
        if boundary:
            area_mm2 = polygon_area(boundary)
            area_m2 = area_mm2 / 1_000_000.0

        room_name = room.get("name", f"Room {idx}")

        # Find wall material cost for this room
        wall_item = next((i for i in wall_items if i.get("room_id") == idx), None)
        if not wall_item and idx - 1 < len(wall_items):
            wall_item = wall_items[idx - 1]
        wall_cost = wall_item["cost"] if wall_item else 0.0
        wall_material = wall_item["material"] if wall_item else None

        # Find door material cost for this room
        door_item = next((i for i in door_items if i.get("room_id") == idx), None)
        if not door_item and door_items:
            door_item = door_items[0] if len(rooms) == 1 or idx == 1 else None
        door_cost = door_item["cost"] if door_item else 0.0
        door_material = door_item["material"] if door_item else (door_items[0]["material"] if door_items else None)
        door_count = door_item["count"] if door_item else (door_items[0]["count"] if len(rooms) == 1 and door_items else 0)

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
