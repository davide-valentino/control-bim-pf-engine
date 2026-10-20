"""Validation rules for partner rate-sheet uploads."""
import copy
import json

import pytest
from pydantic import ValidationError

from src.presets.schemas import PresetDocument
from src.presets.validation import (
    PresetValidationError,
    canonicalize,
    content_version,
    normalize_payload,
    parse_document,
)
from tests.helpers import REPO_ROOT

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "idr_rate_sheet.json"


def load_sheet():
    return json.loads(FIXTURE.read_text())


def test_valid_sheet_parses_without_warnings():
    document, warnings = parse_document(load_sheet())

    assert document.name == "Bali 2026-10"
    assert document.metadata.currency == "IDR"
    assert document.metadata.as_of.isoformat() == "2026-10-01"
    assert set(document.rooms) == {"Living Room", "Bedroom", "Kitchen"}
    assert document.rooms["Living Room"].aliases == ["Ruang Tamu", "Ruang Keluarga"]
    assert warnings == []


def test_legacy_envelope_is_accepted_when_it_contains_one_preset():
    sheet = load_sheet()
    envelope = {
        "presets": {sheet["name"]: sheet["rooms"]},
        "metadata": sheet["metadata"],
    }

    document, _ = parse_document(envelope)
    assert document.name == sheet["name"]
    assert set(document.rooms) == set(sheet["rooms"])


def test_multiple_presets_in_one_file_are_rejected():
    sheet = load_sheet()
    envelope = {
        "presets": {"A": sheet["rooms"], "B": sheet["rooms"]},
        "metadata": sheet["metadata"],
    }

    with pytest.raises(PresetValidationError, match="exactly one preset"):
        normalize_payload(envelope)


def test_missing_metadata_is_rejected():
    sheet = load_sheet()
    del sheet["metadata"]

    with pytest.raises(PresetValidationError, match="metadata"):
        parse_document(sheet)


def test_unknown_component_key_is_rejected():
    sheet = load_sheet()
    sheet["rooms"]["Living Room"]["wall"] = {"material": "Typo", "cost_per_m2": 1}

    with pytest.raises(ValidationError):
        PresetDocument.model_validate(sheet)


def test_door_rate_must_be_per_unit():
    sheet = load_sheet()
    sheet["rooms"]["Living Room"]["doors"] = {"material": "Door", "cost_per_m2": 10}

    with pytest.raises(ValidationError, match="doors requires cost_per_unit"):
        PresetDocument.model_validate(sheet)


def test_area_components_must_be_per_square_metre():
    sheet = load_sheet()
    sheet["rooms"]["Living Room"]["walls"] = {"material": "Wall", "cost_per_unit": 10}

    with pytest.raises(ValidationError, match="walls requires cost_per_m2"):
        PresetDocument.model_validate(sheet)


def test_boolean_rates_are_rejected():
    sheet = load_sheet()
    sheet["rooms"]["Living Room"]["walls"]["cost_per_m2"] = True

    with pytest.raises(ValidationError, match="boolean"):
        PresetDocument.model_validate(sheet)


def test_room_without_components_is_rejected():
    sheet = load_sheet()
    sheet["rooms"]["Empty"] = {"aliases": ["Kosong"]}

    with pytest.raises(ValidationError, match="at least one of"):
        PresetDocument.model_validate(sheet)


def test_advisory_warnings_do_not_block_import():
    sheet = load_sheet()
    sheet["metadata"]["currency"] = "XXX"
    sheet["metadata"]["as_of"] = "2999-01-01"
    sheet["metadata"]["source"] = "placeholder test data"
    del sheet["rooms"]["Living Room"]

    _, warnings = parse_document(sheet)
    text = " ".join(warnings)
    assert "currency XXX" in text
    assert "as_of is in the future" in text
    assert "test/placeholder" in text
    assert "no 'Living Room'" in text


def test_canonical_form_is_key_order_independent():
    sheet = load_sheet()
    reordered = copy.deepcopy(sheet)
    reordered["rooms"] = dict(reversed(list(reordered["rooms"].items())))
    for room in reordered["rooms"].values():
        reordered_room = dict(reversed(list(room.items())))
        room.clear()
        room.update(reordered_room)

    first, _ = parse_document(sheet)
    second, _ = parse_document(reordered)

    assert canonicalize(first) == canonicalize(second)
    assert content_version(canonicalize(first)) == content_version(canonicalize(second))


def test_canonical_form_changes_when_a_rate_changes():
    sheet = load_sheet()
    changed = copy.deepcopy(sheet)
    changed["rooms"]["Living Room"]["walls"]["cost_per_m2"] = 190000

    first, _ = parse_document(sheet)
    second, _ = parse_document(changed)

    assert content_version(canonicalize(first)) != content_version(canonicalize(second))
