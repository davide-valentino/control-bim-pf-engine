"""FastAPI application for the Pre-Feasibility Engine (control-bim-pf-engine) backend service."""
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

from src.api.auth import verify_api_key
from src.api.job_manager import JobManager
from src.api.schemas import (
    ArtifactItem,
    ArtifactListResponse,
    CadFeasibilityRequest,
    HealthResponse,
    ReplayRequest,
    RunStatusResponse,
    SubmitCaseRequest,
    SubmitResponse,
)

# Initialize FastAPI application
app = FastAPI(
    title="Pre-Feasibility Engine (control-bim-pf-engine) API",
    description="Deterministic CAD-to-BOM costing & ControlNet visual restyling microservice.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for front-end clients (React/Vite, Vue, Next.js, mobile web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Job Manager singleton
job_manager = JobManager(max_workers=2, artifacts_root="artifacts")


@app.get("/", response_class=HTMLResponse, tags=["General"])
def index():
    """Interactive landing page and quick developer dashboard."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Pre-Feasibility Engine (control-bim-pf-engine)</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 860px; margin: 40px auto; padding: 20px; line-height: 1.6; color: #1e293b; background: #f8fafc; }
            h1 { color: #0f172a; margin-bottom: 4px; }
            .badge { display: inline-block; background: #0284c7; color: white; padding: 2px 8px; border-radius: 4px; font-size: 13px; font-weight: 600; margin-bottom: 20px; }
            .card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            a { color: #0284c7; text-decoration: none; font-weight: 500; }
            a:hover { text-decoration: underline; }
            code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 14px; }
            pre { background: #0f172a; color: #f8fafc; padding: 14px; border-radius: 6px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>Pre-Feasibility Engine API</h1>
        <div class="badge">control-bim-pf-engine v0.1.0 • Ready</div>
        <div class="card">
            <h3>Overview</h3>
            <p>High-performance backend engine unifying <strong>deterministic CAD-to-BOM costing</strong> with <strong>spatially-locked ControlNet generative restyling</strong>.</p>
            <p>Explore the interactive Swagger documentation: <a href="/docs">/docs</a> or ReDoc: <a href="/redoc">/redoc</a></p>
        </div>
        <div class="card">
            <h3>Core Endpoints</h3>
            <ul>
                <li><code>POST /api/v1/submit</code> - Submit interior, facade, or floorplan case</li>
                <li><code>GET /api/v1/status/{runId}</code> - Poll progress, IoU metrics, and output hashes</li>
                <li><code>GET /api/v1/artifacts/{runId}</code> - List output images, masks, and BOM reports</li>
                <li><code>POST /api/v1/replay</code> - Deterministically replay historical runs by seed</li>
                <li><code>POST /api/v1/cad/feasibility</code> - End-to-end DXF to BOM & visual concept</li>
                <li><code>GET /health</code> - Check provider connectivity and worker state</li>
            </ul>
        </div>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
@app.get("/api/v1/health", response_model=HealthResponse, tags=["Monitoring"])
def health():
    """Health check endpoint reporting provider token status and queue metrics."""
    replicate_token = os.getenv("REPLICATE_API_TOKEN", "")
    stats = job_manager.get_queue_stats()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        service="control-bim-pf-engine",
        replicateTokenConfigured=bool(replicate_token and len(replicate_token) > 5),
        replicateDepthModel=os.getenv(
            "REPLICATE_CONTROLNET_DEPTH_MODEL",
            "lucataco/sdxl-controlnet-depth:465fb41789dc2203a9d7158be11d1d2570606a039c65e0e236fd329b5eecb10c",
        ),
        replicateCannyModel=os.getenv(
            "REPLICATE_CONTROLNET_CANNY_MODEL",
            "jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613",
        ),
        dryRunDefault=os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes"),
        activeWorkers=2,
        pendingJobs=stats["pending"],
        completedJobs=stats["completed"],
    )


@app.post(
    "/api/v1/submit",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Execution"],
    dependencies=[Depends(verify_api_key)],
)
def submit_case(req: SubmitCaseRequest):
    """Submit a single visual restyling or evaluation case to the background queue."""
    run_id = job_manager.submit_case_job(req)
    return SubmitResponse(
        runId=run_id,
        status="queued",
        message=f"Case '{req.caseId}' submitted successfully to background worker queue.",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/api/v1/status/{runId}",
    response_model=RunStatusResponse,
    tags=["Execution"],
)
def get_status(runId: str):
    """Retrieve execution status, metrics, IoU verification, and logs for a job."""
    job = job_manager.get_job(runId)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job runId '{runId}' not found.",
        )
    return RunStatusResponse(**job)


@app.get("/api/v1/jobs", tags=["Execution"], dependencies=[Depends(verify_api_key)])
def list_jobs(limit: int = Query(default=20, ge=1, le=100)):
    """List recent background jobs and their current status."""
    return job_manager.list_jobs(limit=limit)


@app.get("/api/v1/artifacts/{runId}", tags=["Artifacts"])
def get_artifacts(
    runId: str,
    download: Literal["json", "zip"] = Query(default="json", description="Response format"),
):
    """List artifact URLs or download a compressed ZIP bundle of all run files."""
    job = job_manager.get_job(runId)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job runId '{runId}' not found.",
        )

    if download == "zip":
        zip_buffer = job_manager.create_artifacts_zip(runId)
        if not zip_buffer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact directory for runId '{runId}' not found or empty.",
            )
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=artifacts-{runId}.zip"},
        )

    # Return JSON artifact index
    files = []
    for filename in job.get("artifactPaths", {}).keys():
        file_url = f"/api/v1/artifacts/{runId}/file/{filename}"
        mime, _ = mimetypes.guess_type(filename)
        files.append(
            ArtifactItem(
                name=filename,
                url=file_url,
                sizeBytes=0,
                contentType=mime or "application/octet-stream",
            )
        )

    return ArtifactListResponse(
        runId=runId,
        artifactsDir=f"artifacts/evaluations/{runId}",
        zipUrl=f"/api/v1/artifacts/{runId}?download=zip",
        files=files,
    )


@app.get("/api/v1/artifacts/{runId}/file/{filename}", tags=["Artifacts"])
def get_artifact_file(runId: str, filename: str):
    """Stream or preview a specific artifact file (PNG image, mask, SVG, JSON report)."""
    candidate_paths = [
        Path("artifacts") / "evaluations" / runId / filename,
        Path("artifacts") / "replays" / runId / filename,
        Path("artifacts") / "feasibility" / runId / filename,
    ]
    file_path = next((p for p in candidate_paths if p.exists() and p.is_file()), None)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact file '{filename}' not found for runId '{runId}'.",
        )

    mime_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=str(file_path), media_type=mime_type or "application/octet-stream")


@app.post(
    "/api/v1/replay",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Execution"],
    dependencies=[Depends(verify_api_key)],
)
def replay_case(req: ReplayRequest):
    """Deterministically replay a previous run using its recorded seed and parameters."""
    run_id = job_manager.submit_replay_job(req)
    return SubmitResponse(
        runId=run_id,
        status="queued",
        message="Deterministic replay job queued successfully.",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )


@app.post(
    "/api/v1/cad/feasibility",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["CAD Pre-Feasibility"],
    dependencies=[Depends(verify_api_key)],
)
def run_cad_feasibility(req: CadFeasibilityRequest):
    """Run end-to-end DXF parsing, BOM material costing, and ControlNet visual generation."""
    run_id = job_manager.submit_cad_feasibility_job(req)
    return SubmitResponse(
        runId=run_id,
        status="queued",
        message="End-to-end CAD Pre-Feasibility job queued.",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )
