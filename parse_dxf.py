import ezdxf
import json

# Load the DXF file
file_path = "simple_room.dxf"
doc = ezdxf.readfile(file_path)
msp = doc.modelspace()

# Extract walls and doors
extracted_data = {"walls": [], "doors": []}

for entity in msp:
    if entity.dxftype() == "LWPOLYLINE" and entity.dxf.layer == "A-WALL":
        points = [(p[0], p[1]) for p in entity.get_points()]
        extracted_data["walls"].append(points)
    elif entity.dxftype() == "LINE" and entity.dxf.layer == "A-WALL":
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end = (entity.dxf.end.x, entity.dxf.end.y)
        extracted_data["walls"].append({"start": start, "end": end})
    elif entity.dxftype() == "LINE" and entity.dxf.layer == "A-DOOR":
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end = (entity.dxf.end.x, entity.dxf.end.y)
        extracted_data["doors"].append({"start": start, "end": end})

# Save output to JSON
with open("raw_geometry.json", "w") as f:
    json.dump(extracted_data, f, indent=2)

print("DXF parsing complete. Output written to raw_geometry.json")