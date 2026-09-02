"""Material assignment stage with style presets support."""
import json
import os

# Hardcoded default fallback catalog
MATERIAL_CATALOG = {
    "wall": {"name": "Drywall 12mm", "material": "Drywall 12mm", "cost_per_m2": 15.0},
    "door": {"name": "Oak Door", "material": "Oak Door", "cost_per_unit": 120.0}
}


def load_presets(path=None):
    """Load style presets catalog from JSON file."""
    if path and os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            return data.get("presets", data)

    default_paths = [
        os.path.join(os.path.dirname(__file__), "presets.json"),
        os.path.join("src", "pipeline", "presets.json"),
        "presets.json",
    ]
    for p in default_paths:
        if os.path.exists(p):
            with open(p) as f:
                data = json.load(f)
                return data.get("presets", data)
    return {}


STYLE_PRESETS = load_presets()


def load_semantic(path=".output/semantic.json"):
    """Load semantic JSON data."""
    with open(path) as f:
        return json.load(f)



def match_room_preset(room_name, preset_rooms):
    """Match a room name to a preset room style using exact, compound, or fallback matching."""
    if not preset_rooms:
        return {}

    # 1. Exact match
    if room_name in preset_rooms:
        return preset_rooms[room_name]

    # 2. Case-insensitive exact match
    norm_room = room_name.strip().lower()
    for key, val in preset_rooms.items():
        if key.strip().lower() == norm_room:
            return val

    # 3. Compound room name matching (e.g., "Kitchen / Dining" -> check "Kitchen", "Dining")
    if "/" in room_name:
        parts = [p.strip() for p in room_name.split("/")]
        for part in parts:
            part_lower = part.lower()
            for key, val in preset_rooms.items():
                if key.strip().lower() == part_lower:
                    return val

    # 4. Keyword / Substring match
    for key, val in preset_rooms.items():
        key_lower = key.strip().lower()
        if key_lower in norm_room or norm_room in key_lower:
            return val

    # 5. Fallback to "Living Room" or first room preset
    if "Living Room" in preset_rooms:
        return preset_rooms["Living Room"]
    return next(iter(preset_rooms.values()))


def _normalize_material_entry(entry):
    """Ensure material dictionary has both 'name' and 'material' keys."""
    if not isinstance(entry, dict):
        return entry
    norm = dict(entry)
    if "material" in norm and "name" not in norm:
        norm["name"] = norm["material"]
    elif "name" in norm and "material" not in norm:
        norm["material"] = norm["name"]
    return norm


def assign_materials(data, preset=None, catalog=None):
    """Assign catalog materials to rooms and doors, optionally applying a style preset."""
    if catalog is None:
        catalog = STYLE_PRESETS

    if preset:
        if isinstance(preset, str):
            preset_name = preset
            matched_key = next((k for k in catalog if k.lower() == preset.lower()), None)
            if not matched_key:
                raise ValueError(f"Preset '{preset}' not found. Available presets: {list(catalog.keys())}")
            preset_rooms = catalog[matched_key]
        elif isinstance(preset, dict):
            preset_name = "Custom Preset"
            preset_rooms = preset
        else:
            raise TypeError("preset must be a string or a dictionary")

        enriched_rooms = []
        for idx, room in enumerate(data.get("rooms", []), start=1):
            room_name = room.get("name", f"Room {room.get('room_id', idx)}")
            matched_style = match_room_preset(room_name, preset_rooms)

            normalized_materials = {}
            for comp_key, comp_val in matched_style.items():
                normalized_materials[comp_key] = _normalize_material_entry(comp_val)

            wall_mat = normalized_materials.get("walls") or normalized_materials.get("wall")
            if not wall_mat:
                wall_mat = _normalize_material_entry(MATERIAL_CATALOG["wall"])

            room_info = {
                "room_id": room.get("room_id", idx),
                "boundary": room["boundary"],
                "preset": preset_name,
                "material": wall_mat,
                "materials": normalized_materials
            }
            if "name" in room:
                room_info["name"] = room["name"]
            enriched_rooms.append(room_info)

        default_door_mat = None
        if "Living Room" in preset_rooms and "doors" in preset_rooms["Living Room"]:
            default_door_mat = preset_rooms["Living Room"]["doors"]
        elif preset_rooms:
            first_room = next(iter(preset_rooms.values()))
            default_door_mat = first_room.get("doors")

        door_mat = _normalize_material_entry(default_door_mat) if default_door_mat else MATERIAL_CATALOG["door"]

        enriched_doors = []
        for door in data.get("doors", []):
            enriched_doors.append({
                "geometry": door,
                "material": door_mat
            })

        return {"rooms": enriched_rooms, "doors": enriched_doors, "preset": preset_name}

    # Default legacy behavior when no preset is specified
    enriched_rooms = []
    for room in data.get("rooms", []):
        room_info = {
            "room_id": room.get("room_id"),
            "boundary": room["boundary"],
            "material": MATERIAL_CATALOG["wall"]
        }
        if "name" in room:
            room_info["name"] = room["name"]
        enriched_rooms.append(room_info)

    enriched_doors = []
    for door in data.get("doors", []):
        enriched_doors.append({
            "geometry": door,
            "material": MATERIAL_CATALOG["door"]
        })

    return {"rooms": enriched_rooms, "doors": enriched_doors}


def run_material_assignment(input_path=".output/semantic.json", output_path=".output/materials.json", preset=None, catalog_path=None):
    """Execute material assignment stage."""
    data = load_semantic(input_path)
    catalog = load_presets(catalog_path) if catalog_path else STYLE_PRESETS
    enriched = assign_materials(data, preset=preset, catalog=catalog)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(enriched, f, indent=2)
        preset_info = f" with preset '{preset}'" if preset else ""
        print(f"Material assignment complete{preset_info}. Output written to {output_path}")
    return enriched


if __name__ == "__main__":
    run_material_assignment()

