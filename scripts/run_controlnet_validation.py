"""Run one real DXF-to-ControlNet validation."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline.evaluation_executor import execute_evaluation
from src.pipeline.parser import parse_dxf
from src.pipeline.semantics import classify_rooms
from src.visualization import export_silhouette_mask, generate_svg


def main():
    parser = argparse.ArgumentParser(description="Run fast real ControlNet validation.")
    parser.add_argument("--cases", default="tests/fixtures/cases_fast.json")
    args = parser.parse_args()

    cases_file = Path(args.cases)
    if not cases_file.is_file():
        cases_file = ROOT / args.cases

    cases = json.loads(cases_file.read_text())
    if len(cases) != 1 or cases[0].get("inputType") != "interior":
        raise ValueError("cases_fast.json must contain exactly one interior case")

    # Generate real DXF silhouette input if needed
    raw = parse_dxf(str(ROOT / "simple_room.dxf"), output_path=None)
    semantic = classify_rooms(raw)
    svg_path = ROOT / ".output" / "fast-input.svg"
    image_path = ROOT / ".output" / "fast-input.png"
    generate_svg(semantic, str(svg_path))
    export_silhouette_mask(str(svg_path), str(image_path))

    cases[0]["localImagePath"] = str(image_path)
    cases[0]["silhouettePath"] = str(image_path)

    result = execute_evaluation(cases, provider="replicate", runs_per_case=1)
    run = result["runs"][0]
    print(
        json.dumps(
            {
                "caseId": run["caseId"],
                "iou": run["iou"],
                "threshold": run["iouThreshold"],
                "passed": run["passed"],
                "latencyMs": run["latencyMs"],
                "artifacts": result["artifactDir"],
            },
            indent=2,
        )
    )
    return 0 if run["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ControlNet validation failed: {error}", file=sys.stderr)
        sys.exit(1)