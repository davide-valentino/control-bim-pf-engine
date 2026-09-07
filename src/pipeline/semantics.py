"""Semantic classification and spatial normalization stage with topological polygonization."""
import json
import os
import re
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import polygonize, unary_union
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
    # Indonesian architectural vocabulary
    "DAPUR": "Kitchen",
    "KM": "Bathroom",
    "TOILET": "Toilet",
    "KAMAR": "Bedroom",
    "TIDUR": "Bedroom",
    "TERAS": "Terrace",
    "BALKON": "Balcony",
    "GUDANG": "Storage",
    "TANGGA": "Stairs",
    "TAMAN": "Garden",
    "KELUARGA": "Living Room",
    "TAMU": "Guest Room",
    "KUSEN": "Door Frame",
}

ACRONYMS = {"WC", "HVAC", "AC", "TV", "ID", "BOM", "CAD", "DXF", "FFL"}

CONSTRUCTION_FILTER_TERMS = [
    "NOTE", "START POINT", "CERAMIC", "CEILING", "PLAFON", "LANTAI",
    "SK H=", "SWITCH", "AVOOR", "RAK SABUN", "CH +", "SUDAH DIBELI",
    "SCALE", "SKALA", "FFL", "POTONGAN", "TAMPAK", "DETAIL", "SK DINDING",
    "BOTTOM TV"
]


def clean_semantic_room_label(raw_text):
    """Map raw architectural/CAD text into a clean room or functional area name."""
    if not raw_text:
        return ""
    clean = normalize_label(raw_text)
    if not clean:
        return ""
    # Filter out pure numbers or dimensions (e.g., "5", "20", "3", "30 x 60")
    if re.match(r"^[\d\s.,xX+-]+$", clean):
        return ""
    u = clean.upper()
    if any(skip in u for skip in CONSTRUCTION_FILTER_TERMS):
        return ""

    if "SOFABED" in u or "LIVING" in u or "KELUARGA" in u:
        return "Living Area"
    if "BED" in u or "QUEEN" in u or "KAMAR TIDUR" in u or "KAMAR" in u:
        return "Bedroom"
    if "WORKDESK" in u or "STUDY" in u or "MEJA KERJA" in u or "OFFICE" in u:
        return "Study / Work Area"
    if "CUPBOARD" in u or "LEMARI" in u or "WARDROBE" in u or "CLOSET" in u:
        return "Wardrobe / Dressing Area"
    if "DAPUR" in u or "KITCHEN" in u:
        return "Kitchen"
    if "TOILET" in u or "BATH" in u or "WC" in u or "KM" in u or "KAMAR MANDI" in u:
        return "Bathroom / Toilet"
    if "DINING" in u or "MAKAN" in u:
        return "Dining Area"
    if "TERAS" in u or "TERRACE" in u:
        return "Terrace"
    if "BALKON" in u or "BALCONY" in u:
        return "Balcony"
    if "GUDANG" in u or "STORAGE" in u:
        return "Storage"
    if "SHAFT" in u or "PLUMBING" in u:
        return "Service Shaft"
    if "FOYER" in u:
        return "Foyer"
    if "CORRIDOR" in u or "KORIDOR" in u or "HALL" in u:
        return "Corridor"
    if "TANGGA" in u or "STAIRS" in u or "NAIK" in u or "TURUN" in u:
        return "Stairs"
    if "TV" in u:
        return "Living / Media Area"

    return clean


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
    """Classify walls and openings into rooms and associate spatial labels."""
    wall_dicts = [w for w in data.get("walls", []) if isinstance(w, dict) and "start" in w and "end" in w]
    stitched = stitch_walls(wall_dicts)
    labels = data.get("labels", [])

    # 1. Fast-path for simple synthetic/single-loop drawings
    if len(stitched) > 0 and len(wall_dicts) < 20:
        rooms = []
        for idx, loop in enumerate(stitched, start=1):
            matching_labels = []
            for label in labels:
                pos = label.get("position")
                if pos:
                    pt = Point(pos[0], pos[1])
                    poly = Polygon(loop)
                    if poly.contains(pt) or poly.distance(pt) < 300:
                        norm = normalize_label(label.get("text", ""))
                        if norm and norm not in matching_labels:
                            matching_labels.append(norm)

            room_name = " / ".join(matching_labels) if matching_labels else f"Room {idx}"
            rooms.append({
                "room_id": idx,
                "name": room_name,
                "boundary": loop,
            })
        return {"rooms": rooms, "doors": data.get("doors", [])}

    # 2. Topological polygonization for real-world / complex multi-line CAD packages
    segments = []
    for item in data.get("walls", []):
        if isinstance(item, dict) and "start" in item and "end" in item:
            p1, p2 = tuple(item["start"]), tuple(item["end"])
            if p1 != p2:
                segments.append(LineString([p1, p2]))
        elif isinstance(item, list) and len(item) >= 2:
            for i in range(len(item) - 1):
                p1, p2 = tuple(item[i]), tuple(item[i + 1])
                if p1 != p2:
                    segments.append(LineString([p1, p2]))

    for item in data.get("doors", []):
        if isinstance(item, dict) and "start" in item and "end" in item:
            p1, p2 = tuple(item["start"]), tuple(item["end"])
            if p1 != p2:
                segments.append(LineString([p1, p2]))

    if not segments:
        return {"rooms": [], "doors": data.get("doors", [])}

    merged = unary_union(segments)
    candidate_polys = [
        p for p in polygonize(merged)
        if 1_000_000 <= p.area <= 350_000_000  # 1.0 m^2 to 350 m^2
    ]

    # Detect plan sheet title markers and non-plan markers
    plan_markers = []
    non_plan_markers = []
    for l in labels:
        txt = l.get("text", "").strip()
        u = txt.upper()
        pos = l.get("position", [0, 0])
        pt = Point(pos[0], pos[1])
        if any(k in u for k in ["DENAH", "FLOOR PLAN", "PLAN", "LAYOUT"]):
            if not any(k in u for k in ["TITIK LAMPU", "POLA KERAMIK", "PLAFON"]):
                plan_markers.append((txt, pt))
        elif any(k in u for k in ["TAMPAK", "POTONGAN", "SECTION", "ELEVATION", "DETAIL", "CERAMIC"]):
            non_plan_markers.append((txt, pt))

    rooms = []
    room_idx = 1
    for poly in candidate_polys:
        # If CAD package contains distinct sheets, filter out elevation/section/detail views
        if non_plan_markers and plan_markers:
            dist_to_plan = min(poly.distance(pt) for _, pt in plan_markers)
            dist_to_non_plan = min(poly.distance(pt) for _, pt in non_plan_markers)
            if dist_to_non_plan < dist_to_plan and dist_to_plan > 15000:
                continue

        matching_labels = []
        for l in labels:
            pos = l.get("position")
            if pos:
                pt = Point(pos[0], pos[1])
                if poly.contains(pt) or poly.distance(pt) < 500:
                    raw_txt = l.get("text", "")
                    clean_label = clean_semantic_room_label(raw_txt)
                    if clean_label and clean_label not in matching_labels:
                        matching_labels.append(clean_label)

        sheet_name = None
        if plan_markers:
            nearest_title = min(plan_markers, key=lambda m: poly.distance(m[1]))[0]
            sheet_name = normalize_label(nearest_title)

        if matching_labels:
            room_name = " / ".join(matching_labels[:2])
        elif sheet_name:
            room_name = f"{sheet_name} - Space {room_idx}"
        else:
            room_name = f"Room {room_idx}"

        coords = [[float(x), float(y)] for x, y in poly.exterior.coords]
        rooms.append({
            "room_id": room_idx,
            "name": room_name,
            "boundary": coords,
        })
        room_idx += 1

    return {"rooms": rooms, "doors": data.get("doors", [])}

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
