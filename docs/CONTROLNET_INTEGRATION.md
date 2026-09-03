# Deterministic ControlNet Evaluation Path (`pf-engine`)

This document describes the architecture, setup, configuration, and execution of the deterministic ControlNet evaluation path in `pf-engine`.

---

## 1. Overview & Architecture

The ControlNet evaluation path enables automated, deterministic visual rendering and structural verification of CAD/BIM assets:

```
simple_room.dxf / CAD Input
            │
            ▼
 1. Parser & Semantics (raw_geometry.json -> semantic.json)
            │
            ▼
 2. Visualization (SVG -> Silhouette Mask PNG via CairoSVG)
            │
            ▼
 3. Local Conditioning & Debug Map Generation (Canny / Depth / Structural Boundary)
            │
            ▼
 4. Strict Real Provider Execution (Replicate API, No Mocks/Fallback)
            │
            ▼
 5. Artifact Persistence (artifacts/evaluations/<timestamp>/)
      - output-<caseId>-run<runId>.png
      - controlmap-<caseId>-run<runId>.png
      - controlmap-mask-<caseId>-run<runId>.png
      - silhouette-mask-<caseId>.png
      - payload-<caseId>-run<runId>.json (sanitized)
      - runs.json, summary.json, README.txt, implementation-report.json
            │
            ▼
 6. Silhouette IoU Gating (IoU >= IOU_THRESHOLD, default 0.85)
```

---

## 2. Environment Variables & Credentials

| Variable | Required | Default | Description |
|---|---|---|---|
| `REPLICATE_API_TOKEN` | Yes (for real runs) | None | Replicate API authentication token (fail fast if missing). |
| `REPLICATE_CONTROLNET_DEPTH_MODEL` | No | `lucataco/sdxl-controlnet-depth:465fb41789dc2203a9d7158be11d1d2570606a039c65e0e236fd329b5eecb10c` | Model identifier for interior depth restyling. |
| `REPLICATE_CONTROLNET_CANNY_MODEL` | No | `jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613` | Model identifier for floorplans and Canny edges. |
| `REPLICATE_CONTROLNET_FACADE_MODEL` | No | `jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613` | Model identifier for building facades. |
| `IOU_THRESHOLD` | No | `0.85` | Hard failure threshold for silhouette IoU. |
| `IOU_WARN_THRESHOLD` | No | `0.90` | Warning threshold for silhouette IoU in tiered gating. |
| `LATENCY_BUDGET_MS` | No | None | Optional P95 latency budget in milliseconds. |
| `WARMUP_PROBE` | No | `0` | Set to `1` to run a model warm-up probe before timed evaluation runs. |
| `MAX_DATA_URL_SIZE_BYTES` | No | `5000000` (5 MB) | Maximum size for inline base64 data URLs before failing. |

---

## 3. Parameter Ranges & Best Practices

- **`controlnetConditioningScale`**: `0.0` to `2.0` (validated optimal operating range: `0.75`–`0.90`, default `0.80`).
- **`guidanceScale`**: `1.0` to `20.0` (recommended default: `6.0`).
- **`numInferenceSteps`**: `10` to `80` (recommended default: `30`–`40`).
- **`lowThreshold`**: `1` to `255` (recommended default: `50` for facades/interiors, `100` for floorplans).
- **`highThreshold`**: `1` to `255` (recommended default: `150` for facades/interiors, `200` for floorplans).
- **`seed`**: `1` to `2147483647` (recorded in metadata for deterministic reproduction).

---

## 4. Running Evaluations

### Fast Validation Smoke Test (Single Case)
```bash
python scripts/run_controlnet_validation.py --cases tests/fixtures/cases_fast.json
```

### Curated 3-Case Stability Sweep with Warmup Probe
```bash
poetry run python -m src.pipeline.evaluation_executor --cases cases.json --provider replicate --runs-per-case 3 --warmup
```

### Full 12-Case Multi-Style Sweep
```bash
poetry run python -m src.pipeline.evaluation_executor --cases tests/fixtures/cases_style_sweep.json --provider replicate --runs-per-case 1 --warmup
```

### Deterministic Replay Verification
```bash
poetry run python -m src.pipeline.evaluation_executor --replay artifacts/evaluations/20260903T105438Z/runs.json
```

### Direct Terminal Python Execution Snippet
```python
import os, json
from src.pipeline.evaluation_executor import execute_evaluation

cases = [
    {
        "caseId": "quick-test-001",
        "inputType": "interior",
        "targetStyle": "luxury-minimal",
        "localImagePath": "tests/fixtures/sample_interior.png",
        "silhouettePath": "tests/fixtures/sample_interior.png"
    }
]

result = execute_evaluation(cases=cases, provider="replicate", runs_per_case=1, warmup=True)
print(json.dumps(result["summary"], indent=2))
```

### Running Test Suite
```bash
# Run full unit and offline test suite
poetry run pytest -q

# Run real provider integration tests (requires REPLICATE_API_TOKEN)
set -a && source .env.local && set +a
poetry run pytest -q -m real_provider
```

---

## 5. Artifact Directory Layout

Every evaluation run creates a self-contained directory under `artifacts/evaluations/<timestamp>/`:

- **`output-<caseId>-run<runId>.png`**: Full rendered output image downloaded from provider.
- **`controlmap-<caseId>-run<runId>.png`**: Canonical conditioning control map used for structural guidance.
- **`controlmap-mask-<caseId>-run<runId>.png`**: Thresholded binary mask of the control map.
- **`silhouette-mask-<caseId>.png`**: Ground-truth binary silhouette mask exported from CAD/SVG.
- **`payload-<caseId>-run<runId>.json`**: Sanitized provider payload for exact auditability.
- **`runs.json`**: Detailed array of run records including `seed`, `latencyMs`, `imageHash_SHA256`, `iou`, and pass/fail status.
- **`summary.json`**: Aggregate statistics including total runs, success/failure counts, and P50/P95 latencies.
- **`implementation-report.json`**: Deliverables summary for validation and compliance.
- **`README.txt`**: Human-readable run summary.

---

## 6. Strict Failure Semantics

- **No Mocks or Fallbacks**: Evaluation runs communicate directly with the live provider. If API tokens, model identifiers, or network connections fail, the run immediately terminates with a non-zero exit code.
- **IoU Gating**: If any run generates an IoU below `IOU_THRESHOLD`, the run is marked failed and the evaluation process exits non-zero.
