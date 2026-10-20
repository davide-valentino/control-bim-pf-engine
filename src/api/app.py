"""FastAPI application for the Pre-Feasibility Engine (control-bim-pf-engine) backend service."""
import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

_root_dir = Path(__file__).resolve().parents[2]
if (_root_dir / ".env.local").is_file():
    load_dotenv(_root_dir / ".env.local")
if (_root_dir / ".env").is_file():
    load_dotenv(_root_dir / ".env")

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Security, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import ValidationError

from src.api.auth import verify_api_key
from src.api.job_manager import JobManager
from src.api.schemas import (
    ArtifactItem,
    ArtifactListResponse,
    CadFeasibilityRequest,
    HealthResponse,
    PresetDetailResponse,
    PresetDisableResponse,
    PresetListResponse,
    PresetSummary,
    PresetUploadResponse,
    ReplayRequest,
    RunStatusResponse,
    SubmitCaseRequest,
    SubmitResponse,
)
from src.presets.store import (
    PresetBuiltinProtected,
    PresetConflict,
    PresetDisabled,
    PresetNotFound,
    PresetRecord,
    PresetStore,
)
from src.presets.validation import PresetTooLargeError, PresetValidationError

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

# Initialize rate-sheet store singleton (persisted next to job artifacts)
preset_store = PresetStore(root=job_manager.artifacts_root / "presets")


def _preset_summary(record: PresetRecord) -> PresetSummary:
    return PresetSummary(
        presetId=record.preset_id,
        name=record.name,
        currency=record.currency,
        asOf=record.as_of,
        source=record.source,
        origin=record.origin,
        version=record.version,
        roomTypes=record.room_types,
        itemCount=record.item_count,
        warnings=record.warnings,
        createdAt=record.created_at,
        disabled=record.disabled,
    )


def _preset_error(exc: Exception, not_found_status: int = status.HTTP_404_NOT_FOUND) -> HTTPException:
    """Translate store/validation exceptions into HTTP responses."""
    if isinstance(exc, PresetNotFound):
        return HTTPException(status_code=not_found_status, detail=str(exc))
    if isinstance(exc, (PresetConflict, PresetBuiltinProtected)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, PresetDisabled):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, PresetTooLargeError):
        return HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    if isinstance(exc, PresetValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": list(exc.loc), "msg": exc.message, "type": "value_error"}],
        )
    if isinstance(exc, ValidationError):
        detail = [
            {"loc": list(item.get("loc", ())), "msg": item.get("msg", ""), "type": item.get("type", "")}
            for item in exc.errors()
        ]
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _save_preset(raw: object, name_override: str | None = None) -> PresetUploadResponse:
    try:
        record, created = preset_store.save(raw, name_override=name_override)
    except (PresetNotFound, PresetConflict, PresetBuiltinProtected, PresetDisabled,
            PresetTooLargeError, PresetValidationError, ValidationError) as exc:
        raise _preset_error(exc) from exc
    return PresetUploadResponse(created=created, **_preset_summary(record).model_dump())


def _resolve_request_preset(preset_id: str | None, preset_name: str | None):
    """Resolve a job's rate sheet, reporting bad references as 422."""
    try:
        return preset_store.resolve(preset_id=preset_id, name=preset_name)
    except (PresetNotFound, PresetDisabled, PresetConflict) as exc:
        raise _preset_error(exc, not_found_status=status.HTTP_422_UNPROCESSABLE_ENTITY) from exc


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
    "/api/v1/presets",
    response_model=PresetUploadResponse,
    tags=["Rate Sheets"],
    dependencies=[Depends(verify_api_key)],
)
def create_preset(payload: dict = Body(..., description="Rate sheet JSON")):
    """Import a partner rate sheet from a JSON body.

    Accepts either ``{name, metadata, rooms}`` or the engine's native
    ``{presets: {<name>: ...}, metadata}`` envelope (one preset per upload).
    Identical content is idempotent; changed content creates a new version.
    """
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > preset_store.max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Rate sheet exceeds the {preset_store.max_bytes // 1024} KB limit.",
        )
    return _save_preset(payload)


@app.post(
    "/api/v1/presets/upload",
    response_model=PresetUploadResponse,
    tags=["Rate Sheets"],
    dependencies=[Depends(verify_api_key)],
)
async def upload_preset(
    file: UploadFile = File(..., description="Rate sheet JSON file"),
    presetName: str | None = Form(None, description="Optional name override"),
):
    """Import a partner rate sheet from an uploaded JSON file."""
    filename = Path(file.filename or "rates.json").name
    if not filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .json rate sheets are supported.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded rate sheet is empty.",
        )
    if len(contents) > preset_store.max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Rate sheet exceeds the {preset_store.max_bytes // 1024} KB limit.",
        )
    try:
        raw = json.loads(contents)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON: {exc}",
        ) from exc
    return _save_preset(raw, name_override=presetName)


@app.get("/api/v1/presets", response_model=PresetListResponse, tags=["Rate Sheets"])
def list_presets():
    """List built-in and uploaded rate sheets, including the exact version IDs."""
    groups = preset_store.list_all()
    return PresetListResponse(
        builtin=[_preset_summary(record) for record in groups["builtin"]],
        uploaded=[_preset_summary(record) for record in groups["uploaded"]],
    )


@app.get("/api/v1/presets/{presetId}", response_model=PresetDetailResponse, tags=["Rate Sheets"])
def get_preset(presetId: str):
    """Return one rate sheet's registry metadata and normalized document."""
    try:
        record, document = preset_store.detail(presetId)
    except (PresetNotFound, PresetConflict) as exc:
        raise _preset_error(exc) from exc
    return PresetDetailResponse(
        created=False,
        document=document,
        **_preset_summary(record).model_dump(),
    )


@app.delete(
    "/api/v1/presets/{presetId}",
    response_model=PresetDisableResponse,
    tags=["Rate Sheets"],
    dependencies=[Depends(verify_api_key)],
)
def disable_preset(presetId: str):
    """Soft-disable an uploaded rate sheet. Built-in presets are read-only."""
    try:
        record = preset_store.disable(presetId)
    except (PresetNotFound, PresetBuiltinProtected) as exc:
        raise _preset_error(exc) from exc
    return PresetDisableResponse(presetId=record.preset_id, name=record.name, disabled=True)


@app.post(
    "/api/v1/cad/feasibility",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["CAD Pre-Feasibility"],
    dependencies=[Depends(verify_api_key)],
)
def run_cad_feasibility(req: CadFeasibilityRequest):
    """Run end-to-end DXF parsing, BOM material costing, and ControlNet visual generation."""
    resolved_preset = _resolve_request_preset(req.presetId, req.preset)
    run_id = job_manager.submit_cad_feasibility_job(req, resolved_preset=resolved_preset)
    return SubmitResponse(
        runId=run_id,
        status="queued",
        message="End-to-end CAD Pre-Feasibility job queued.",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )


@app.post(
    "/api/v1/cad/feasibility/upload",
    response_model=SubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["CAD Pre-Feasibility"],
    dependencies=[Depends(verify_api_key)],
)
async def upload_cad_feasibility(
    file: UploadFile = File(..., description="DXF floorplan file"),
    preset: str | None = Form(None, description="BOM rate-sheet name"),
    presetId: str | None = Form(None, description="Exact rate-sheet version ID"),
    targetStyle: str = Form("luxury-minimal", description="ControlNet visual restyling style"),
    inputType: Literal["interior", "floorplan", "facade"] = Form("interior"),
    roomId: int | None = Form(None, description="Optional room_id to focus the render on"),
    maxRoomRenders: int = Form(3, description="Maximum per-room renders (0 = main concept only)"),
    dryRun: bool = Form(False, description="Generate CAD BOM and mock visual render offline"),
):
    """Upload a DXF file and queue the end-to-end pre-feasibility pipeline.

    This is the browser-facing counterpart of ``/api/v1/cad/feasibility``, which
    only accepts server-local paths. The uploaded file is stored under
    ``artifacts/uploads/`` and passed to the same job queue.
    """
    resolved_preset = _resolve_request_preset(presetId, preset)

    filename = Path(file.filename or "upload.dxf").name
    if not filename.lower().endswith(".dxf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .dxf files are supported.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    max_bytes = int(os.getenv("MAX_DXF_UPLOAD_BYTES", str(50 * 1024 * 1024)))
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"DXF exceeds the {max_bytes // (1024 * 1024)} MB upload limit.",
        )

    upload_dir = job_manager.artifacts_root / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dxf_path = upload_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{filename}"
    dxf_path.write_bytes(contents)

    run_id = job_manager.submit_cad_feasibility_job(CadFeasibilityRequest(
        dxfPath=str(dxf_path),
        preset=resolved_preset.name,
        presetId=resolved_preset.preset_id,
        targetStyle=targetStyle,
        inputType=inputType,
        roomId=roomId,
        maxRoomRenders=maxRoomRenders,
        dryRun=dryRun,
    ), resolved_preset=resolved_preset)
    return SubmitResponse(
        runId=run_id,
        status="queued",
        message="Uploaded CAD Pre-Feasibility job queued.",
        createdAt=datetime.now(timezone.utc).isoformat(),
    )
