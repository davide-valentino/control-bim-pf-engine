"""Evaluation executor orchestrating real ControlNet runs, artifact saving, and IoU gating."""
import argparse
import base64
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from PIL import Image

from src.pipeline.debug_map import generate_control_map, save_control_map_and_mask
from src.pipeline.image_io import normalize_source
from src.pipeline.replicate_adapter import EvalPayload, ReplicateAdapter
from tools.iou_checker import compute_iou, save_binary_mask


def fetch_image_bytes(source: str) -> bytes:
    """Fetch image bytes from a URL or data URL."""
    if source.startswith("data:"):
        encoded = source.split(",", 1)[1]
        return base64.b64decode(encoded)
    with urlopen(source, timeout=120) as response:
        return response.read()


def percentile(sorted_values: list[float | int], p: float) -> float:
    """Compute percentile from sorted list."""
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, int(len(sorted_values) * p))
    return float(sorted_values[idx])


def execute_evaluation(
    cases: list[dict | EvalPayload],
    provider: str = "replicate",
    runs_per_case: int = 1,
    replicate_overrides: dict | None = None,
    output_dir: str | Path | None = None,
) -> dict:
    """Run real ControlNet evaluation across test cases and persist artifacts."""
    if provider != "replicate":
        raise ValueError(
            f"Unsupported provider '{provider}'. Only the real 'replicate' provider is supported; "
            "no mocks or fallback are allowed."
        )

    if runs_per_case < 1 or runs_per_case > 10:
        raise ValueError(f"runs_per_case must be between 1 and 10, got {runs_per_case}")

    iou_threshold = float(os.getenv("IOU_THRESHOLD", "0.85"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if output_dir is None:
        target_dir = Path("artifacts/evaluations") / timestamp
    else:
        target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    adapter = ReplicateAdapter(artifact_dir=str(target_dir))
    runs = []

    for case_idx, case_data in enumerate(cases):
        payload = case_data if isinstance(case_data, EvalPayload) else EvalPayload(**case_data)
        normalized_image = normalize_source(payload.imageUrl, payload.localImagePath)

        # 1. Deterministic silhouette mask
        silhouette_mask_path = target_dir / f"silhouette-mask-{payload.caseId}.png"
        silhouette_source = payload.silhouettePath or payload.localImagePath or normalized_image
        save_binary_mask(silhouette_source, silhouette_mask_path)

        for run_id in range(1, runs_per_case + 1):
            print(f"[{case_idx+1}/{len(cases)}] Running {payload.caseId} (style: {payload.targetStyle}, type: {payload.inputType})...", flush=True)
            # 2. Local conditioning control map
            local_control_path = target_dir / f"controlmap-{payload.caseId}-run{run_id}.png"
            generate_control_map(
                image_source=normalized_image,
                output_path=str(local_control_path),
                input_type=payload.inputType,
            )

            # 3. Call real provider
            render_result = adapter.run(
                payload=payload,
                overrides=replicate_overrides,
                run_id=run_id,
                local_control_map_path=str(local_control_path),
            )
            print(f"  -> Generated in {render_result.latencyMs} ms. Output: {render_result.outputImageUrl[:60]}...", flush=True)

            # 4. Download and cache output image
            output_bytes = fetch_image_bytes(render_result.outputImageUrl)
            output_path = target_dir / f"output-{payload.caseId}-run{run_id}.png"
            output_path.write_bytes(output_bytes)
            output_sha256 = hashlib.sha256(output_bytes).hexdigest()

            # 5. Persist debug control map & binary mask
            control_mask_path = target_dir / f"controlmap-mask-{payload.caseId}-run{run_id}.png"
            if render_result.debugControlMapUrl.startswith("http"):
                control_bytes = fetch_image_bytes(render_result.debugControlMapUrl)
                local_control_path.write_bytes(control_bytes)
            save_control_map_and_mask(local_control_path, local_control_path, control_mask_path)

            # 6. Compute silhouette IoU
            iou = compute_iou(silhouette_mask_path, control_mask_path)
            passed = iou >= iou_threshold

            run_entry = {
                "caseId": payload.caseId,
                "runId": run_id,
                "inputType": payload.inputType,
                "targetStyle": payload.targetStyle,
                "provider": render_result.provider,
                "modelId": render_result.modelId,
                "seed": render_result.seed,
                "overrides": replicate_overrides or {},
                "latencyMs": render_result.latencyMs,
                "outputImagePath": str(output_path),
                "outputImageUrl": render_result.outputImageUrl,
                "controlMapPath": str(local_control_path),
                "controlMapMaskPath": str(control_mask_path),
                "silhouetteMaskPath": str(silhouette_mask_path),
                "imageHash_SHA256": output_sha256,
                "iou": round(iou, 4),
                "iouThreshold": iou_threshold,
                "passed": passed,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            runs.append(run_entry)

    # Summary metrics
    latencies = sorted([r["latencyMs"] for r in runs])
    failed_runs = [r for r in runs if not r["passed"]]
    summary = {
        "totalCases": len(cases),
        "runsPerCase": runs_per_case,
        "totalRuns": len(runs),
        "successRuns": len(runs) - len(failed_runs),
        "failedRuns": len(failed_runs),
        "iouThreshold": iou_threshold,
        "p50LatencyMs": percentile(latencies, 0.5),
        "p95LatencyMs": percentile(latencies, 0.95),
        "latenciesMs": latencies,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }

    # Write summary artifacts
    (target_dir / "runs.json").write_text(json.dumps(runs, indent=2))
    (target_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    readme_content = (
        f"ControlNet Real Provider Evaluation Run\n"
        f"Timestamp: {timestamp}\n"
        f"Provider: {provider}\n"
        f"Cases: {len(cases)}, Total Runs: {len(runs)}\n"
        f"Success: {summary['successRuns']}, Failed: {summary['failedRuns']}\n"
        f"P50 Latency: {summary['p50LatencyMs']} ms, P95: {summary['p95LatencyMs']} ms\n"
        f"IoU Threshold: {iou_threshold}\n"
    )
    (target_dir / "README.txt").write_text(readme_content)

    # Write implementation report if example run exists
    example_run = runs[0] if runs else None
    implementation_report = {
        "files_added": [
            "src/pipeline/replicate_adapter.py",
            "src/pipeline/controlnet_utils.py",
            "src/pipeline/image_io.py",
            "src/pipeline/evaluation_executor.py",
            "src/pipeline/debug_map.py",
            "tools/iou_checker.py",
            "scripts/run_controlnet_validation.py",
            "tests/test_replicate_adapter.py",
            "tests/test_evaluation_executor_integration.py",
            "tests/fixtures/cases.json",
            "tests/fixtures/cases_fast.json",
            "docs/CONTROLNET_INTEGRATION.md",
            ".github/workflows/ci.yml",
        ],
        "files_modified": [
            "src/visualization.py",
            "pyproject.toml",
        ],
        "tests_added": [
            "tests/test_replicate_adapter.py",
            "tests/test_evaluation_executor_integration.py",
        ],
        "ci_changes": "Added GitHub Actions workflow .github/workflows/ci.yml with real_provider gate and artifact upload",
        "example_run": (
            {
                "caseId": example_run["caseId"],
                "seed": example_run["seed"],
                "modelId": example_run["modelId"],
                "latencyMs": example_run["latencyMs"],
                "outputImagePath": example_run["outputImagePath"],
                "controlMapPath": example_run["controlMapPath"],
                "iou": example_run["iou"],
            }
            if example_run
            else None
        ),
    }
    (target_dir / "implementation-report.json").write_text(
        json.dumps(implementation_report, indent=2)
    )

    if failed_runs:
        raise RuntimeError(
            f"Evaluation IoU gating failed: {len(failed_runs)}/{len(runs)} runs below threshold {iou_threshold}."
        )

    return {"artifactDir": str(target_dir), "runs": runs, "summary": summary}


def execute_fast(cases, provider="replicate", runs_per_case=1, replicateOverrides=None):
    """Alias for fast execution compatible with validation scripts."""
    return execute_evaluation(
        cases=cases,
        provider=provider,
        runs_per_case=runs_per_case,
        replicate_overrides=replicateOverrides,
    )


def main():
    parser = argparse.ArgumentParser(description="Run ControlNet evaluation pipeline against real provider.")
    parser.add_argument("--cases", default="tests/fixtures/cases.json", help="Path to JSON test cases file.")
    parser.add_argument("--provider", default="replicate", help="Model provider (must be 'replicate').")
    parser.add_argument("--runs-per-case", type=int, default=1, help="Number of runs per case.")
    parser.add_argument("--output-dir", default=None, help="Optional output directory for artifacts.")
    args = parser.parse_args()

    cases_path = Path(args.cases)
    if not cases_path.is_file():
        # Try resolving relative to workspace root
        cases_path = Path(__file__).resolve().parents[2] / args.cases

    if not cases_path.is_file():
        print(f"Error: cases file not found at {args.cases}", file=sys.stderr)
        return 1

    with open(cases_path) as f:
        cases_data = json.load(f)

    try:
        result = execute_evaluation(
            cases=cases_data,
            provider=args.provider,
            runs_per_case=args.runs_per_case,
            output_dir=args.output_dir,
        )
        print(f"Evaluation completed successfully! Artifacts written to: {result['artifactDir']}")
        return 0
    except Exception as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())