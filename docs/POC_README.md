# Pre-Feasibility Engine (`pf-engine`) Local POC & REST API

This document describes the architecture, setup, configuration, and API contract for the **Pre-Feasibility Engine (`pf-engine`)** backend microservice.

---

## 1. Architectural Overview

`pf-engine` provides a high-performance, containerized backend API that decouples front-end user interfaces from the computational and generative engines:

```
┌────────────────────────────────────────────────────────┐
│                   Front-End Client                     │
│       (React/Vite, Next.js, Mobile Web, A-Frame VR)    │
└───────────────────────────┬────────────────────────────┘
                            │ REST API (JSON / Webhooks)
                            ▼
┌────────────────────────────────────────────────────────┐
│           FastAPI REST Service (src/api/app.py)        │
│  - POST /api/v1/submit        - GET /api/v1/status/{id}│
│  - POST /api/v1/replay        - GET /api/v1/artifacts  │
│  - POST /api/v1/cad/feasibility - GET /health          │
└───────────────────────────┬────────────────────────────┘
                            │ In-Process Worker Queue
                            ▼
┌────────────────────────────────────────────────────────┐
│             Job Manager (ThreadPoolExecutor)           │
├────────────────────────────┬───────────────────────────┤
│ Deterministic CAD-to-BOM   │ Spatially-Locked Gen-AI   │
│ - DXF Entity Parser        │ - SDXL Depth & Canny API  │
│ - Semantic Room Classifier │ - IoU Silhouette Gating   │
│ - Material Catalog Presets │ - SHA-256 Hash History    │
│ - BOM Cost Calculation     │ - Deterministic Replay    │
└────────────────────────────┴───────────────────────────┘
```

---

## 2. API Contract & Endpoints

Base URL: `http://localhost:8000`

### 1. Health & Readiness
`GET /health` or `GET /api/v1/health`

**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "service": "pf-engine",
  "replicateTokenConfigured": true,
  "replicateDepthModel": "lucataco/sdxl-controlnet-depth:465fb417...",
  "replicateCannyModel": "jagilley/controlnet-canny:aff48af9...",
  "dryRunDefault": false,
  "activeWorkers": 2,
  "pendingJobs": 0,
  "completedJobs": 12
}
```

---

### 2. Submit Restyling Case
`POST /api/v1/submit`

**Payload:**
```json
{
  "caseId": "interior-villa-001",
  "inputType": "interior",
  "targetStyle": "tropical-boutique",
  "localImagePath": "tests/fixtures/sample_interior.png",
  "overrides": {
    "guidanceScale": 6.0,
    "controlnetConditioningScale": 0.80
  },
  "runsPerCase": 1,
  "warmup": false,
  "dryRun": false
}
```

**Response (`202 Accepted`):**
```json
{
  "runId": "run_interior-villa-001_20260903T113000Z",
  "status": "queued",
  "message": "Case 'interior-villa-001' submitted successfully to background worker queue.",
  "createdAt": "2026-09-03T11:30:00.123456+00:00"
}
```

---

### 3. Poll Job Status & Verification Metrics
`GET /api/v1/status/{runId}`

**Response:**
```json
{
  "runId": "run_interior-villa-001_20260903T113000Z",
  "status": "done",
  "progress": 1.0,
  "latencyMs": 8958.0,
  "iou": 1.0,
  "tier": "pass",
  "imageHash_SHA256": "903ab350bae6c06cbffe15ec1034e8a5a4603b31f4d1d87f165ec4213d9c6d46",
  "seed": 860060717,
  "error": null,
  "logs": [
    "[11:30:00] Job queued successfully.",
    "[11:30:01] Starting real ControlNet run against Replicate for case: interior-villa-001",
    "[11:30:09] Execution completed successfully. (IoU=1.0, Latency=8958.0ms)"
  ],
  "artifactPaths": {
    "output-interior-villa-001-run1.png": "/api/v1/artifacts/run_interior-villa-001_20260903T113000Z/file/output-interior-villa-001-run1.png",
    "controlmap-interior-villa-001-run1.png": "/api/v1/artifacts/run_interior-villa-001_20260903T113000Z/file/controlmap-interior-villa-001-run1.png",
    "runs.json": "/api/v1/artifacts/run_interior-villa-001_20260903T113000Z/file/runs.json"
  },
  "createdAt": "2026-09-03T11:30:00.123456+00:00",
  "updatedAt": "2026-09-03T11:30:09.654321+00:00"
}
```

---

### 4. Download Artifacts Bundle
`GET /api/v1/artifacts/{runId}?download=zip`

Streams a compressed `.zip` archive containing the generated render, control edge/depth maps, silhouette masks, sanitized JSON payloads, and summary metadata.

---

### 5. Deterministic Replay
`POST /api/v1/replay`

**Payload:**
```json
{
  "runId": "run_interior-villa-001_20260903T113000Z"
}
```

---

### 6. End-to-End CAD Pre-Feasibility
`POST /api/v1/cad/feasibility`

**Payload:**
```json
{
  "dxfPath": "simple_room.dxf",
  "preset": "Luxury Minimal",
  "targetStyle": "luxury-minimal",
  "dryRun": false
}
```

Executes:
1. DXF parsing via `ezdxf`
2. Semantic room classification & ray-casting boundary polygon stitching
3. BOM material catalog assignment & pricing
4. 2D SVG floorplan generation
5. ControlNet visual style synthesis

---

## 3. Quickstart & Local Execution

### Option A: Local Poetry Environment
```bash
# 1. Install dependencies
poetry install

# 2. Configure environment
cp .env.local.example .env.local
# Edit .env.local with your REPLICATE_API_TOKEN

# 3. Launch API server
poetry run uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Option B: Docker Containerization
```bash
# Build and run container with docker-compose
docker compose up --build -d

# Check logs
docker compose logs -f

# Verify health
curl -s http://localhost:8000/health | jq
```

---

## 4. Front-End Integration Guidelines

Front-end teams (React, Vite, Vue, Next.js) can connect directly to `pf-engine`:

1. **Submit Job**: Call `POST /api/v1/submit` with chosen image / sketch and style preset.
2. **Poll Status**: Poll `GET /api/v1/status/{runId}` every 1–2 seconds to show a loading spinner and log messages.
3. **Display Output**: When `status === "done"`, render `output-*.png` and compare against the `controlmap-*.png` overlay.
4. **Offline Development**: Set `"dryRun": true` or env `DRY_RUN=1` in the payload to build and test UI flows without consuming provider credits.
