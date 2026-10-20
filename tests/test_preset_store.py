"""Immutable, content-addressed rate-sheet storage."""
import copy
import json

import pytest

from src.presets.store import (
    PresetBuiltinProtected,
    PresetConflict,
    PresetDisabled,
    PresetNotFound,
    PresetStore,
)
from src.presets.validation import PresetTooLargeError
from tests.helpers import REPO_ROOT

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "idr_rate_sheet.json"


def load_sheet():
    return json.loads(FIXTURE.read_text())


@pytest.fixture()
def store(tmp_path):
    return PresetStore(root=tmp_path / "presets")


def test_save_is_idempotent_for_identical_content(store):
    first, created_first = store.save(load_sheet())
    second, created_second = store.save(load_sheet())

    assert created_first is True
    assert created_second is False
    assert first.preset_id == second.preset_id
    assert first.preset_id.startswith("bali-2026-10-")
    assert len(store.list_records()) == 1


def test_changed_content_creates_a_new_version(store):
    first, _ = store.save(load_sheet())

    changed = load_sheet()
    changed["rooms"]["Living Room"]["walls"]["cost_per_m2"] = 190000
    second, created = store.save(changed)

    assert created is True
    assert second.preset_id != first.preset_id
    assert {record.preset_id for record in store.list_records()} == {
        first.preset_id,
        second.preset_id,
    }


def test_existing_version_file_is_never_overwritten(store):
    record, _ = store.save(load_sheet())
    path = store.root / f"{record.preset_id}.json"
    before = path.read_text()

    store.save(load_sheet())
    assert path.read_text() == before


def test_builtin_names_are_protected(store):
    sheet = load_sheet()
    sheet["name"] = "luxury minimal"

    with pytest.raises(PresetConflict, match="built-in"):
        store.save(sheet)


def test_resolve_by_id_name_and_default(store):
    record, _ = store.save(load_sheet())

    by_id = store.resolve(preset_id=record.preset_id)
    by_name = store.resolve(name="Bali 2026-10")
    default = store.resolve()

    assert by_id.preset_id == record.preset_id
    assert by_name.preset_id == record.preset_id
    assert by_id.currency == "IDR"
    assert "Bali 2026-10" in by_id.catalog
    assert "Living Room" in by_id.catalog["Bali 2026-10"]
    assert default.name == "Luxury Minimal"
    assert default.origin == "builtin"
    assert default.currency == "USD"


def test_newest_upload_wins_when_resolving_by_name(store):
    old, _ = store.save(load_sheet())
    changed = load_sheet()
    changed["rooms"]["Living Room"]["walls"]["cost_per_m2"] = 190000
    new, _ = store.save(changed)

    assert store.resolve(name="Bali 2026-10").preset_id == new.preset_id
    assert store.resolve(preset_id=old.preset_id).preset_id == old.preset_id


def test_disable_hides_version_from_name_resolution(store):
    record, _ = store.save(load_sheet())

    disabled = store.disable(record.preset_id)
    assert disabled.disabled is True

    with pytest.raises(PresetNotFound):
        store.resolve(name="Bali 2026-10")
    with pytest.raises(PresetDisabled):
        store.resolve(preset_id=record.preset_id)


def test_builtin_presets_cannot_be_disabled(store):
    with pytest.raises(PresetBuiltinProtected):
        store.disable("builtin:luxury-minimal")


def test_unknown_presets_raise_not_found(store):
    with pytest.raises(PresetNotFound):
        store.resolve(preset_id="missing-000000000000")
    with pytest.raises(PresetNotFound):
        store.resolve(name="No Such Sheet")


def test_oversized_sheet_is_rejected(tmp_path):
    store = PresetStore(root=tmp_path / "presets", max_bytes=50)

    with pytest.raises(PresetTooLargeError):
        store.save(load_sheet())


def test_registry_survives_store_restart(store, tmp_path):
    record, _ = store.save(load_sheet())
    reopened = PresetStore(root=store.root)

    assert reopened.get_record(record.preset_id).name == "Bali 2026-10"
    assert reopened.resolve(preset_id=record.preset_id).name == "Bali 2026-10"


def test_identity_is_stable_and_complete(store):
    record, _ = store.save(load_sheet())
    resolved = store.resolve(preset_id=record.preset_id)

    assert resolved.identity() == {
        "preset_id": record.preset_id,
        "preset_name": "Bali 2026-10",
        "preset_version": record.version,
        "preset_origin": "upload",
    }
