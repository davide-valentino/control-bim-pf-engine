"""DXF Parser stage supporting multi-layer regex matching and block reference explosion."""
import json
import os
import re
import ezdxf

WALL_LAYER_PATTERN = re.compile(
    r"(?i)(wall|dind|kolom|column|struktur|str_kolom|batas|a-wall)",
    re.IGNORECASE,
)
DOOR_LAYER_PATTERN = re.compile(
    r"(?i)(door|window|pintu|kusen|jendela|bukaan|boven|a-door)",
    re.IGNORECASE,
)


def _extract_entity_geometry(entity, extracted_data):
    """Extract wall or door linear geometry and text from a single DXF entity."""
    layer = getattr(entity.dxf, "layer", "")
    etype = entity.dxftype()

    # 1. Walls and Columns
    if WALL_LAYER_PATTERN.search(layer):
        if etype == "LINE":
            start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
            end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
            if start != end:
                extracted_data["walls"].append({"start": start, "end": end})
        elif etype in ("LWPOLYLINE", "POLYLINE"):
            pts = [(float(p[0]), float(p[1])) for p in entity.get_points()]
            is_closed = getattr(entity, "closed", False)
            if pts:
                if len(pts) >= 2 and pts[0] == pts[-1]:
                    is_closed = True
                extracted_data["walls"].append(pts)
                # Also index individual segments for robust topological processing
                for i in range(len(pts) - (0 if is_closed else 1)):
                    p1, p2 = pts[i], pts[(i + 1) % len(pts)]
                    if p1 != p2:
                        extracted_data["walls"].append({"start": p1, "end": p2})

    # 2. Doors and Openings
    elif DOOR_LAYER_PATTERN.search(layer):
        if etype == "LINE":
            start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
            end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
            if start != end:
                extracted_data["doors"].append({"start": start, "end": end})
        elif etype in ("LWPOLYLINE", "POLYLINE"):
            pts = [(float(p[0]), float(p[1])) for p in entity.get_points()]
            is_closed = getattr(entity, "closed", False)
            for i in range(len(pts) - (0 if is_closed else 1)):
                p1, p2 = pts[i], pts[(i + 1) % len(pts)]
                if p1 != p2:
                    extracted_data["doors"].append({"start": p1, "end": p2})

    # 3. Text and Annotations
    if etype == "TEXT":
        txt = entity.dxf.text.strip()
        if txt:
            extracted_data["labels"].append({
                "text": txt,
                "position": [float(entity.dxf.insert.x), float(entity.dxf.insert.y)],
            })
    elif etype == "MTEXT":
        txt = (entity.plain_text() if hasattr(entity, "plain_text") else entity.text).strip()
        if txt:
            extracted_data["labels"].append({
                "text": txt,
                "position": [float(entity.dxf.insert.x), float(entity.dxf.insert.y)],
            })


def parse_dxf(file_path="simple_room.dxf", output_path=".output/raw_geometry.json"):
    """Parse DXF file and extract walls, doors, and labels with block explosion and multi-layer support."""
    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    extracted_data = {"walls": [], "doors": [], "labels": []}

    for entity in msp:
        # Explode INSERT blocks into world-space virtual entities
        if entity.dxftype() == "INSERT":
            try:
                for ve in entity.virtual_entities():
                    _extract_entity_geometry(ve, extracted_data)
            except Exception:
                pass
        else:
            _extract_entity_geometry(entity, extracted_data)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(extracted_data, f, indent=2)
        print(f"DXF parsing complete. Output written to {output_path}")

    return extracted_data


if __name__ == "__main__":
    parse_dxf()
