"""In-process background job manager and state store for control-bim-pf-engine."""
import concurrent.futures
import hashlib
import io
import json
import os
import shutil
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image, ImageDraw

from src.api.schemas import (
    CadFeasibilityRequest,
    ReplayRequest,
    RunStatusResponse,
    SubmitCaseRequest,
)
from src.pipeline.debug_map import generate_control_map, save_control_map_and_mask
from src.pipeline.evaluation_executor import execute_evaluation, replay_run
from src.pipeline.image_io import normalize_source
from src.pipeline.replicate_adapter import EvalPayload
from tools.iou_checker import compute_iou, save_binary_mask


class JobManager:
    """Manages asynchronous job queue, background worker execution, and status polling."""

    def __init__(self, max_workers: int = 2, artifacts_root: str = "artifacts"):
        self.artifacts_root = Path(artifacts_root)
        self.jobs_dir = self.artifacts_root / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="pf-worker"
        )
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._load_persisted_jobs()

    def _load_persisted_jobs(self) -> None:
        """Load previously persisted jobs from disk into memory."""
        for file in self.jobs_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text())
                if "runId" in data:
                    self._jobs[data["runId"]] = data
            except Exception:
                pass

    def _persist_job(self, run_id: str) -> None:
        """Persist in-memory job state to disk JSON."""
        job_data = self._jobs.get(run_id)
        if job_data:
            job_file = self.jobs_dir / f"{run_id}.json"
            job_file.write_text(json.dumps(job_data, indent=2))

    def get_job(self, run_id: str) -> dict[str, Any] | None:
        """Retrieve job record by runId."""
        with self._lock:
            return self._jobs.get(run_id)

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent jobs ordered by creation timestamp."""
        with self._lock:
            sorted_jobs = sorted(
                self._jobs.values(),
                key=lambda x: x.get("createdAt", ""),
                reverse=True,
            )
            return sorted_jobs[:limit]

    def get_queue_stats(self) -> dict[str, int]:
        """Get summary count of active, queued, and completed jobs."""
        with self._lock:
            pending = sum(1 for j in self._jobs.values() if j.get("status") in ("queued", "running"))
            completed = sum(1 for j in self._jobs.values() if j.get("status") == "done")
            failed = sum(1 for j in self._jobs.values() if j.get("status") == "fail")
            return {"pending": pending, "completed": completed, "failed": failed}

    def _append_log(self, run_id: str, message: str) -> None:
        """Append log line to job record and print."""
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        with self._lock:
            if run_id in self._jobs:
                self._jobs[run_id]["logs"].append(log_line)
                self._jobs[run_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()
                self._persist_job(run_id)
        print(f"[{run_id}] {message}", flush=True)

    def submit_case_job(self, req: SubmitCaseRequest) -> str:
        """Queue a single case execution job."""
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"run_{req.caseId}_{timestamp_str}"
        now = datetime.now(timezone.utc).isoformat()

        job_record = {
            "runId": run_id,
            "type": "single_case",
            "caseId": req.caseId,
            "inputType": req.inputType,
            "targetStyle": req.targetStyle,
            "status": "queued",
            "progress": 0.0,
            "latencyMs": None,
            "iou": None,
            "tier": None,
            "imageHash_SHA256": None,
            "seed": None,
            "error": None,
            "logs": [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Job queued successfully."],
            "artifactPaths": {},
            "summary": None,
            "createdAt": now,
            "updatedAt": now,
        }

        with self._lock:
            self._jobs[run_id] = job_record
            self._persist_job(run_id)

        self.executor.submit(self._run_single_case_task, run_id, req)
        return run_id

    def submit_replay_job(self, req: ReplayRequest) -> str:
        """Queue a deterministic replay job."""
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"replay_{timestamp_str}"
        now = datetime.now(timezone.utc).isoformat()

        job_record = {
            "runId": run_id,
            "type": "replay",
            "status": "queued",
            "progress": 0.0,
            "latencyMs": None,
            "iou": None,
            "tier": None,
            "imageHash_SHA256": None,
            "seed": None,
            "error": None,
            "logs": [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Replay job queued."],
            "artifactPaths": {},
            "summary": None,
            "createdAt": now,
            "updatedAt": now,
        }

        with self._lock:
            self._jobs[run_id] = job_record
            self._persist_job(run_id)

        self.executor.submit(self._run_replay_task, run_id, req)
        return run_id

    def submit_cad_feasibility_job(self, req: CadFeasibilityRequest) -> str:
        """Queue end-to-end DXF to BOM & ControlNet restyling job."""
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"feasibility_{timestamp_str}"
        now = datetime.now(timezone.utc).isoformat()

        job_record = {
            "runId": run_id,
            "type": "cad_feasibility",
            "preset": req.preset,
            "targetStyle": req.targetStyle,
            "status": "queued",
            "progress": 0.0,
            "latencyMs": None,
            "iou": None,
            "tier": None,
            "imageHash_SHA256": None,
            "seed": None,
            "error": None,
            "logs": [f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Pre-feasibility job queued."],
            "artifactPaths": {},
            "summary": None,
            "createdAt": now,
            "updatedAt": now,
        }

        with self._lock:
            self._jobs[run_id] = job_record
            self._persist_job(run_id)

        self.executor.submit(self._run_cad_feasibility_task, run_id, req)
        return run_id

    # ---------------- Worker Implementations ----------------

    def _run_single_case_task(self, run_id: str, req: SubmitCaseRequest) -> None:
        """Worker task executing a single evaluation or dry-run."""
        with self._lock:
            self._jobs[run_id]["status"] = "running"
            self._jobs[run_id]["progress"] = 0.1
            self._jobs[run_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()
            self._persist_job(run_id)

        target_dir = self.artifacts_root / "evaluations" / run_id
        target_dir.mkdir(parents=True, exist_ok=True)

        is_dry_run = req.dryRun or os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

        try:
            if is_dry_run:
                self._append_log(run_id, f"Executing in DRY_RUN mode (offline simulation)...")
                time.sleep(0.5)
                # Create mock dry run artifacts
                result = self._execute_dry_run(run_id, req, target_dir)
            else:
                self._append_log(run_id, f"Starting real ControlNet run against Replicate for case: {req.caseId}")
                # Convert SubmitCaseRequest to EvalPayload
                payload_dict = req.model_dump()
                eval_payload = EvalPayload(
                    caseId=req.caseId,
                    inputType=req.inputType,
                    targetStyle=req.targetStyle,
                    imageUrl=req.imageUrl,
                    localImagePath=req.localImagePath or f"tests/fixtures/sample_{req.inputType}.png",
                    silhouettePath=req.silhouettePath,
                )

                self._append_log(run_id, f"Calling evaluation executor (runs_per_case={req.runsPerCase}, warmup={req.warmup})...")
                result = execute_evaluation(
                    cases=[eval_payload],
                    provider="replicate",
                    runs_per_case=req.runsPerCase,
                    replicate_overrides=req.overrides,
                    output_dir=target_dir,
                    warmup=req.warmup,
                )

            # Extract artifact paths
            artifact_paths = {}
            for path in target_dir.glob("*"):
                if path.is_file():
                    artifact_paths[path.name] = f"/api/v1/artifacts/{run_id}/file/{path.name}"

            runs = result.get("runs", [])
            primary_run = runs[0] if runs else {}

            with self._lock:
                self._jobs[run_id]["status"] = "done"
                self._jobs[run_id]["progress"] = 1.0
                self._jobs[run_id]["latencyMs"] = primary_run.get("latencyMs")
                self._jobs[run_id]["iou"] = primary_run.get("iou")
                self._jobs[run_id]["tier"] = primary_run.get("tier", "pass")
                self._jobs[run_id]["imageHash_SHA256"] = primary_run.get("imageHash_SHA256")
                self._jobs[run_id]["seed"] = primary_run.get("seed")
                self._jobs[run_id]["artifactPaths"] = artifact_paths
                self._jobs[run_id]["summary"] = result.get("summary")
                self._jobs[run_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()
                self._persist_job(run_id)

            self._append_log(run_id, f"Execution completed successfully. (IoU={primary_run.get('iou')}, Latency={primary_run.get('latencyMs')}ms)")

        except Exception as e:
            self._append_log(run_id, f"Execution failed: {str(e)}")
            with self._lock:
                self._jobs[run_id]["status"] = "failed"
                self._jobs[run_id]["progress"] = 1.0
                self._jobs[run_id]["error"] = str(e)
                self._jobs[run_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()
                self._persist_job(run_id)

    def _execute_dry_run(self, run_id: str, req: SubmitCaseRequest, target_dir: Path) -> dict:
        """Simulate an offline render with real image artifacts and deterministic IoU."""
        self._append_log(run_id, "[Dry Run] Generating mock conditioning maps and diffusion render...")
        src_path = req.localImagePath or f"tests/fixtures/sample_{req.inputType}.png"
        src_file = Path(src_path)
        if not src_file.exists():
            # Create a blank fallback canvas
            img = Image.new("RGB", (768, 768), color=(240, 240, 240))
            draw = ImageDraw.Draw(img)
            draw.rectangle([100, 100, 668, 668], outline=(0, 0, 0), width=8)
            src_file = target_dir / "fallback_input.png"
            img.save(src_file)

        # Save silhouette mask
        sil_path = target_dir / f"silhouette-mask-{req.caseId}.png"
        save_binary_mask(str(src_file), sil_path)

        # Save control map and mask
        ctrl_path = target_dir / f"controlmap-{req.caseId}-run1.png"
        mask_path = target_dir / f"controlmap-mask-{req.caseId}-run1.png"
        generate_control_map(str(src_file), str(ctrl_path), input_type=req.inputType)
        save_control_map_and_mask(str(ctrl_path), str(ctrl_path), str(mask_path))

        # Create synthetic output render
        out_img = Image.open(src_file).convert("RGB")
        out_path = target_dir / f"output-{req.caseId}-run1.png"
        out_img.save(out_path)
        output_bytes = out_path.read_bytes()
        sha256 = hashlib.sha256(output_bytes).hexdigest()

        iou = compute_iou(sil_path, mask_path)

        run_obj = {
            "caseId": req.caseId,
            "runId": 1,
            "inputType": req.inputType,
            "targetStyle": req.targetStyle,
            "modelId": "dry-run-mock-model",
            "seed": 424242,
            "latencyMs": 150.0,
            "iou": round(float(iou), 4),
            "tier": "pass",
            "passed": True,
            "imageHash_SHA256": sha256,
            "outputImagePath": str(out_path),
            "controlMapPath": str(ctrl_path),
            "controlMapMaskPath": str(mask_path),
            "silhouetteMaskPath": str(sil_path),
        }

        runs_file = target_dir / "runs.json"
        runs_file.write_text(json.dumps([run_obj], indent=2))

        summary_obj = {
            "totalCases": 1,
            "runsPerCase": 1,
            "totalRuns": 1,
            "successRuns": 1,
            "failedRuns": 0,
            "p50LatencyMs": 150.0,
            "p95LatencyMs": 150.0,
            "iouThreshold": 0.85,
        }
        (target_dir / "summary.json").write_text(json.dumps(summary_obj, indent=2))

        return {"runs": [run_obj], "summary": summary_obj}

    def _run_replay_task(self, run_id: str, req: ReplayRequest) -> None:
        """Worker task for deterministic replay."""
        with self._lock:
            self._jobs[run_id]["status"] = "running"
            self._jobs[run_id]["progress"] = 0.2
            self._jobs[run_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()
            self._persist_job(run_id)

        target_dir = self.artifacts_root / "replays" / run_id
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            run_spec = None
            if req.runSpecPath and Path(req.runSpecPath).exists():
                run_spec = req.runSpecPath
            elif req.runId and (self.artifacts_root / "evaluations" / req.runId / "runs.json").exists():
                run_spec = str(self.artifacts_root / "evaluations" / req.runId / "runs.json")
            elif req.runData:
                run_spec = req.runData
            else:
                raise ValueError("Valid runSpecPath, existing runId, or runData is required for replay.")

            self._append_log(run_id, f"Executing replay against provider with spec: {run_spec}")
            replay_res = replay_run(run_spec, provider="replicate", output_dir=target_dir)

            artifact_paths = {}
            for path in target_dir.glob("*"):
                if path.is_file():
                    artifact_paths[path.name] = f"/api/v1/artifacts/{run_id}/file/{path.name}"

            with self._lock:
                self._jobs[run_id]["status"] = "done"
                self._jobs[run_id]["progress"] = 1.0
                self._jobs[run_id]["latencyMs"] = replay_res.get("latencyMs")
                self._jobs[run_id]["imageHash_SHA256"] = replay_res.get("replayHash")
                self._jobs[run_id]["seed"] = replay_res.get("seed")
                self._jobs[run_id]["artifactPaths"] = artifact_paths
                self._jobs[run_id]["summary"] = replay_res
                self._jobs[run_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()
                self._persist_job(run_id)

            self._append_log(run_id, f"Replay finished. Hash matched: {replay_res.get('hashMatched')}")

        except Exception as e:
            self._append_log(run_id, f"Replay failed: {str(e)}")
            with self._lock:
                self._jobs[run_id]["status"] = "failed"
                self._jobs[run_id]["progress"] = 1.0
                self._jobs[run_id]["error"] = str(e)
                self._jobs[run_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()
                self._persist_job(run_id)

    def _run_cad_feasibility_task(self, run_id: str, req: CadFeasibilityRequest) -> None:
        """Worker task for CAD parsing, BOM calculation, and visual render."""
        with self._lock:
            self._jobs[run_id]["status"] = "running"
            self._jobs[run_id]["progress"] = 0.1
            self._persist_job(run_id)

        target_dir = self.artifacts_root / "feasibility" / run_id
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._append_log(run_id, f"1. Parsing DXF file: {req.dxfPath}")
            from src.pipeline.parser import parse_dxf
            from src.pipeline.semantics import classify_semantics
            from src.pipeline.materials import run_material_assignment
            from src.pipeline.costing import run_cost_estimation
            from src.summary import generate_summary
            from src.visualization import generate_svg, export_silhouette_mask

            raw_geom_path = str(target_dir / "raw_geometry.json")
            parse_dxf(req.dxfPath, raw_geom_path)
            self._jobs[run_id]["progress"] = 0.25

            self._append_log(run_id, "2. Classifying semantic rooms and wall polygons")
            semantic_path = str(target_dir / "semantic.json")
            classify_semantics(raw_geom_path, semantic_path)
            self._jobs[run_id]["progress"] = 0.40

            self._append_log(run_id, f"3. Assigning material catalog preset: {req.preset}")
            materials_path = str(target_dir / "materials.json")
            run_material_assignment(semantic_path, materials_path, preset=req.preset)
            self._jobs[run_id]["progress"] = 0.55

            self._append_log(run_id, "4. Estimating BOM line-item costs and wall areas")
            costs_path = str(target_dir / "costs.json")
            run_cost_estimation(materials_path, costs_path)
            self._jobs[run_id]["progress"] = 0.70

            self._append_log(run_id, "5. Generating consolidated report and SVG floorplan")
            report_path = str(target_dir / "report.json")
            svg_path = str(target_dir / "visualization.svg")

            raw_geom_data = json.loads(Path(raw_geom_path).read_text())
            semantic_data = json.loads(Path(semantic_path).read_text())
            materials_data = json.loads(Path(materials_path).read_text())
            costs_data = json.loads(Path(costs_path).read_text())

            report_dict = {
                "raw_geometry": raw_geom_data,
                "semantic": semantic_data,
                "materials": materials_data,
                "costs": costs_data,
            }
            report_dict["summary"] = generate_summary(report_dict)
            Path(report_path).write_text(json.dumps(report_dict, indent=2))
            generate_svg(semantic_data, svg_path)
            self._jobs[run_id]["progress"] = 0.85

            # Dynamic conditioning image extraction from semantic CAD geometry
            input_type = req.inputType or "interior"
            room_id = req.roomId
            if input_type == "interior":
                if room_id is None and semantic_data.get("rooms"):
                    room_id = semantic_data["rooms"][0].get("room_id")
                cad_sil_path = str(target_dir / f"cad_room_{room_id or 1}_silhouette.png")
                export_silhouette_mask(svg_path, cad_sil_path, room_id=room_id, semantic_data=semantic_data)
            else:
                cad_sil_path = str(target_dir / "cad_silhouette.png")
                export_silhouette_mask(svg_path, cad_sil_path)

            # Trigger ControlNet visual restyling from dynamic CAD conditioning
            self._append_log(run_id, f"6. Synthesizing visual concept with ControlNet style: {req.targetStyle} (modality: {input_type})")
            case_id = f"cad-{req.targetStyle}"
            dxf_submit_case = SubmitCaseRequest(
                caseId=case_id,
                inputType=input_type,
                targetStyle=req.targetStyle,
                localImagePath=cad_sil_path,
                overrides=req.overrides,
                dryRun=req.dryRun,
            )
            if req.dryRun:
                dry_res = self._execute_dry_run(run_id, dxf_submit_case, target_dir)
                run_obj = dry_res["runs"][0]
                with self._lock:
                    self._jobs[run_id]["latencyMs"] = run_obj.get("latencyMs")
                    self._jobs[run_id]["iou"] = run_obj.get("iou")
                    self._jobs[run_id]["tier"] = run_obj.get("tier")
                    self._jobs[run_id]["imageHash_SHA256"] = run_obj.get("imageHash_SHA256")
                    self._jobs[run_id]["seed"] = run_obj.get("seed")
            else:
                eval_res = execute_evaluation(
                    cases=[EvalPayload(
                        caseId=case_id,
                        inputType=input_type,
                        targetStyle=req.targetStyle,
                        localImagePath=cad_sil_path,
                    )],
                    provider="replicate",
                    replicate_overrides=req.overrides,
                    output_dir=target_dir,
                )
                runs_list = eval_res.get("runs", [])
                if runs_list:
                    r0 = runs_list[0]
                    with self._lock:
                        self._jobs[run_id]["latencyMs"] = r0.get("latencyMs")
                        self._jobs[run_id]["iou"] = r0.get("iou")
                        self._jobs[run_id]["tier"] = r0.get("status")
                        self._jobs[run_id]["imageHash_SHA256"] = r0.get("imageHash_SHA256")
                        self._jobs[run_id]["seed"] = r0.get("seed")

            artifact_paths = {}
            for path in target_dir.glob("*"):
                if path.is_file():
                    artifact_paths[path.name] = f"/api/v1/artifacts/{run_id}/file/{path.name}"

            with self._lock:
                self._jobs[run_id]["status"] = "done"
                self._jobs[run_id]["progress"] = 1.0
                self._jobs[run_id]["artifactPaths"] = artifact_paths
                self._jobs[run_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()
                self._persist_job(run_id)

            self._append_log(run_id, "Pre-feasibility pipeline executed successfully!")

        except Exception as e:
            self._append_log(run_id, f"Feasibility pipeline failed: {str(e)}")
            with self._lock:
                self._jobs[run_id]["status"] = "failed"
                self._jobs[run_id]["progress"] = 1.0
                self._jobs[run_id]["error"] = str(e)
                self._jobs[run_id]["updatedAt"] = datetime.now(timezone.utc).isoformat()
                self._persist_job(run_id)

    # ---------------- Artifact Packaging ----------------

    def create_artifacts_zip(self, run_id: str) -> io.BytesIO | None:
        """Create a zip archive buffer containing all files in the job's artifact directory."""
        # Find directory matching run_id across categories
        candidate_dirs = [
            self.artifacts_root / "evaluations" / run_id,
            self.artifacts_root / "replays" / run_id,
            self.artifacts_root / "feasibility" / run_id,
        ]
        target_dir = next((d for d in candidate_dirs if d.exists()), None)
        if not target_dir:
            return None

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in target_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(target_dir)
                    zip_file.write(file_path, arcname=str(arcname))

        zip_buffer.seek(0)
        return zip_buffer
