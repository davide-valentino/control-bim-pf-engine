import json
import os


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


def classify_rooms(data):
    stitched = stitch_walls(data.get("walls", []))
    labels = data.get("labels", [])
    rooms = []
    for idx, loop in enumerate(stitched, start=1):
        room_name = None
        for label in labels:
            pos = label.get("position")
            if pos and point_in_polygon(pos, loop):
                room_name = label.get("text")
                break
        
        room_data = {
            "name": room_name if room_name else f"Room {idx}",
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