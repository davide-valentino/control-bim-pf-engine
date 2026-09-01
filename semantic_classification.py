import json
import os


def load_geometry(path=".output/raw_geometry.json"):
    with open(path) as f:
        return json.load(f)


def stitch_walls(walls):
    # naive stitching: chain segments by matching endpoints
    loops = []
    used = set()
    for wall in walls:
        if tuple(wall["start"]) in used:
            continue
        loop = [wall["start"], wall["end"]]
        used.add(tuple(wall["start"]))
        used.add(tuple(wall["end"]))
        current = wall["end"]
        while True:
            next_wall = next((w for w in walls if tuple(w["start"]) == tuple(current) and tuple(w["end"]) not in used), None)
            if not next_wall:
                break
            loop.append(next_wall["end"])
            used.add(tuple(next_wall["start"]))
            used.add(tuple(next_wall["end"]))
            current = next_wall["end"]
            if current == wall["start"]:
                loop.append(current)
                break
        if len(loop) > 2:
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