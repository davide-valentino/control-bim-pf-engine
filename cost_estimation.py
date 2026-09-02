from src.pipeline.costing import (
    estimate_cost,
    load_materials,
    run_cost_estimation
)
from src.geometry import polygon_area

if __name__ == "__main__":
    run_cost_estimation()
