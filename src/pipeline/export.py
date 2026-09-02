"""BIM / IFC / CSV Export stage."""
import json
import os


def export_csv_summary(report, output_path=".output/summary.csv"):
    """Export room breakdown and BOM as a CSV file."""
    summary = report.get("summary", {})
    rooms_breakdown = summary.get("rooms_breakdown", [])

    lines = ["Room ID,Room Name,Area (m2),Wall Material,Wall Cost,Door Material,Door Cost,Total Cost"]
    for r in rooms_breakdown:
        rid = r.get("room_id", "")
        name = r.get("name", "")
        area = r.get("area_m2", 0.0)
        wall_mat = r.get("materials", {}).get("wall", {}).get("material", "")
        wall_cost = r.get("materials", {}).get("wall", {}).get("cost", 0.0)
        door_mat = r.get("materials", {}).get("door", {}).get("material", "")
        door_cost = r.get("materials", {}).get("door", {}).get("cost", 0.0)
        tot = r.get("total_cost", 0.0)
        lines.append(f'{rid},"{name}",{area:.2f},"{wall_mat}",{wall_cost:.2f},"{door_mat}",{door_cost:.2f},{tot:.2f}')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return output_path
