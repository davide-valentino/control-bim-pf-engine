"""Integration tests for evaluation_executor against real provider."""
import json
import os
from pathlib import Path
import pytest

from src.pipeline.evaluation_executor import execute_evaluation
from src.pipeline.parser import parse_dxf
from src.pipeline.semantics import classify_rooms
from src.visualization import export_silhouette_mask, generate_svg
from tools.iou_checker import compute_iou


@pytest.mark.real_provider
def test_real_provider_evaluation_run(tmp_path):
    if not os.getenv("REPLICATE_API_TOKEN"):
        pytest.skip("REPLICATE_API_TOKEN not set; skipping real provider integration test.")

    root = Path(__file__).resolve().parents[1]
    raw = parse_dxf(str(root / "simple_room.dxf"), output_path=None)
    semantic = classify_rooms(raw)

    svg_path = tmp_path / "input.svg"
    png_path = tmp_path / "input.png"
    generate_svg(semantic, str(svg_path))
    export_silhouette_mask(str(svg_path), str(png_path))

    cases = [
        {
            "caseId": "interior-integration-test-001",
            "inputType": "interior",
            "targetStyle": "tropical-boutique",
            "localImagePath": str(png_path),
            "silhouettePath": str(png_path),
        }
    ]

    out_dir = tmp_path / "artifacts"
    result = execute_evaluation(
        cases=cases,
        provider="replicate",
        runs_per_case=1,
        output_dir=out_dir,
    )

    runs_json_path = out_dir / "runs.json"
    summary_json_path = out_dir / "summary.json"
    assert runs_json_path.exists(), "runs.json not created"
    assert summary_json_path.exists(), "summary.json not created"

    runs = json.loads(runs_json_path.read_text())
    assert len(runs) == 1
    run = runs[0]

    assert run["caseId"] == "interior-integration-test-001"
    assert run["seed"] > 0
    assert run["modelId"]
    assert run["latencyMs"] > 0
    assert run["imageHash_SHA256"]
    assert os.path.exists(run["outputImagePath"])
    assert os.path.exists(run["controlMapPath"])
    assert os.path.exists(run["controlMapMaskPath"])
    assert os.path.exists(run["silhouetteMaskPath"])

    iou = compute_iou(run["silhouetteMaskPath"], run["controlMapMaskPath"])
    threshold = float(os.getenv("IOU_THRESHOLD", "0.85"))
    assert iou >= threshold, f"IoU {iou} below threshold {threshold}"
    assert run["passed"] is True


def test_calculate_stats():
    from src.pipeline.evaluation_executor import calculate_stats

    empty = calculate_stats([])
    assert empty["mean"] == 0.0
    assert empty["stddev"] == 0.0

    stats = calculate_stats([10, 20, 30, 40, 50])
    assert stats["mean"] == 30.0
    assert stats["min"] == 10.0
    assert stats["max"] == 50.0
    assert stats["p50"] == 30.0
    assert round(stats["stddev"], 2) == 14.14


def test_percentile():
    from src.pipeline.evaluation_executor import percentile

    assert percentile([], 0.5) == 0.0
    assert percentile([10, 20, 30, 40, 50], 0.5) == 30.0
    assert percentile([10, 20, 30, 40, 50], 0.95) == 50.0


def test_tiered_gating_and_stats():
    from src.pipeline.evaluation_executor import calculate_stats

    latencies = [15000, 16000, 18000, 20000]
    stats = calculate_stats(latencies)
    assert stats["mean"] == 17250.0
    assert stats["p50"] == 18000.0
    assert stats["p95"] == 20000.0
