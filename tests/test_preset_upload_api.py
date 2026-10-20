"""API tests for importing and applying partner rate sheets."""
import json
import time

import pytest
from fastapi.testclient import TestClient

import src.api.app as app_module
from src.api.app import app
from src.presets.store import PresetStore
from tests.helpers import REPO_ROOT

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "idr_rate_sheet.json"


def load_sheet():
    return json.loads(FIXTURE.read_text())


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "preset_store", PresetStore(root=tmp_path / "presets"))
    return TestClient(app)


def _poll(client, run_id, timeout_s=90):
    deadline = time.time() + timeout_s
    status_data = {}
    while time.time() < deadline:
        status_data = client.get(f"/api/v1/status/{run_id}").json()
        if status_data.get("status") in ("done", "failed"):
            return status_data
        time.sleep(0.25)
    return status_data


def _upload_sheet(client):
    response = client.post("/api/v1/presets", json=load_sheet())
    assert response.status_code == 200, response.text
    return response.json()


def test_json_import_is_idempotent_and_versioned(client):
    first = _upload_sheet(client)
    assert first["created"] is True
    assert first["presetId"].startswith("bali-2026-10-")
    assert first["currency"] == "IDR"
    assert first["origin"] == "upload"
    assert first["warnings"] == []

    again = _upload_sheet(client)
    assert again["created"] is False
    assert again["presetId"] == first["presetId"]

    changed = load_sheet()
    changed["rooms"]["Living Room"]["walls"]["cost_per_m2"] = 190000
    response = client.post("/api/v1/presets", json=changed)
    assert response.status_code == 200, response.text
    assert response.json()["presetId"] != first["presetId"]


def test_multipart_upload_and_extension_check(client):
    raw = FIXTURE.read_bytes()
    response = client.post(
        "/api/v1/presets/upload",
        files={"file": ("bali-rates.json", raw, "application/json")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["currency"] == "IDR"

    rejected = client.post(
        "/api/v1/presets/upload",
        files={"file": ("bali-rates.txt", raw, "text/plain")},
    )
    assert rejected.status_code == 400
    assert "json" in rejected.json()["detail"].lower()


def test_invalid_sheet_returns_422(client):
    sheet = load_sheet()
    sheet["rooms"]["Living Room"]["doors"] = {"material": "Door", "cost_per_m2": 1000}
    response = client.post("/api/v1/presets", json=sheet)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("cost_per_unit" in item["msg"] for item in detail), detail


def test_builtin_name_collision_returns_409(client):
    sheet = load_sheet()
    sheet["name"] = "Rustic"
    response = client.post("/api/v1/presets", json=sheet)

    assert response.status_code == 409
    assert "built-in" in response.json()["detail"]


def test_oversized_sheet_returns_413(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        app_module, "preset_store", PresetStore(root=tmp_path / "small", max_bytes=10)
    )
    response = client.post("/api/v1/presets", json=load_sheet())

    assert response.status_code == 413


def test_list_detail_and_soft_delete(client):
    created = _upload_sheet(client)

    listing = client.get("/api/v1/presets")
    assert listing.status_code == 200
    body = listing.json()
    assert {item["name"] for item in body["builtin"]} == {
        "Luxury Minimal",
        "Rustic",
        "Industrial",
    }
    assert [item["presetId"] for item in body["uploaded"]] == [created["presetId"]]

    detail = client.get(f"/api/v1/presets/{created['presetId']}")
    assert detail.status_code == 200
    assert detail.json()["document"]["name"] == "Bali 2026-10"
    assert "Living Room" in detail.json()["document"]["rooms"]

    assert client.get("/api/v1/presets/missing-000000000000").status_code == 404
    assert client.delete("/api/v1/presets/builtin:rustic").status_code == 409

    deleted = client.delete(f"/api/v1/presets/{created['presetId']}")
    assert deleted.status_code == 200
    assert deleted.json()["disabled"] is True

    after = client.get("/api/v1/presets").json()["uploaded"]
    assert after[0]["disabled"] is True


def test_feasibility_uses_uploaded_idr_rates(client):
    created = _upload_sheet(client)

    with open(REPO_ROOT / "simple_room.dxf", "rb") as dxf_file:
        response = client.post(
            "/api/v1/cad/feasibility/upload",
            files={"file": ("simple_room.dxf", dxf_file, "application/dxf")},
            data={
                "presetId": created["presetId"],
                "targetStyle": "tropical-boutique",
                "maxRoomRenders": "0",
                "dryRun": "true",
            },
        )
    assert response.status_code == 202, response.text
    run_id = response.json()["runId"]

    status_data = _poll(client, run_id)
    assert status_data.get("status") == "done", status_data.get("error")

    job = app_module.job_manager.get_job(run_id)
    assert job["presetId"] == created["presetId"]
    assert job["preset"] == "Bali 2026-10"
    assert job["currency"] == "IDR"

    run_dir = app_module.job_manager.artifacts_root / "feasibility" / run_id
    costs = json.loads((run_dir / "costs.json").read_text())

    # simple_room.dxf: walls 54 m2, floor 20 m2, one door.
    assert costs["currency"] == "IDR"
    assert costs["preset"] == {
        "id": created["presetId"],
        "name": "Bali 2026-10",
        "version": created["version"],
        "origin": "upload",
    }
    assert costs["total_cost"] == pytest.approx(18_890_000.0)

    snapshot = json.loads((run_dir / "rates-snapshot.json").read_text())
    assert snapshot["metadata"]["currency"] == "IDR"
    assert snapshot["presets"]["Bali 2026-10"]["Living Room"]["walls"]["cost_per_m2"] == 185000


def test_unknown_preset_id_is_rejected_before_queueing(client):
    with open(REPO_ROOT / "simple_room.dxf", "rb") as dxf_file:
        response = client.post(
            "/api/v1/cad/feasibility/upload",
            files={"file": ("simple_room.dxf", dxf_file, "application/dxf")},
            data={"presetId": "missing-000000000000", "dryRun": "true"},
        )

    assert response.status_code == 422
    assert "unknown preset" in response.json()["detail"].lower()
