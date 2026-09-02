"""Report Orchestration Module."""
import json
import os
from src.summary import generate_summary
from src.visualization import generate_svg


def load_json(path):
    """Safely load a JSON file if it exists, otherwise return None."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def generate_report():
    """Aggregate all pipeline stages into a unified consolidated report."""
    report = {
        "raw_geometry": load_json(".output/raw_geometry.json"),
        "semantic": load_json(".output/semantic.json"),
        "materials": load_json(".output/materials.json"),
        "costs": load_json(".output/costs.json"),
    }
    report["summary"] = generate_summary(report)
    return report


def main():
    report = generate_report()
    os.makedirs(".output", exist_ok=True)
    with open(".output/report.json", "w") as f:
        json.dump(report, f, indent=2)
    if report.get("semantic"):
        generate_svg(report["semantic"], ".output/visualization.svg")
    print("Report generation complete. Output written to .output/report.json and .output/visualization.svg")
    return report


if __name__ == "__main__":
    main()
