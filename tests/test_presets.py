"""Unit and integration tests for style preset assignment."""
import json
import os
import subprocess
import sys
import pytest

from src.pipeline.materials import (
    STYLE_PRESETS,
    load_presets,
    match_room_preset,
    assign_materials,
    run_material_assignment
)
from src.pipeline.costing import estimate_cost


def test_presets_catalog_loaded():
    """Verify that style presets catalog contains all expected presets and keys."""
    presets = load_presets()
    assert "Luxury Minimal" in presets
    assert "Rustic" in presets
    assert "Industrial" in presets

    for preset_name in ["Luxury Minimal", "Rustic", "Industrial"]:
        preset = presets[preset_name]
        assert "Living Room" in preset
        assert "Kitchen" in preset

        for room_type in ["Living Room", "Kitchen"]:
            room_cfg = preset[room_type]
            assert "walls" in room_cfg
            assert "floors" in room_cfg
            assert "doors" in room_cfg
            assert "windows" in room_cfg

            assert "material" in room_cfg["walls"]
            assert "cost_per_m2" in room_cfg["walls"]
            assert "material" in room_cfg["floors"]
            assert "cost_per_m2" in room_cfg["floors"]
            assert "material" in room_cfg["doors"]
            assert "cost_per_unit" in room_cfg["doors"]
            assert "material" in room_cfg["windows"]
            assert "cost_per_m2" in room_cfg["windows"]


def test_assign_materials_luxury_minimal():
    """Verify material assignment for Luxury Minimal preset."""
    semantic_data = {
        "rooms": [
            {
                "room_id": 1,
                "name": "Living Room",
                "boundary": [[0.0, 0.0], [5000.0, 0.0], [5000.0, 4000.0], [0.0, 4000.0], [0.0, 0.0]]
            },
            {
                "room_id": 2,
                "name": "Kitchen",
                "boundary": [[5000.0, 0.0], [8000.0, 0.0], [8000.0, 4000.0], [5000.0, 4000.0], [5000.0, 0.0]]
            }
        ],
        "doors": [
            {"start": [1000.0, 0.0], "end": [1900.0, 0.0]}
        ]
    }

    result = assign_materials(semantic_data, preset="Luxury Minimal")

    assert result["preset"] == "Luxury Minimal"
    assert len(result["rooms"]) == 2

    living_room = result["rooms"][0]
    assert living_room["materials"]["walls"]["material"] == "White Drywall"
    assert living_room["materials"]["walls"]["cost_per_m2"] == 18.0
    assert living_room["materials"]["floors"]["material"] == "Oak Hardwood"
    assert living_room["materials"]["floors"]["cost_per_m2"] == 45.0
    assert living_room["materials"]["doors"]["material"] == "Frameless Glass Door"
    assert living_room["materials"]["doors"]["cost_per_unit"] == 250.0
    assert living_room["materials"]["windows"]["material"] == "Floor-to-Ceiling Glass"
    assert living_room["materials"]["windows"]["cost_per_m2"] == 120.0
    assert living_room["material"]["material"] == "White Drywall"



def test_assign_materials_rustic():
    """Verify material assignment for Rustic preset."""
    semantic_data = {
        "rooms": [
            {"room_id": 1, "name": "Living Room", "boundary": [[0.0, 0.0], [5000.0, 0.0], [5000.0, 4000.0], [0.0, 0.0]]},
            {"room_id": 2, "name": "Kitchen", "boundary": [[5000.0, 0.0], [8000.0, 0.0], [8000.0, 4000.0], [5000.0, 0.0]]}
        ],
        "doors": [{"start": [1000.0, 0.0], "end": [1900.0, 0.0]}]
    }

    result = assign_materials(semantic_data, preset="Rustic")

    lr = result["rooms"][0]
    assert lr["materials"]["walls"]["material"] == "Exposed Timber"
    assert lr["materials"]["walls"]["cost_per_m2"] == 20.0
    assert lr["materials"]["floors"]["material"] == "Wide Plank Wood"
    assert lr["materials"]["floors"]["cost_per_m2"] == 40.0
    assert lr["materials"]["doors"]["material"] == "Heavy Wood Door"
    assert lr["materials"]["doors"]["cost_per_unit"] == 150.0
    assert lr["materials"]["windows"]["material"] == "Wood Frame Window"
    assert lr["materials"]["windows"]["cost_per_m2"] == 80.0

    kit = result["rooms"][1]
    assert kit["materials"]["walls"]["material"] == "Stone Cladding"
    assert kit["materials"]["walls"]["cost_per_m2"] == 28.0
    assert kit["materials"]["floors"]["material"] == "Terracotta Tile"
    assert kit["materials"]["floors"]["cost_per_m2"] == 30.0
    assert kit["materials"]["doors"]["material"] == "Wrought Iron Door"
    assert kit["materials"]["doors"]["cost_per_unit"] == 200.0
    assert kit["materials"]["windows"]["material"] == "Small Pane Window"
    assert kit["materials"]["windows"]["cost_per_m2"] == 70.0


def test_assign_materials_industrial():
    """Verify material assignment for Industrial preset."""
    semantic_data = {
        "rooms": [
            {"room_id": 1, "name": "Living Room", "boundary": [[0.0, 0.0], [5000.0, 0.0], [5000.0, 4000.0], [0.0, 0.0]]},
            {"room_id": 2, "name": "Kitchen", "boundary": [[5000.0, 0.0], [8000.0, 0.0], [8000.0, 4000.0], [5000.0, 0.0]]}
        ],
        "doors": [{"start": [1000.0, 0.0], "end": [1900.0, 0.0]}]
    }

    result = assign_materials(semantic_data, preset="Industrial")

    lr = result["rooms"][0]
    assert lr["materials"]["walls"]["material"] == "Exposed Brick"
    assert lr["materials"]["walls"]["cost_per_m2"] == 25.0
    assert lr["materials"]["floors"]["material"] == "Polished Concrete"
    assert lr["materials"]["floors"]["cost_per_m2"] == 32.0
    assert lr["materials"]["doors"]["material"] == "Steel Frame Door"
    assert lr["materials"]["doors"]["cost_per_unit"] == 220.0
    assert lr["materials"]["windows"]["material"] == "Metal Frame Window"
    assert lr["materials"]["windows"]["cost_per_m2"] == 90.0

    kit = result["rooms"][1]
    assert kit["materials"]["walls"]["material"] == "Raw Concrete"
    assert kit["materials"]["walls"]["cost_per_m2"] == 20.0
    assert kit["materials"]["floors"]["material"] == "Steel Plate Flooring"
    assert kit["materials"]["floors"]["cost_per_m2"] == 50.0
    assert kit["materials"]["doors"]["material"] == "Glass Insert Door"
    assert kit["materials"]["doors"]["cost_per_unit"] == 210.0
    assert kit["materials"]["windows"]["material"] == "Large Pane Window"
    assert kit["materials"]["windows"]["cost_per_m2"] == 95.0

def test_match_room_preset_compound_and_fallback():
    """Test compound room names like 'Kitchen / Dining' and fallback matching."""
    preset = STYLE_PRESETS["Luxury Minimal"]

    # Compound name matching
    matched = match_room_preset("Kitchen / Dining", preset)
    assert matched["walls"]["material"] == "Polished Concrete"

    # Case-insensitivity
    matched_lower = match_room_preset("living room", preset)
    assert matched_lower["walls"]["material"] == "White Drywall"

    # Fallback to Living Room for unlisted rooms
    matched_unknown = match_room_preset("Closet", preset)
    assert matched_unknown["walls"]["material"] == "White Drywall"


def test_invalid_preset_raises_error():
    """Verify ValueError is raised for an unknown preset name."""
    semantic_data = {"rooms": [], "doors": []}
    with pytest.raises(ValueError, match="Preset 'Nonexistent' not found"):
        assign_materials(semantic_data, preset="Nonexistent")


def test_preset_cost_estimation():
    """Verify that cost estimation correctly uses preset prices."""
    semantic_data = {
        "rooms": [
            {
                "room_id": 1,
                "name": "Living Room",
                "boundary": [[0.0, 0.0], [5000.0, 0.0], [5000.0, 4000.0], [0.0, 4000.0], [0.0, 0.0]]
            }
        ],
        "doors": [
            {"start": [1000.0, 0.0], "end": [1900.0, 0.0]}
        ]
    }

    materials_data = assign_materials(semantic_data, preset="Luxury Minimal")
    costs = estimate_cost(materials_data)

    # 20 m2 * 18.0 = 360.0 wall cost
    # 1 door * 250.0 = 250.0 door cost
    # Total = 610.0
    assert abs(costs["total_cost"] - 610.0) < 1e-6
    wall_item = next(i for i in costs["items"] if i["type"] == "wall")
    assert wall_item["material"] == "White Drywall"
    assert abs(wall_item["cost"] - 360.0) < 1e-6

    door_item = next(i for i in costs["items"] if i["type"] == "door")
    assert door_item["material"] == "Frameless Glass Door"
    assert abs(door_item["cost"] - 250.0) < 1e-6


def test_cli_preset_execution():
    """Verify material assignment script with --preset argument."""
    subprocess.run([sys.executable, "semantic_classification.py"], check=True)

    test_out = os.path.join(".output", "test_preset_materials.json")
    result = subprocess.run(
        [sys.executable, "material_assignment.py", "--preset", "Rustic", "--output", test_out],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert os.path.exists(test_out)

    with open(test_out) as f:
        data = json.load(f)

    assert data["preset"] == "Rustic"
    assert data["rooms"][0]["material"]["material"] == "Exposed Timber"


