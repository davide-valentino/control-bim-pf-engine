"""Tests for complex architectural DXF files containing multi-room, multi-layer drawings."""
import os
import pytest
from src.pipeline.parser import parse_dxf
from src.pipeline.semantics import classify_rooms
from src.pipeline.materials import assign_materials
from src.pipeline.costing import estimate_cost
from src.summary import generate_summary
from src.visualization import generate_svg, export_silhouette_mask


@pytest.mark.skipif(not os.path.exists("RUMAH_RENOV.dxf"), reason="RUMAH_RENOV.dxf not present in workspace")
def test_complex_dxf_multi_room_extraction(tmp_path):
    # 1. Parse complex DXF
    raw_path = tmp_path / "raw_geometry.json"
    raw_data = parse_dxf("RUMAH_RENOV.dxf", str(raw_path))

    assert len(raw_data["walls"]) > 100, f"Expected >100 walls, got {len(raw_data['walls'])}"
    assert len(raw_data["doors"]) > 50, f"Expected >50 doors, got {len(raw_data['doors'])}"
    assert len(raw_data["labels"]) > 50, f"Expected >50 labels, got {len(raw_data['labels'])}"

    # 2. Semantic room classification
    semantic_data = classify_rooms(raw_data)
    rooms = semantic_data.get("rooms", [])
    assert len(rooms) >= 10, f"Expected >=10 rooms, got {len(rooms)}"

    # Verify presence of key architectural room types
    room_names = [r["name"] for r in rooms]
    has_bedroom = any("Bedroom" in name or "Wardrobe" in name for name in room_names)
    has_wet_area = any("Bathroom" in name or "Toilet" in name or "Kitchen" in name for name in room_names)
    assert has_bedroom, f"Expected at least one bedroom space in {room_names[:10]}"
    assert has_wet_area, f"Expected at least one wet area space in {room_names[:10]}"

    # 3. BOM Material Assignment & Costing
    materials_data = assign_materials(semantic_data, preset="Luxury Minimal")
    costs_data = estimate_cost(materials_data)
    assert costs_data["total_cost"] > 0, "Total cost should be greater than 0"

    # 4. Report Summary Generation
    report = {
        "raw_geometry": raw_data,
        "semantic": semantic_data,
        "materials": materials_data,
        "costs": costs_data,
    }
    summary = generate_summary(report)
    assert summary["rooms"] == len(rooms)
    assert summary["wall_area_m2"] > 0

    # 5. Visualization & Silhouette Mask Extraction
    svg_path = str(tmp_path / "visualization.svg")
    mask_path = str(tmp_path / "cad_room_1_silhouette.png")
    generate_svg(semantic_data, svg_path)
    assert os.path.exists(svg_path)

    export_silhouette_mask(svg_path, mask_path, room_id=1, semantic_data=semantic_data)
    assert os.path.exists(mask_path)


@pytest.mark.skipif(not os.path.exists("RUMAH_RENOV.dxf"), reason="RUMAH_RENOV.dxf not present in workspace")
def test_complex_dxf_multi_room_api_feasibility():
    import time
    from fastapi.testclient import TestClient
    from src.api.app import app

    client = TestClient(app)
    payload = {
        "dxfPath": "RUMAH_RENOV.dxf",
        "preset": "Luxury Minimal",
        "targetStyle": "tropical-boutique",
        "inputType": "interior",
        "dryRun": True,
    }
    resp = client.post("/api/v1/cad/feasibility", json=payload)
    assert resp.status_code == 202
    run_id = resp.json()["runId"]

    for _ in range(60):
        time.sleep(0.5)
        status_resp = client.get(f"/api/v1/status/{run_id}")
        if status_resp.json()["status"] in ("done", "failed"):
            break

    status_data = status_resp.json()
    assert status_data["status"] == "done"
    artifact_paths = status_data["artifactPaths"]

    # Verify both the main concept file and per-room renders are in the artifact list
    assert "output-cad-tropical-boutique-run1.png" in artifact_paths, "Missing main concept render"
    assert "output-cad-room-1-run1.png" in artifact_paths, "Missing room 1 render"
    assert "cad_silhouette.png" in artifact_paths, "Missing main concept silhouette mask"
    assert "cad_room_1_silhouette.png" in artifact_paths, "Missing room 1 silhouette mask"
    assert "report.json" in artifact_paths
    assert "visualization.svg" in artifact_paths
