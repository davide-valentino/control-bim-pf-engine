"""Geometry and math utilities for CAD polygon computations."""


def polygon_area(boundary):
    """Compute polygon area in mm^2 using the shoelace formula."""
    if not boundary or len(boundary) < 3:
        return 0.0
    area = 0.0
    n = len(boundary)
    for i in range(n - 1):
        x1, y1 = boundary[i]
        x2, y2 = boundary[i + 1]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def polygon_centroid(boundary):
    """Compute centroid (cx, cy) of a polygon boundary."""
    if not boundary:
        return (0.0, 0.0)
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


def point_in_polygon(point, polygon):
    """Ray-casting point-in-polygon containment test."""
    if not polygon or len(polygon) < 3:
        return False
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
