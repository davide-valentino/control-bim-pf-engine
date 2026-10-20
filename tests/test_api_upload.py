"""API tests for multipart DXF upload into the pre-feasibility pipeline."""
import time

from fastapi.testclient import TestClient

from src.api.app import app
from tests.helpers import REPO_ROOT


def _poll(client, run_id, timeout_s=60):
    deadline = time.time() + timeout_s
    status_data = {}
    while time.time() < deadline:
        status_data = client.get(f"/api/v1/status/{run_id}").json()
        if status_data.get("status") in ("done", "failed"):
            return status_data
        time.sleep(0.25)
    return status_data


def test_upload_cad_feasibility_dry_run():
    client = TestClient(app)
    with open(REPO_ROOT / "simple_room.dxf", "rb") as dxf_file:
        response = client.post(
            "/api/v1/cad/feasibility/upload",
            files={"file": ("simple_room.dxf", dxf_file, "application/dxf")},
            data={
                "preset": "Luxury Minimal",
                "targetStyle": "tropical-boutique",
                "inputType": "interior",
                "dryRun": "true",
            },
        )

    assert response.status_code == 202, response.text
    run_id = response.json()["runId"]

    status_data = _poll(client, run_id)
    assert status_data.get("status") == "done", status_data.get("error")

    artifacts = status_data.get("artifactPaths", {})
    assert "report.json" in artifacts
    assert "costs.json" in artifacts


def test_upload_rejects_non_dxf():
    client = TestClient(app)
    response = client.post(
        "/api/v1/cad/feasibility/upload",
        files={"file": ("plan.pdf", b"%PDF-1.4", "application/pdf")},
        data={"dryRun": "true"},
    )
    assert response.status_code == 400
    assert "dxf" in response.json()["detail"].lower()
