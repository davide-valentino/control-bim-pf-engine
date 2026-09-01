import json
import os

def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def generate_report():
    report = {
        "raw_geometry": load_json(".output/raw_geometry.json"),
        "semantic": load_json(".output/semantic.json"),
        "materials": load_json(".output/materials.json"),
        "costs": load_json(".output/costs.json"),
    }
    return report

if __name__ == "__main__":
    report = generate_report()
    os.makedirs(".output", exist_ok=True)
    with open(".output/report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("Report generation complete. Output written to .output/report.json")
