import ezdxf
import json

# Load the DXF file
file_path = "simple_room.dxf"
doc = ezdxf.readfile(file_path)
msp = doc.modelspace()

# Extract walls, doors, and labels
extracted_data = {"walls": [], "doors": [], "labels": []}

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
    elif entity.dxftype() == "TEXT":
        extracted_data["labels"].append({
            "text": entity.dxf.text,
            "position": [entity.dxf.insert.x, entity.dxf.insert.y]
        })
    elif entity.dxftype() == "MTEXT":
        text = entity.plain_text() if hasattr(entity, "plain_text") else entity.text
        extracted_data["labels"].append({
            "text": text,
            "position": [entity.dxf.insert.x, entity.dxf.insert.y]
        })

# Save output to JSON
# write the raw json file in the ocal .output folder
with open(".output/raw_geometry.json", "w") as f:
    json.dump(extracted_data, f, indent=2)

print("DXF parsing complete. Output written to .output/raw_geometry.json")