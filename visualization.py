from src.visualization import generate_svg

if __name__ == "__main__":
    import json
    import os
    if os.path.exists(".output/semantic.json"):
        with open(".output/semantic.json") as f:
            data = json.load(f)
        generate_svg(data)
        print("Visualization complete. Output written to .output/visualization.svg")

