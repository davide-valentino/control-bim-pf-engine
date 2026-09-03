"""Evaluation executor orchestrating real ControlNet runs, artifact saving, and IoU gating."""
import argparse
import base64
import hashlib
import io
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
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


def calculate_stats(values: list[float | int]) -> dict[str, float]:
    """Compute summary statistics for a numeric sequence."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0}
    n = len(values)
    mean_val = sum(values) / n
    variance = sum((x - mean_val) ** 2 for x in values) / n if n > 0 else 0.0
    stddev_val = math.sqrt(variance)
    sorted_vals = sorted(values)
    return {
        "mean": round(mean_val, 4),
        "stddev": round(stddev_val, 4),
        "min": round(float(min(values)), 4),
        "max": round(float(max(values)), 4),
        "p50": round(percentile(sorted_vals, 0.5), 4),
        "p95": round(percentile(sorted_vals, 0.95), 4),
    }


def execute_evaluation(
    cases: list[dict | EvalPayload],
    provider: str = "replicate",
    runs_per_case: int = 1,
    replicate_overrides: dict | None = None,
    output_dir: str | Path | None = None,
    warmup: bool = False,
    iou_threshold: float | None = None,
    iou_warn_threshold: float | None = None,
    latency_budget_ms: float | None = None,
) -> dict:
    """Run real ControlNet evaluation across test cases and persist artifacts."""
    if provider != "replicate":
        raise ValueError(
            f"Unsupported provider '{provider}'. Only the real 'replicate' provider is supported; "
            "no mocks or fallback are allowed."
        )

    if runs_per_case < 1 or runs_per_case > 10:
        raise ValueError(f"runs_per_case must be between 1 and 10, got {runs_per_case}")

    if iou_threshold is None:
        iou_threshold = float(os.getenv("IOU_THRESHOLD", "0.85"))
    if iou_warn_threshold is None:
        iou_warn_threshold = float(os.getenv("IOU_WARN_THRESHOLD", "0.90"))
    if latency_budget_ms is None:
        latency_budget_str = os.getenv("LATENCY_BUDGET_MS", "")
        latency_budget_ms = float(latency_budget_str) if latency_budget_str else None

    # Check env var for warmup override
    if not warmup and os.getenv("WARMUP_PROBE", "").lower() in ("1", "true", "yes"):
        warmup = True

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if output_dir is None:
        target_dir = Path("artifacts/evaluations") / timestamp
    else:
        target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    adapter = ReplicateAdapter(artifact_dir=str(target_dir))
    runs = []
    warnings_list = []

    # Optional warm-up probe
    warmup_latencies: dict[str, int] = {}
    if warmup and len(cases) > 0:
        input_types = {c.get("inputType") if isinstance(c, dict) else c.inputType for c in cases}
        print(f"[Evaluation] Running warm-up probe for input types: {sorted(input_types)}...", flush=True)
        warmup_latencies = adapter.warmup_models(input_types)

    for case_idx, case_data in enumerate(cases):
        payload = case_data if isinstance(case_data, EvalPayload) else EvalPayload(**case_data)
        normalized_image = normalize_source(payload.imageUrl, payload.localImagePath)

        # 1. Deterministic silhouette mask
        silhouette_mask_path = target_dir / f"silhouette-mask-{payload.caseId}.png"
        silhouette_source = payload.silhouettePath or payload.localImagePath or normalized_image
        save_binary_mask(silhouette_source, silhouette_mask_path)

        for run_id in range(1, runs_per_case + 1):
            print(f"[{case_idx+1}/{len(cases)}] Running {payload.caseId} (run {run_id}/{runs_per_case}, style: {payload.targetStyle}, type: {payload.inputType})...", flush=True)
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
            
            # Tiered gating status
            run_warning = None
            if iou < iou_threshold:
                run_status = "fail"
                passed = False
                run_warning = f"IoU {iou:.4f} is below minimum threshold {iou_threshold:.4f}"
            elif iou < iou_warn_threshold:
                run_status = "warn"
                passed = True
                run_warning = f"IoU {iou:.4f} is below warning threshold {iou_warn_threshold:.4f}"
            else:
                run_status = "pass"
                passed = True

            if run_warning:
                warnings_list.append(f"Case {payload.caseId} run {run_id}: {run_warning}")

            run_entry = {
                "caseId": payload.caseId,
                "runId": run_id,
                "inputType": payload.inputType,
                "targetStyle": payload.targetStyle,
                "localImagePath": payload.localImagePath,
                "imageUrl": payload.imageUrl,
                "silhouettePath": payload.silhouettePath,
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
                "iouWarnThreshold": iou_warn_threshold,
                "status": run_status,
                "warning": run_warning,
                "passed": passed,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            runs.append(run_entry)

    # Per-case aggregation statistics
    case_stats: dict[str, dict] = {}
    for case_data in cases:
        c_id = case_data.get("caseId") if isinstance(case_data, dict) else case_data.caseId
        case_runs = [r for r in runs if r["caseId"] == c_id]
        if case_runs:
            c_ious = [r["iou"] for r in case_runs]
            c_latencies = [r["latencyMs"] for r in case_runs]
            iou_stat = calculate_stats(c_ious)
            lat_stat = calculate_stats(c_latencies)
            case_stats[c_id] = {
                "runs": len(case_runs),
                "passed": all(r["passed"] for r in case_runs),
                "meanIoU": iou_stat["mean"],
                "stdDevIoU": iou_stat["stddev"],
                "minIoU": iou_stat["min"],
                "maxIoU": iou_stat["max"],
                "meanLatencyMs": lat_stat["mean"],
                "stdDevLatencyMs": lat_stat["stddev"],
                "p50LatencyMs": lat_stat["p50"],
                "p95LatencyMs": lat_stat["p95"],
            }

    # Summary metrics across all measured runs
    latencies = sorted([r["latencyMs"] for r in runs])
    ious = [r["iou"] for r in runs]
    lat_stats = calculate_stats(latencies)
    iou_stats = calculate_stats(ious)

    failed_runs = [r for r in runs if not r["passed"]]
    warning_runs = [r for r in runs if r["status"] == "warn"]
    pass_clean_runs = [r for r in runs if r["status"] == "pass"]

    # Latency budget evaluation
    if latency_budget_ms is not None and lat_stats["p95"] > latency_budget_ms:
        budget_warn = f"P95 latency {lat_stats['p95']} ms exceeded budget of {latency_budget_ms} ms"
        warnings_list.append(budget_warn)

    gating_result = "FAIL" if failed_runs else ("WARN" if warning_runs else "PASS")

    summary = {
        "totalCases": len(cases),
        "runsPerCase": runs_per_case,
        "totalRuns": len(runs),
        "successRuns": len(runs) - len(failed_runs),
        "passedRuns": len(pass_clean_runs),
        "warningRuns": len(warning_runs),
        "failedRuns": len(failed_runs),
        "gatingResult": gating_result,
        "iouThreshold": iou_threshold,
        "iouWarnThreshold": iou_warn_threshold,
        "latencyBudgetMs": latency_budget_ms,
        "meanIoU": iou_stats["mean"],
        "stdDevIoU": iou_stats["stddev"],
        "minIoU": iou_stats["min"],
        "maxIoU": iou_stats["max"],
        "warmupEnabled": warmup,
        "warmupLatenciesMs": warmup_latencies,
        "p50LatencyMs": lat_stats["p50"],
        "p95LatencyMs": lat_stats["p95"],
        "meanLatencyMs": lat_stats["mean"],
        "stdDevLatencyMs": lat_stats["stddev"],
        "minLatencyMs": lat_stats["min"],
        "maxLatencyMs": lat_stats["max"],
        "measuredLatenciesMs": latencies,
        "caseStats": case_stats,
        "warnings": warnings_list,
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
        f"Gating Result: {gating_result}\n"
        f"Pass (Clean): {summary['passedRuns']}, Warn: {summary['warningRuns']}, Fail: {summary['failedRuns']}\n"
        f"Mean IoU: {summary['meanIoU']:.4f} (std: {summary['stdDevIoU']:.4f}, min: {summary['minIoU']:.4f}, max: {summary['maxIoU']:.4f})\n"
        f"Measured P50 Latency: {summary['p50LatencyMs']} ms, P95: {summary['p95LatencyMs']} ms, Mean: {summary['meanLatencyMs']} ms\n"
        f"Warmup Enabled: {warmup} (Warmup Latencies: {warmup_latencies})\n"
        f"IoU Threshold: {iou_threshold} (Warn: {iou_warn_threshold})\n"
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
            "tests/fixtures/cases_style_sweep.json",
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
                "status": example_run["status"],
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


def replay_run(
    run_spec: dict | str | Path,
    provider: str = "replicate",
    output_dir: str | Path | None = None,
) -> dict:
    """Re-run a saved execution payload deterministically to verify reproducibility."""
    if isinstance(run_spec, (str, Path)):
        spec_path = Path(run_spec)
        with open(spec_path) as f:
            raw_data = json.load(f)
        if isinstance(raw_data, list):
            run_data = raw_data[0]
        else:
            run_data = raw_data
    else:
        run_data = run_spec

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_dir = Path(output_dir) if output_dir else Path("artifacts/replays") / timestamp
    target_dir.mkdir(parents=True, exist_ok=True)

    adapter = ReplicateAdapter(artifact_dir=str(target_dir))
    case_id = run_data.get("caseId", "replay-case")
    input_type = run_data.get("inputType", "interior")
    target_style = run_data.get("targetStyle", "midrange-modern")
    seed = run_data.get("seed")
    overrides = dict(run_data.get("overrides", {}))
    if seed is not None:
        overrides["seed"] = seed

    # Resolve image source with fallback for older runs
    img_path = (
        run_data.get("localImagePath")
        or run_data.get("imageUrl")
        or run_data.get("silhouettePath")
        or run_data.get("silhouetteMaskPath")
        or f"tests/fixtures/sample_{input_type}.png"
    )

    payload = EvalPayload(
        caseId=f"replay-{case_id}",
        inputType=input_type,
        targetStyle=target_style,
        localImagePath=img_path if not str(img_path).startswith("http") else None,
        imageUrl=img_path if str(img_path).startswith("http") else None,
        silhouettePath=run_data.get("silhouetteMaskPath") or run_data.get("silhouettePath"),
    )

    # Execute replay run
    res = adapter.run(payload=payload, overrides=overrides, run_id=1)
    output_bytes = fetch_image_bytes(res.outputImageUrl)
    output_path = target_dir / f"replay-output-{case_id}.png"
    output_path.write_bytes(output_bytes)
    replay_sha256 = hashlib.sha256(output_bytes).hexdigest()

    original_sha256 = run_data.get("imageHash_SHA256")
    hash_matched = (replay_sha256 == original_sha256) if original_sha256 else None

    replay_result = {
        "caseId": case_id,
        "seed": res.seed,
        "modelId": res.modelId,
        "originalHash": original_sha256,
        "replayHash": replay_sha256,
        "hashMatched": hash_matched,
        "latencyMs": res.latencyMs,
        "outputImageUrl": res.outputImageUrl,
        "outputImagePath": str(output_path),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    (target_dir / "replay-result.json").write_text(json.dumps(replay_result, indent=2))
    return replay_result


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
    parser.add_argument("--warmup", action="store_true", help="Run a warmup probe before timed runs.")
    parser.add_argument("--iou-threshold", type=float, default=None, help="Hard failure threshold for silhouette IoU.")
    parser.add_argument("--iou-warn-threshold", type=float, default=None, help="Warning threshold for silhouette IoU.")
    parser.add_argument("--latency-budget-ms", type=float, default=None, help="Latency budget in ms.")
    parser.add_argument("--replay", default=None, help="Path to runs.json or run spec to replay deterministically.")
    parser.add_argument("--output-dir", default=None, help="Optional output directory for artifacts.")
    args = parser.parse_args()

    if args.replay:
        print(f"Executing deterministic replay for spec: {args.replay}...", flush=True)
        res = replay_run(args.replay, provider=args.provider, output_dir=args.output_dir)
        print(f"Replay finished! Matched original: {res['hashMatched']} (Hash: {res['replayHash']})")
        return 0

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
            warmup=args.warmup,
            iou_threshold=args.iou_threshold,
            iou_warn_threshold=args.iou_warn_threshold,
            latency_budget_ms=args.latency_budget_ms,
        )
        print(f"Evaluation completed successfully! Artifacts written to: {result['artifactDir']}")
        return 0
    except Exception as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())