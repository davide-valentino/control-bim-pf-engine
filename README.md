# Pre-Feasibility Engine (`control-bim-pf-engine`)

[![CI](https://github.com/davide-valentino/control-bim-pf-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/davide-valentino/control-bim-pf-engine/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)

**Pre-Feasibility Engine (`control-bim-pf-engine`)** is a high-performance backend microservice combining **deterministic CAD-to-BOM costing** with **spatially-locked ControlNet generative restyling**. 

It enables property developers, local Indonesian architects, and international investors to convert 2D CAD floorplans or site sketches into photorealistic, structurally validated architectural concepts and preliminary financial estimates in seconds.

---

## 🚀 Key Features

* **Deterministic CAD-to-BOM Engine**: Ingests `.dxf` drawings, automatically extracts walls and openings, performs ray-casting room classification, and computes a Bill of Materials (BOM) with explicit, auditable quantity rules — wall area = room perimeter × wall height, floor area = room boundary area, doors = clustered opening units, windows = opening width × assumed height. Material presets (*Luxury Minimal*, *Tropical-Boutique*, *Rustic*) supply rates that carry `currency`, `as_of`, and `source` metadata so placeholder numbers can never be mistaken for real firm rates.
* **Spatially-Locked Generative Restyling**: SDXL Depth and Canny ControlNet conditioning with automated **silhouette IoU gating of the rendered output** (`IOU_THRESHOLD`, default 0.85). The gate compares the input silhouette against the binarized composition of the generated image; the legacy input-vs-control-map score is retained as a `conditioningIou` diagnostic. See *Known limitations* below.
* **Reproducible & Replayable**: Full SHA-256 hash tracking and seed recording guarantee bit-for-bit identical reproduction across design revisions.
* **REST API & Job Queue**: Lightweight FastAPI service with an in-process thread pool queue, status polling, and zip artifact packaging for easy handoff to front-end teams (React, Vite, Next.js).
* **Docker Containerized**: One-command reproducible local and cloud deployment.

---

## 📦 Quickstart

### Option 1: Docker (Recommended)
```bash
# 1. Clone repository
git clone git@github.com:davide-valentino/control-bim-pf-engine.git
cd control-bim-pf-engine

# 2. Configure credentials
cp .env.local.example .env.local
# Add your REPLICATE_API_TOKEN to .env.local

# 3. Start API service
docker compose up --build -d

# 4. View interactive Swagger documentation
open http://localhost:8000/docs
```

### Option 2: Local Python & Poetry
```bash
# Install dependencies
poetry install

# Run tests (hermetic: each pipeline test builds its own .output/ workspace)
poetry run pytest -q

# Start API server
poetry run python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

---

## ⚠️ Known Limitations & Data Provenance

* **Rates are placeholders.** `src/pipeline/presets.json` contains benchmark numbers, **not** the partner firm's Indonesian rate sheet. The BOM output labels them via `rate_source` ("placeholder benchmark rates - NOT partner-firm rates"), `currency`, and `as_of`. Replace the preset values (or the `metadata` block) with the firm's IDR rates before quoting any client.
* **Wall area is a gross approximation.** Walls are priced as room perimeter × wall height, so shared partition walls are counted once per adjoining room. No deduction for openings, structure, or finishes.
* **Openings need layer separation for window pricing.** The parser clusters opening segments into units, but door/window classification relies on layer names (`door`/`pintu` vs `window`/`jendela`). Drawings that place both on a single layer (e.g. `DOOR___WINDOW`) are priced entirely as doors.
* **Room seeding uses drawing text.** Annotation text inside a closed polygon can be picked up as a room label; plans with many notes may produce annotation-named "rooms".
* **IoU gating is a coarse proxy.** The gate measures binarized composition overlap between the input silhouette and the rendered output — it detects gross scene drift, not semantic geometry fidelity. A learned structural metric (e.g. depth-map consistency) would be stronger.

---

## 🔌 API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health, worker pool stats, and provider readiness |
| `POST` | `/api/v1/submit` | Queue a visual restyling / evaluation case |
| `GET` | `/api/v1/status/{runId}` | Poll job progress, IoU score, latency, and output hash |
| `GET` | `/api/v1/artifacts/{runId}` | List artifact links or download `.zip` bundle |
| `GET` | `/api/v1/artifacts/{runId}/file/{file}` | Preview or stream image/JSON/SVG artifact |
| `POST` | `/api/v1/replay` | Deterministically replay previous run by seed |
| `POST` | `/api/v1/cad/feasibility` | End-to-end DXF to BOM costing + ControlNet render |
| `POST` | `/api/v1/cad/feasibility/upload` | Multipart DXF upload -> end-to-end pre-feasibility job |

---

## 🧪 Interactive Demo Scripts

```bash
# Submit and poll an interior restyling job (offline dry-run)
./scripts/demo_submit.sh interior-villa-001 interior tropical-boutique true

# Submit and poll full DXF to BOM pre-feasibility pipeline
./scripts/demo_cad_feasibility.sh simple_room.dxf "Luxury Minimal" luxury-minimal true
```

---

## Example runs with curl requests

Create a new CAD feasibility run:

```sh
curl -X POST "http://localhost:8000/api/v1/cad/feasibility" \
  -H "Content-Type: application/json" \
  -d '{
    "preset": "Luxury Minimal",
    "targetStyle": "tropical-boutique",
    "dxfPath": "RUMAH_RENOV.dxf",
    "overrides": {
      "seed": 424242,
      "guidance_scale": 7.5,
      "numInferenceSteps": 30
    },
    "dryRun": false
  }'
```

Check the status of the run using the returned `runId`:

```sh
curl "http://localhost:8000/api/v1/status/{runId}"
```

---

## 📚 Documentation
* [REST API & POC Runbook](docs/POC_README.md)
* [ControlNet Evaluation & Gating Guide](docs/CONTROLNET_INTEGRATION.md)
* [CAD-to-BOM Pipeline Architecture](docs/pipeline.md)
* [Front-End React Integration Stub](docs/FRONTEND_STUB.md)

---

## 📄 License
MIT
