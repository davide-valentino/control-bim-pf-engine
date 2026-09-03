"""Integration and unit tests for the pf-engine REST API."""
import os
import time
import pytest
from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_health_endpoints():
    """Verify health endpoints return ok status and configuration fields."""
    for path in ["/health", "/api/v1/health"]:
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "pf-engine"
        assert "replicateTokenConfigured" in data
        assert "activeWorkers" in data


def test_submit_dry_run_and_poll_status():
    """Submit a dry-run case and poll status to completion."""
    payload = {
        "caseId": "test-api-dryrun-001",
        "inputType": "interior",
        "targetStyle": "luxury-minimal",
        "localImagePath": "tests/fixtures/sample_interior.png",
        "runsPerCase": 1,
        "dryRun": True,
    }

    submit_resp = client.post("/api/v1/submit", json=payload)
    assert submit_resp.status_code == 202
    submit_data = submit_resp.json()
    assert "runId" in submit_data
    run_id = submit_data["runId"]
    assert submit_data["status"] == "queued"

    # Poll status until done
    for _ in range(10):
        time.sleep(0.3)
        status_resp = client.get(f"/api/v1/status/{run_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        if status_data["status"] == "done":
            break

    assert status_data["status"] == "done"
    assert status_data["progress"] == 1.0
    assert status_data["iou"] is not None
    assert status_data["imageHash_SHA256"] is not None
    assert len(status_data["artifactPaths"]) > 0


def test_artifacts_endpoints():
    """Verify listing and downloading artifacts for a completed run."""
    # First submit and finish a dry-run job
    payload = {
        "caseId": "test-artifacts-001",
        "inputType": "floorplan",
        "targetStyle": "tropical-boutique",
        "localImagePath": "tests/fixtures/sample_floorplan.png",
        "dryRun": True,
    }
    submit_resp = client.post("/api/v1/submit", json=payload)
    run_id = submit_resp.json()["runId"]

    # Wait for completion
    for _ in range(10):
        time.sleep(0.3)
        status_resp = client.get(f"/api/v1/status/{run_id}")
        if status_resp.json()["status"] == "done":
            break

    # 1. Test JSON artifact list
    list_resp = client.get(f"/api/v1/artifacts/{run_id}")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["runId"] == run_id
    assert len(list_data["files"]) > 0

    # 2. Test downloading single artifact file
    first_file = list_data["files"][0]["name"]
    file_resp = client.get(f"/api/v1/artifacts/{run_id}/file/{first_file}")
    assert file_resp.status_code == 200
    assert len(file_resp.content) > 0

    # 3. Test downloading ZIP bundle
    zip_resp = client.get(f"/api/v1/artifacts/{run_id}?download=zip")
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"
    assert len(zip_resp.content) > 0


def test_cad_feasibility_pipeline_endpoint():
    """Verify end-to-end DXF parsing, BOM costing, and visual generation via API."""
    payload = {
        "dxfPath": "simple_room.dxf",
        "preset": "Luxury Minimal",
        "targetStyle": "luxury-minimal",
        "dryRun": True,
    }
    resp = client.post("/api/v1/cad/feasibility", json=payload)
    assert resp.status_code == 202
    run_id = resp.json()["runId"]

    # Poll status
    for _ in range(15):
        time.sleep(0.3)
        status_resp = client.get(f"/api/v1/status/{run_id}")
        if status_resp.json()["status"] == "done":
            break

    status_data = status_resp.json()
    assert status_data["status"] == "done"
    assert "report.json" in status_data["artifactPaths"]
    assert "visualization.svg" in status_data["artifactPaths"]


def test_auth_protection(monkeypatch):
    """Verify that setting PF_API_KEY enforces authentication."""
    monkeypatch.setenv("PF_API_KEY", "secret-test-token-12345")

    payload = {
        "caseId": "test-auth-001",
        "inputType": "interior",
        "targetStyle": "luxury-minimal",
        "dryRun": True,
    }

    # 1. Unauthenticated request should fail with 401
    unauth_resp = client.post("/api/v1/submit", json=payload)
    assert unauth_resp.status_code == 401

    # 2. Authenticated request with Bearer header should succeed
    auth_resp = client.post(
        "/api/v1/submit",
        json=payload,
        headers={"Authorization": "Bearer secret-test-token-12345"},
    )
    assert auth_resp.status_code == 202

    # 3. Authenticated request with X-API-Key header should succeed
    api_key_resp = client.post(
        "/api/v1/submit",
        json=payload,
        headers={"X-API-Key": "secret-test-token-12345"},
    )
    assert api_key_resp.status_code == 202
