"""End-to-end pricing integration: localized aliases -> IDR BOM -> summary."""
import json

import pytest

from src.pipeline.costing import estimate_cost
from src.pipeline.materials import assign_materials, run_material_assignment
from src.presets.validation import canonicalize, parse_document
from src.summary import generate_summary
from tests.helpers import REPO_ROOT

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "idr_rate_sheet.json"


def load_sheet():
    return json.loads(FIXTURE.read_text())


def canonical_catalog():
    document, _ = parse_document(load_sheet())
    return canonicalize(document)


def semantic(room_name="Living Room"):
    return {
        "rooms": [
            {
                "room_id": 1,
                "name": room_name,
                "boundary": [[0, 0], [5000, 0], [5000, 4000], [0, 4000], [0, 0]],
            }
        ],
        "doors": [
            {"type": "door", "width_mm": 900.0, "start": [1000, 0], "end": [1900, 0]}
        ],
    }


def test_assign_materials_strips_alias_metadata():
    catalog = canonical_catalog()["presets"]
    enriched = assign_materials(semantic(), preset="Bali 2026-10", catalog=catalog)

    materials = enriched["rooms"][0]["materials"]
    assert set(materials) == {"walls", "floors", "doors", "windows"}
    assert "aliases" not in materials
    assert materials["walls"]["cost_per_m2"] == 185000


@pytest.mark.parametrize(
    "room_name,floor_rate",
    [
        ("Ruang Tamu", 320000),
        ("Kamar Tidur", 280000),
        ("Dapur", 320000),
    ],
)
def test_indonesian_aliases_match_canonical_rooms(room_name, floor_rate):
    catalog = canonical_catalog()["presets"]
    enriched = assign_materials(semantic(room_name), preset="Bali 2026-10", catalog=catalog)

    assert enriched["rooms"][0]["materials"]["floors"]["cost_per_m2"] == floor_rate


def test_cost_and_summary_carry_preset_identity(tmp_path):
    catalog_path = tmp_path / "bali-2026-10.json"
    catalog_path.write_text(json.dumps(canonical_catalog(), indent=2))
    semantic_path = tmp_path / "semantic.json"
    semantic_path.write_text(json.dumps(semantic()))
    materials_path = tmp_path / "materials.json"

    identity = {
        "preset_id": "bali-2026-10-abcdef123456",
        "preset_name": "Bali 2026-10",
        "preset_version": "abcdef123456",
        "preset_origin": "upload",
    }
    enriched = run_material_assignment(
        str(semantic_path),
        str(materials_path),
        preset="Bali 2026-10",
        catalog_path=str(catalog_path),
        preset_identity=identity,
    )

    assert enriched["metadata"]["currency"] == "IDR"
    assert enriched["metadata"]["preset_id"] == identity["preset_id"]

    costs = estimate_cost(enriched)
    assert costs["currency"] == "IDR"
    assert costs["as_of"] == "2026-10-01"
    assert costs["preset"] == {
        "id": identity["preset_id"],
        "name": identity["preset_name"],
        "version": identity["preset_version"],
        "origin": identity["preset_origin"],
    }
    assert costs["total_cost"] == pytest.approx(18_890_000.0)

    report = {
        "semantic": semantic(),
        "materials": enriched,
        "costs": costs,
    }
    summary = generate_summary(report)
    assert summary["currency"] == "IDR"
    assert summary["total_cost"] == pytest.approx(18_890_000.0)
    assert summary["preset"]["id"] == identity["preset_id"]


def test_placeholder_costs_have_no_preset_block():
    enriched = assign_materials(semantic(), preset="Luxury Minimal")
    costs = estimate_cost(enriched)

    assert costs["preset"] is None
    assert costs["currency"] == "USD"
