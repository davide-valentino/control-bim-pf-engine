"""Room breakdown generation logic."""
from src.geometry import polygon_area


def _items_for_room(items, room_id):
    return [item for item in items if item.get("room_id") == room_id]


def generate_rooms_breakdown(report):
    """Generate detailed per-room material and cost breakdown."""
    rooms_breakdown = []
    semantic = report.get("semantic") or {}
    rooms = semantic.get("rooms", [])
    costs = report.get("costs") or {}

    wall_items = [item for item in costs.get("items", []) if item["type"] == "wall"]
    floor_items = [item for item in costs.get("items", []) if item["type"] == "floor"]
    door_items = [item for item in costs.get("items", []) if item["type"] == "door"]
    window_items = [item for item in costs.get("items", []) if item["type"] == "window"]

    # Openings are not room-scoped in the CAD model; attribute them to the only
    # room when the plan has exactly one room, otherwise report them globally.
    single_room = len(rooms) == 1

    for idx, room in enumerate(rooms, start=1):
        room_id = room.get("room_id", idx)
        boundary = room.get("boundary", [])
        area_m2 = polygon_area(boundary) / 1_000_000.0 if boundary else 0.0
        room_name = room.get("name", f"Room {idx}")

        wall_item = next(iter(_items_for_room(wall_items, room_id)), None)
        if wall_item is None and idx - 1 < len(wall_items):
            wall_item = wall_items[idx - 1]
        floor_item = next(iter(_items_for_room(floor_items, room_id)), None)
        if floor_item is None and idx - 1 < len(floor_items):
            floor_item = floor_items[idx - 1]

        door_cost = sum(item["cost"] for item in door_items) if single_room else 0.0
        door_count = sum(item.get("count", 1) for item in door_items) if single_room else 0
        door_material = door_items[0]["material"] if single_room and door_items else None

        window_cost = sum(item["cost"] for item in window_items) if single_room else 0.0
        window_count = sum(item.get("count", 1) for item in window_items) if single_room else 0
        window_area = sum(item.get("area_m2", 0.0) for item in window_items) if single_room else 0.0
        window_material = window_items[0]["material"] if single_room and window_items else None

        room_total = 0.0
        for item in (wall_item, floor_item):
            if item:
                room_total += item["cost"]
        room_total += door_cost + window_cost

        rooms_breakdown.append({
            "room_id": room_id,
            "name": room_name,
            "area_m2": area_m2,
            "materials": {
                "wall": {
                    "material": wall_item["material"] if wall_item else None,
                    "area_m2": wall_item.get("area_m2", 0.0) if wall_item else 0.0,
                    "cost": wall_item["cost"] if wall_item else 0.0,
                },
                "floor": {
                    "material": floor_item["material"] if floor_item else None,
                    "area_m2": floor_item.get("area_m2", 0.0) if floor_item else 0.0,
                    "cost": floor_item["cost"] if floor_item else 0.0,
                },
                "door": {"material": door_material, "count": door_count, "cost": door_cost},
                "window": {
                    "material": window_material,
                    "count": window_count,
                    "area_m2": window_area,
                    "cost": window_cost,
                },
            },
            "total_cost": room_total,
        })

    return rooms_breakdown
