"""Semantic classification and spatial normalization stage."""
import json
import os
import re
from src.geometry import point_in_polygon, polygon_centroid


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
    """Load raw geometry from JSON file."""
    with open(path) as f:
        return json.load(f)


def stitch_walls(walls):
    """Stitch wall line segments into closed loops."""
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


def classify_rooms(data):
    """Classify stitched walls into rooms and associate spatial labels."""
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


def classify_semantics(input_path=".output/raw_geometry.json", output_path=".output/semantic.json"):
    """Execute semantic classification stage."""
    data = load_geometry(input_path)
    classified = classify_rooms(data)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(classified, f, indent=2)
        print(f"Semantic classification complete. Output written to {output_path}")
    return classified


if __name__ == "__main__":
    classify_semantics()
