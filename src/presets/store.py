"""Immutable, content-addressed storage for uploaded rate sheets.

Layout::

    artifacts/presets/
      registry.json
      <slug>-<sha256[:12]>.json

Sheets are never mutated: re-uploading identical content is idempotent, and
changed content produces a new version and a new ``presetId``. Jobs record the
exact version they used, and copy the sheet into their artifact directory.
"""
import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.presets.validation import (
    PresetTooLargeError,
    canonical_json,
    canonicalize,
    content_version,
    build_preset_id,
    parse_document,
    slugify,
)

DEFAULT_BUILTIN_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "presets.json"
DEFAULT_MAX_BYTES = 2 * 1024 * 1024


class PresetNotFound(LookupError):
    """No preset matches the requested id or name."""


class PresetConflict(ValueError):
    """The upload conflicts with an existing preset."""


class PresetDisabled(ValueError):
    """The requested preset has been soft-disabled."""


class PresetBuiltinProtected(ValueError):
    """Built-in presets are read-only."""


@dataclass(frozen=True)
class PresetRecord:
    preset_id: str
    name: str
    slug: str
    version: str
    file: str
    currency: str
    as_of: str
    source: str
    origin: str
    room_types: list[str] = field(default_factory=list)
    item_count: int = 0
    warnings: list[str] = field(default_factory=list)
    created_at: str | None = None
    disabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "presetId": self.preset_id,
            "name": self.name,
            "slug": self.slug,
            "version": self.version,
            "file": self.file,
            "currency": self.currency,
            "asOf": self.as_of,
            "source": self.source,
            "origin": self.origin,
            "roomTypes": list(self.room_types),
            "itemCount": self.item_count,
            "warnings": list(self.warnings),
            "createdAt": self.created_at,
            "disabled": self.disabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PresetRecord":
        return cls(
            preset_id=data["presetId"],
            name=data["name"],
            slug=data.get("slug") or slugify(data["name"]),
            version=data.get("version", "builtin"),
            file=data.get("file", ""),
            currency=data.get("currency", ""),
            as_of=data.get("asOf", ""),
            source=data.get("source", ""),
            origin=data.get("origin", "upload"),
            room_types=list(data.get("roomTypes", [])),
            item_count=int(data.get("itemCount", 0)),
            warnings=list(data.get("warnings", [])),
            created_at=data.get("createdAt"),
            disabled=bool(data.get("disabled", False)),
        )


@dataclass(frozen=True)
class ResolvedPreset:
    preset_id: str
    name: str
    version: str
    origin: str
    currency: str
    as_of: str
    source: str
    file_path: Path | None
    catalog: dict[str, Any]
    metadata: dict[str, Any]

    def identity(self) -> dict[str, str]:
        """Fields merged into materials/costs metadata for auditability."""
        return {
            "preset_id": self.preset_id,
            "preset_name": self.name,
            "preset_version": self.version,
            "preset_origin": self.origin,
        }


class PresetStore:
    """Filesystem-backed preset registry with immutable, hashed versions."""

    def __init__(self, root: str | Path, builtin_path: str | Path | None = None,
                 max_bytes: int | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.root / "registry.json"
        self.builtin_path = Path(builtin_path) if builtin_path else DEFAULT_BUILTIN_PATH
        self.max_bytes = int(max_bytes if max_bytes is not None else
                             (os.getenv("MAX_PRESET_UPLOAD_BYTES") or DEFAULT_MAX_BYTES))
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ built-ins

    def _load_builtin_document(self) -> dict[str, Any]:
        if not self.builtin_path.exists():
            return {"presets": {}, "metadata": {}}
        with open(self.builtin_path) as handle:
            return json.load(handle)

    def _builtin_records(self) -> list[PresetRecord]:
        document = self._load_builtin_document()
        metadata = document.get("metadata", {})
        records = []
        for name, rooms in document.get("presets", {}).items():
            records.append(PresetRecord(
                preset_id=f"builtin:{slugify(name)}",
                name=name,
                slug=slugify(name),
                version="builtin",
                file=str(self.builtin_path),
                currency=metadata.get("currency", ""),
                as_of=str(metadata.get("as_of", "")),
                source=metadata.get("source", ""),
                origin="builtin",
                room_types=list(rooms.keys()),
                item_count=sum(
                    len([key for key in room if key in ("walls", "floors", "doors", "windows")])
                    for room in rooms.values() if isinstance(room, dict)
                ),
                warnings=[],
                created_at=None,
                disabled=False,
            ))
        return records

    # ------------------------------------------------------------------ registry

    def _load_registry(self) -> list[PresetRecord]:
        if not self.registry_path.exists():
            return []
        try:
            with open(self.registry_path) as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise PresetConflict(f"preset registry is unreadable: {exc}") from exc
        return [PresetRecord.from_dict(item) for item in data.get("presets", [])]

    def _write_registry(self, records: list[PresetRecord]) -> None:
        payload = {"version": 1, "presets": [record.to_dict() for record in records]}
        temp_path = self.registry_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2))
        os.replace(temp_path, self.registry_path)

    def _write_sheet(self, preset_id: str, payload: dict[str, Any]) -> Path:
        path = self.root / f"{preset_id}.json"
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        os.replace(temp_path, path)
        return path

    # ------------------------------------------------------------------ commands

    def save(self, raw: Any, name_override: str | None = None) -> tuple[PresetRecord, bool]:
        """Validate and persist a rate sheet. Returns ``(record, created)``."""
        document, warnings = parse_document(raw, name_override=name_override)
        payload = canonicalize(document)
        serialized = canonical_json(payload)
        if len(serialized.encode("utf-8")) > self.max_bytes:
            raise PresetTooLargeError(
                f"rate sheet exceeds the {self.max_bytes // 1024} KB limit")

        builtin_names = {record.name.casefold() for record in self._builtin_records()}
        if document.name.casefold() in builtin_names:
            raise PresetConflict(
                f"'{document.name}' is a built-in preset name; choose a distinct sheet name "
                "(for example 'Bali 2026-10')")

        version = content_version(payload)
        preset_id = build_preset_id(document.name, version)

        with self._lock:
            records = self._load_registry()
            for existing in records:
                if existing.preset_id == preset_id:
                    return existing, False

            path = self._write_sheet(preset_id, payload)
            record = PresetRecord(
                preset_id=preset_id,
                name=document.name,
                slug=slugify(document.name),
                version=version,
                file=str(path),
                currency=document.metadata.currency,
                as_of=document.metadata.as_of.isoformat(),
                source=document.metadata.source,
                origin="upload",
                room_types=list(document.rooms.keys()),
                item_count=sum(
                    1
                    for room in document.rooms.values()
                    for component in (room.walls, room.floors, room.doors, room.windows)
                    if component is not None
                ),
                warnings=warnings,
                created_at=datetime.now(timezone.utc).isoformat(),
                disabled=False,
            )
            records.append(record)
            self._write_registry(records)
            return record, True

    def list_records(self, include_disabled: bool = True) -> list[PresetRecord]:
        with self._lock:
            records = self._load_registry()
        if not include_disabled:
            records = [record for record in records if not record.disabled]
        return sorted(records, key=lambda record: record.created_at or "", reverse=True)

    def get_record(self, preset_id: str) -> PresetRecord:
        if preset_id.startswith("builtin:"):
            for record in self._builtin_records():
                if record.preset_id == preset_id:
                    return record
            raise PresetNotFound(f"unknown built-in preset '{preset_id}'")

        with self._lock:
            for record in self._load_registry():
                if record.preset_id == preset_id:
                    return record
        raise PresetNotFound(f"unknown preset '{preset_id}'")

    def disable(self, preset_id: str) -> PresetRecord:
        if preset_id.startswith("builtin:") or any(
                record.preset_id == preset_id for record in self._builtin_records()):
            raise PresetBuiltinProtected("built-in presets cannot be disabled")

        with self._lock:
            records = self._load_registry()
            for index, record in enumerate(records):
                if record.preset_id == preset_id:
                    if record.disabled:
                        return record
                    updated = PresetRecord(**{**record.__dict__, "disabled": True})
                    records[index] = updated
                    self._write_registry(records)
                    return updated
        raise PresetNotFound(f"unknown preset '{preset_id}'")

    def resolve(self, preset_id: str | None = None, name: str | None = None) -> ResolvedPreset:
        """Resolve a preset reference into a loadable catalog.

        Precedence: explicit ``preset_id`` -> ``name`` (built-in first, then the
        newest enabled upload) -> the default built-in preset.
        """
        if preset_id:
            record = self.get_record(preset_id)
            if record.disabled:
                raise PresetDisabled(f"preset '{record.name}' ({preset_id}) is disabled")
            resolved = self._load_record(record)
            if name and name.strip().casefold() != record.name.casefold():
                raise PresetConflict(
                    f"presetId '{preset_id}' is '{record.name}', not '{name}'")
            return resolved

        builtins = self._builtin_records()
        if name:
            target = name.strip().casefold()
            for record in builtins:
                if record.name.casefold() == target:
                    return self._load_record(record)
            candidates = [
                record for record in self.list_records(include_disabled=False)
                if record.name.casefold() == target
            ]
            if candidates:
                return self._load_record(candidates[0])
            available = ", ".join(record.name for record in builtins)
            raise PresetNotFound(
                f"unknown preset '{name}'. Built-in presets: {available}. "
                "Uploaded sheets must be referenced by name or presetId.")

        for record in builtins:
            if record.name == "Luxury Minimal":
                return self._load_record(record)
        if builtins:
            return self._load_record(builtins[0])
        raise PresetNotFound("no built-in presets are available")

    def _load_record(self, record: PresetRecord) -> ResolvedPreset:
        path = Path(record.file) if record.file else None
        if path is None or not path.exists():
            raise PresetNotFound(f"rate sheet file for '{record.name}' is missing")
        with open(path) as handle:
            document = json.load(handle)
        catalog = document.get("presets", {})
        if record.origin != "builtin":
            catalog = {record.name: catalog.get(record.name, next(iter(catalog.values()), {}))}
        metadata = dict(document.get("metadata", {}))
        return ResolvedPreset(
            preset_id=record.preset_id,
            name=record.name,
            version=record.version,
            origin=record.origin,
            currency=metadata.get("currency", record.currency),
            as_of=str(metadata.get("as_of", record.as_of)),
            source=metadata.get("source", record.source),
            file_path=path,
            catalog=catalog,
            metadata=metadata,
        )

    # ------------------------------------------------------------------ views

    def list_all(self) -> dict[str, list[PresetRecord]]:
        return {
            "builtin": self._builtin_records(),
            "uploaded": self.list_records(),
        }

    def detail(self, preset_id: str) -> tuple[PresetRecord, dict[str, Any]]:
        record = self.get_record(preset_id)
        resolved = self._load_record(record)
        document = {
            "name": resolved.name,
            "metadata": resolved.metadata,
            "rooms": resolved.catalog.get(resolved.name, {}),
        }
        return record, document


__all__ = [
    "PresetStore",
    "PresetRecord",
    "ResolvedPreset",
    "PresetNotFound",
    "PresetConflict",
    "PresetDisabled",
    "PresetBuiltinProtected",
]
