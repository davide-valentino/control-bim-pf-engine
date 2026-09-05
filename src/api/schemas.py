"""Pydantic schemas for the Pre-Feasibility Engine (control-bim-pf-engine) REST API."""
from typing import Any, Literal
from pydantic import BaseModel, Field


class SubmitCaseRequest(BaseModel):
    """Payload to submit a single restyling or evaluation case."""
    caseId: str = Field(..., description="Unique case identifier", examples=["interior-villa-001"])
    inputType: Literal["interior", "facade", "floorplan"] = Field(
        ..., description="Spatial modality to condition ControlNet on", examples=["interior"]
    )
    targetStyle: str = Field(
        default="tropical-boutique",
        description="Target style preset or custom prompt key",
        examples=["tropical-boutique"],
    )
    imageUrl: str | None = Field(default=None, description="Public hosted URL of input image")
    localImagePath: str | None = Field(
        default=None, description="Local path to input image (workspace-relative or absolute)"
    )
    silhouettePath: str | None = Field(
        default=None, description="Optional custom silhouette mask path for IoU gating"
    )
    overrides: dict[str, Any] | None = Field(
        default=None, description="Optional model parameter overrides (e.g., seed, guidance_scale)"
    )
    runsPerCase: int = Field(
        default=1, ge=1, le=10, description="Number of sequential runs with seed tracking"
    )
    warmup: bool = Field(default=False, description="Whether to execute a pre-flight model warmup probe")
    dryRun: bool = Field(
        default=False, description="Simulate provider execution offline for front-end development without API spend"
    )


class BatchSubmitRequest(BaseModel):
    """Payload to submit multiple cases as a batch job."""
    batchId: str | None = Field(default=None, description="Optional batch job identifier")
    cases: list[SubmitCaseRequest] = Field(..., description="List of cases to execute")
    warmup: bool = Field(default=True, description="Execute model warmup before batch sweep")
    runsPerCase: int = Field(default=1, ge=1, le=10, description="Runs per case in batch")


class ReplayRequest(BaseModel):
    """Payload to deterministically replay a previously completed run."""
    runSpecPath: str | None = Field(
        default=None, description="File path to runs.json or replay spec"
    )
    runId: str | None = Field(
        default=None, description="Previous job runId to replay"
    )
    runData: dict[str, Any] | None = Field(
        default=None, description="Raw dictionary containing run metadata and seed"
    )


class CadFeasibilityRequest(BaseModel):
    """Payload to run end-to-end DXF parsing, BOM estimation, and ControlNet visual generation."""
    dxfPath: str = Field(
        default="simple_room.dxf", description="Path to DXF file"
    )
    preset: str = Field(
        default="Luxury Minimal", description="BOM material catalog preset (Luxury Minimal, Rustic, Industrial)"
    )
    targetStyle: str = Field(
        default="luxury-minimal", description="ControlNet visual restyling style"
    )
    inputType: Literal["interior", "floorplan", "facade"] = Field(
        default="interior", description="ControlNet conditioning input type (interior, floorplan, facade)"
    )
    roomId: int | None = Field(
        default=None, description="Optional room_id to focus on for interior rendering (defaults to first room)"
    )
    overrides: dict[str, Any] | None = Field(
        default=None, description="Optional model parameter overrides"
    )
    dryRun: bool = Field(
        default=False, description="If true, generates CAD BOM and mock visual render offline"
    )


class SubmitResponse(BaseModel):
    """Response returned immediately after queuing a job."""
    runId: str = Field(..., description="Unique job execution ID")
    status: Literal["queued", "running", "failed", "done"] = Field(
        ..., description="Current status of the job"
    )
    message: str = Field(..., description="Human-readable status message")
    artifactPaths: dict[str, str] | None = Field(
        default=None, description="Artifact relative paths or download URLs when completed"
    )
    createdAt: str = Field(..., description="ISO 8601 creation timestamp")


class RunStatusResponse(BaseModel):
    """Detailed status and metrics response for a job."""
    runId: str = Field(..., description="Unique job execution ID")
    status: Literal["queued", "running", "failed", "done"] = Field(
        ..., description="Current status of the job"
    )
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress from 0.0 to 1.0")
    latencyMs: float | None = Field(default=None, description="Execution latency in milliseconds")
    iou: float | None = Field(default=None, description="Calculated silhouette IoU")
    tier: str | None = Field(default=None, description="Gating tier (pass, warn, fail)")
    imageHash_SHA256: str | None = Field(default=None, description="SHA-256 hash of output image")
    seed: int | None = Field(default=None, description="Random seed used for generation")
    error: str | None = Field(default=None, description="Error message if failed")
    logs: list[str] = Field(default_factory=list, description="Job execution log entries")
    artifactPaths: dict[str, str] = Field(
        default_factory=dict, description="Artifact relative URLs / paths"
    )
    summary: dict[str, Any] | None = Field(default=None, description="Full summary JSON if batch run")
    createdAt: str = Field(..., description="Job creation timestamp")
    updatedAt: str = Field(..., description="Last updated timestamp")


class ArtifactItem(BaseModel):
    name: str
    url: str
    sizeBytes: int
    contentType: str


class ArtifactListResponse(BaseModel):
    runId: str
    artifactsDir: str
    zipUrl: str
    files: list[ArtifactItem]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    service: str = "control-bim-pf-engine"
    replicateTokenConfigured: bool
    replicateDepthModel: str
    replicateCannyModel: str
    dryRunDefault: bool
    activeWorkers: int
    pendingJobs: int
    completedJobs: int
