from src.pipeline.semantics import (
    load_geometry,
    stitch_walls,
    classify_rooms,
    classify_semantics,
    normalize_label
)
from src.geometry import point_in_polygon, polygon_centroid

if __name__ == "__main__":
    classify_semantics()
