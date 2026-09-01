import json
import os
import re


ABBREVIATIONS = {
    "BR": "Bedroom",
    "BDRM": "Bedroom",
    "MBR": "Master Bedroom",
    "M.BR": "Master Bedroom",
    "KIT": "Kitchen",
    "KITCH": "Kitchen",
    "LR": "Living Room",
    "LIV": "Living Room",
    "DR": "Dining Room",
    "DIN": "Dining",
    "DINING": "Dining",
    "BA": "Bathroom",
    "BATH": "Bathroom",
    "WC": "WC",
    "CORR": "Corridor",
    "BALC": "Balcony",
    "STOR": "Storage",
    "STR": "Storage",
    "UTIL": "Utility Room",
    "OFF": "Office",
}

ACRONYMS = {"WC", "HVAC", "AC", "TV", "ID", "BOM", "CAD", "DXF"}


def normalize_label(text):
    """Normalize DXF text label: clean formatting, trim whitespace, expand abbreviations, normalize casing."""
    if not text:
        return ""
    
    # Remove MTEXT curly braces without stripping enclosed content
    clean = text.replace("{", "").replace("}", "")
    # Replace \P (paragraph break) and \X with space
    clean = re.sub(r"\\[PpXx]", " ", clean)
    # Remove format codes like \fArial|b0|i0;, \A1;, \H1.5;, \W0.8;, \C1;, \F...;
    clean = re.sub(r"\\[A-Za-z0-9|.,=~^ -]+;?", " ", clean)
    # Remove DXF formatting flags %%u, %%d, %%c, %%p, %%o
    clean = re.sub(r"%%[a-zA-Z]", " ", clean)
    # Collapse multiple whitespaces
    clean = re.sub(r"\s+", " ", clean).strip()

    if not clean:
        return ""

    # Check whole-string abbreviation lookup (case-insensitive)
    upper = clean.upper()
    if upper in ABBREVIATIONS:
        return ABBREVIATIONS[upper]

    # Normalize words while preserving known acronyms and expanding word abbreviations
    words = clean.split()
    normalized_words = []
    for w in words:
        w_upper = w.upper()
        if w_upper in ACRONYMS:
            normalized_words.append(w_upper)
        elif w_upper in ABBREVIATIONS:
            normalized_words.append(ABBREVIATIONS[w_upper])
        else:
            normalized_words.append(w.capitalize())

    return " ".join(normalized_words)


def load_geometry(path=".output/raw_geometry.json"):
    with open(path) as f:
        return json.load(f)


def stitch_walls(walls):
    # naive stitching: chain segments by matching endpoints
    loops = []
    used_walls = set()
    for i, wall in enumerate(walls):
        if i in used_walls:
            continue
        loop = [wall["start"], wall["end"]]
        used_walls.add(i)
        current = wall["end"]
        while current != wall["start"]:
            next_idx, next_wall = next(
                ((idx, w) for idx, w in enumerate(walls) if idx not in used_walls and w["start"] == current),
                (None, None)
            )
            if not next_wall:
                break
            loop.append(next_wall["end"])
            used_walls.add(next_idx)
            current = next_wall["end"]
        if len(loop) > 2 and loop[0] == loop[-1]:
            loops.append(loop)
    return loops


def point_in_polygon(point, polygon):
    """Ray-casting point-in-polygon algorithm."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n - 1):
        x1, y1 = polygon[i]
        x2, y2 = polygon[i + 1]
        if ((y1 > y) != (y2 > y)):
            x_intersect = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_intersect:
                inside = not inside
    return inside


def polygon_centroid(boundary):
    """Compute centroid (cx, cy) of a polygon boundary."""
    area = 0.0
    cx = 0.0
    cy = 0.0
    n = len(boundary)
    for i in range(n - 1):
        x1, y1 = boundary[i]
        x2, y2 = boundary[i + 1]
        cross = (x1 * y2 - x2 * y1)
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    area = area / 2.0
    if abs(area) < 1e-6:
        xs = [p[0] for p in boundary]
        ys = [p[1] for p in boundary]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    cx = cx / (6.0 * area)
    cy = cy / (6.0 * area)
    return (cx, cy)


def classify_rooms(data):
    stitched = stitch_walls(data.get("walls", []))
    labels = data.get("labels", [])
    rooms = []
    
    for idx, loop in enumerate(stitched, start=1):
        matching_labels = []
        for label in labels:
            pos = label.get("position")
            if pos and point_in_polygon(pos, loop):
                raw_text = label.get("text", "")
                norm = normalize_label(raw_text)
                if norm and norm not in matching_labels:
                    matching_labels.append(norm)
        
        if matching_labels:
            room_name = " / ".join(matching_labels)
        else:
            room_name = f"Room {idx}"
        
        room_data = {
            "room_id": idx,
            "name": room_name,
            "boundary": loop
        }
        rooms.append(room_data)
    
    return {"rooms": rooms, "doors": data.get("doors", [])}


if __name__ == "__main__":
    data = load_geometry()
    classified = classify_rooms(data)
    os.makedirs(".output", exist_ok=True)
    with open(".output/semantic.json", "w") as f:
        json.dump(classified, f, indent=2)
    print("Semantic classification complete. Output written to .output/semantic.json")