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


def classify_rooms(data):
    stitched = stitch_walls(data["walls"])
    rooms = []
    for loop in stitched:
        rooms.append({"boundary": loop})
    return {"rooms": rooms, "doors": data["doors"]}


if __name__ == "__main__":
    data = load_geometry()
    classified = classify_rooms(data)
    os.makedirs(".output", exist_ok=True)
    with open(".output/semantic.json", "w") as f:
        json.dump(classified, f, indent=2)
    print("Semantic classification complete. Output written to .output/semantic.json")