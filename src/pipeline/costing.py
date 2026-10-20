"""Costing and BOM estimation stage.

Quantity rules (deterministic, documented in the BOM output):

* wall  = room perimeter x wall height (wall surface, NOT floor area)
* floor = room boundary area
* door  = one clustered opening unit (door swings / jambs are grouped upstream)
* window = clustered opening width x assumed window height

Rates come from the material catalog and carry currency / as-of / source
metadata so placeholder numbers can never be mistaken for partner-firm rates.
"""
import json
import os

from src.geometry import polygon_area, polygon_perimeter
from src.pipeline.materials import CATALOG_METADATA

DEFAULT_WALL_HEIGHT_M = 3.0
DEFAULT_WINDOW_HEIGHT_M = 1.5
DEFAULT_OPENING_WIDTH_M = 0.9


def load_materials(path=".output/materials.json"):
    """Load materials JSON data."""
    with open(path) as f:
        return json.load(f)


def _env_float(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def _room_component_material(room, key, fallback):
    """Resolve a room component material, accepting singular/plural keys."""
    materials = room.get("materials") or {}
    return materials.get(key) or materials.get(key.rstrip("s")) or room.get("material") or fallback


def _preset_block(metadata):
    """Expose the exact rate-sheet identity used for this estimate."""
    if not (metadata.get("preset_id") or metadata.get("preset_name")):
        return None
    return {
        "id": metadata.get("preset_id"),
        "name": metadata.get("preset_name"),
        "version": metadata.get("preset_version"),
        "origin": metadata.get("preset_origin"),
    }


def _opening_width_m(opening):
    """Opening width in metres from semantic metadata, with a documented fallback."""
    if isinstance(opening, dict):
        width_mm = opening.get("width_mm")
        if width_mm:
            return float(width_mm) / 1000.0
        start, end = opening.get("start"), opening.get("end")
        if start and end:
            dx = float(end[0]) - float(start[0])
            dy = float(end[1]) - float(start[1])
            return (dx * dx + dy * dy) ** 0.5 / 1000.0
    return DEFAULT_OPENING_WIDTH_M


def estimate_cost(data):
    """Calculate deterministic quantities and BOM cost per room and opening."""
    wall_height_m = _env_float("WALL_HEIGHT_M", DEFAULT_WALL_HEIGHT_M)
    window_height_m = _env_float("WINDOW_HEIGHT_M", DEFAULT_WINDOW_HEIGHT_M)
    metadata = data.get("metadata") or CATALOG_METADATA

    total_cost = 0.0
    items = []

    # Walls and floors per room
    for idx, room in enumerate(data.get("rooms", []), start=1):
        boundary = room["boundary"]
        floor_area_m2 = polygon_area(boundary) / 1_000_000.0
        perimeter_m = polygon_perimeter(boundary) / 1000.0
        wall_area_m2 = perimeter_m * wall_height_m

        wall_material = _room_component_material(room, "walls", {"name": "Unassigned wall"})
        wall_cost = wall_area_m2 * float(wall_material.get("cost_per_m2", 0.0))
        wall_item = {
            "type": "wall",
            "room_id": room.get("room_id", idx),
            "material": wall_material.get("name") or wall_material.get("material"),
            "area_m2": round(wall_area_m2, 4),
            "perimeter_m": round(perimeter_m, 4),
            "cost": wall_cost,
        }
        if "name" in room:
            wall_item["room_name"] = room["name"]
        items.append(wall_item)
        total_cost += wall_cost

        floor_material = _room_component_material(room, "floors", {"name": "Unassigned floor"})
        floor_cost = floor_area_m2 * float(floor_material.get("cost_per_m2", 0.0))
        floor_item = {
            "type": "floor",
            "room_id": room.get("room_id", idx),
            "material": floor_material.get("name") or floor_material.get("material"),
            "area_m2": round(floor_area_m2, 4),
            "cost": floor_cost,
        }
        if "name" in room:
            floor_item["room_name"] = room["name"]
        items.append(floor_item)
        total_cost += floor_cost

    # Doors (per unit) and windows (per opening area)
    for opening in data.get("doors", []):
        geometry = opening.get("geometry", opening) if isinstance(opening, dict) else opening
        opening_type = opening.get("type", "door") if isinstance(opening, dict) else "door"
        material = opening.get("material", {}) if isinstance(opening, dict) else {}
        material_name = material.get("name") or material.get("material")

        if opening_type == "window":
            width_m = _opening_width_m(geometry)
            area_m2 = width_m * window_height_m
            cost = area_m2 * float(material.get("cost_per_m2", 0.0))
            items.append({
                "type": "window",
                "material": material_name,
                "area_m2": round(area_m2, 4),
                "width_m": round(width_m, 4),
                "count": 1,
                "cost": cost,
            })
        else:
            cost = float(material.get("cost_per_unit", 0.0))
            items.append({
                "type": "door",
                "material": material_name,
                "count": 1,
                "cost": cost,
            })
        total_cost += cost

    return {
        "items": items,
        "total_cost": total_cost,
        "currency": metadata.get("currency", "USD"),
        "as_of": metadata.get("as_of"),
        "rate_source": metadata.get("source"),
        "preset": _preset_block(metadata),
        "assumptions": {
            "wall_height_m": wall_height_m,
            "window_height_m": window_height_m,
            "wall_quantity_basis": "room perimeter x wall height",
            "floor_quantity_basis": "room boundary area",
            "door_quantity_basis": "clustered opening units",
            "window_quantity_basis": "clustered opening width x assumed window height",
        },
    }


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
