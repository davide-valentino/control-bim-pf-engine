"""2D Floorplan SVG visualization generation."""
import json
import os
import io
import cairosvg
import numpy as np
import scipy.ndimage as ndi
from PIL import Image
from src.geometry import polygon_centroid


def generate_svg(data, output_path=".output/visualization.svg"):
    """Generate a clean 2D SVG floorplan overlay from semantic room and door data."""
    rooms = data.get("rooms", [])
    doors = data.get("doors", [])

    all_points = []
    for room in rooms:
        for pt in room.get("boundary", []):
            all_points.append(pt)
    for door in doors:
        if isinstance(door, dict):
            if "start" in door and "end" in door:
                all_points.append(door["start"])
                all_points.append(door["end"])
            elif "geometry" in door:
                all_points.append(door["geometry"]["start"])
                all_points.append(door["geometry"]["end"])

    if not all_points:
        min_x, min_y, max_x, max_y = 0, 0, 1000, 1000
    else:
        min_x = min(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_x = max(p[0] for p in all_points)
        max_y = max(p[1] for p in all_points)

    padding = max(500.0, (max_x - min_x) * 0.1, (max_y - min_y) * 0.1)
    view_min_x = min_x - padding
    view_min_y = min_y - padding
    view_width = max(100.0, (max_x - min_x) + 2 * padding)
    view_height = max(100.0, (max_y - min_y) + 2 * padding)

    palette = ["#e8f4f8", "#fef3c7", "#e0e7ff", "#dcfce7", "#fce7f3", "#f3e8ff"]

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_min_x} {view_min_y} {view_width} {view_height}" width="100%" height="100%" style="background-color: #f8fafc;">',
        '  <defs>',
        '    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">',
        '      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.08"/>',
        '    </filter>',
        '  </defs>',
        '  <g id="rooms">'
    ]

    for idx, room in enumerate(rooms):
        boundary = room.get("boundary", [])
        if not boundary:
            continue
        pts_str = " ".join(f"{p[0]},{p[1]}" for p in boundary)
        fill_color = palette[idx % len(palette)]
        svg_parts.append(
            f'    <polygon points="{pts_str}" fill="{fill_color}" stroke="#1e293b" stroke-width="40" stroke-linejoin="round" filter="url(#shadow)"/>'
        )

    svg_parts.append('  </g>')
    svg_parts.append('  <g id="doors">')

    for door in doors:
        if isinstance(door, dict):
            geom = door.get("geometry", door)
            start = geom.get("start")
            end = geom.get("end")
            if start and end:
                svg_parts.append(
                    f'    <line x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" stroke="#ef4444" stroke-width="60" stroke-linecap="round"/>'
                )

    svg_parts.append('  </g>')
    svg_parts.append('  <g id="labels">')

    for idx, room in enumerate(rooms):
        boundary = room.get("boundary", [])
        if not boundary:
            continue
        cx, cy = polygon_centroid(boundary)
        room_name = room.get("name", f"Room {idx+1}")
        
        area = 0.0
        n = len(boundary)
        for i in range(n - 1):
            area += boundary[i][0] * boundary[i+1][1] - boundary[i+1][0] * boundary[i][1]
        area_m2 = abs(area) / 2.0 / 1_000_000.0

        svg_parts.append(
            f'    <text x="{cx}" y="{cy - 40}" text-anchor="middle" font-family="system-ui, -apple-system, sans-serif" font-size="180" font-weight="700" fill="#0f172a">{room_name}</text>'
        )
        svg_parts.append(
            f'    <text x="{cx}" y="{cy + 140}" text-anchor="middle" font-family="system-ui, -apple-system, sans-serif" font-size="130" font-weight="500" fill="#64748b">{area_m2:.1f} m²</text>'
        )

    svg_parts.append('  </g>')
    svg_parts.append('</svg>')

    svg_content = "\n".join(svg_parts)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(svg_content)
    return svg_content


def export_silhouette_mask(svg_path, out_mask_path, size=(1024, 1024)):
    """Rasterize an SVG and save non-background geometry as a binary PNG mask."""
    png_data = cairosvg.svg2png(url=svg_path, output_width=size[0], output_height=size[1])
    image = Image.open(io.BytesIO(png_data))
    arr = np.asarray(image)
    if arr.ndim == 3 and arr.shape[2] == 4:
        mask = arr[:, :, 3] > 0
    else:
        gray = np.asarray(image.convert("L"))
        mask = gray < 250
    filled = ndi.binary_fill_holes(mask)
    os.makedirs(os.path.dirname(out_mask_path) or ".", exist_ok=True)
    Image.fromarray((filled * 255).astype(np.uint8), mode="L").save(out_mask_path)
    return out_mask_path


if __name__ == "__main__":
    if os.path.exists(".output/semantic.json"):
        with open(".output/semantic.json") as f:
            data = json.load(f)
        generate_svg(data)
        print("Visualization complete. Output written to .output/visualization.svg")
