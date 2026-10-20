"""Normalization, validation and hashing for uploaded rate sheets.

Accepts either a single-sheet document::

    {"name": ..., "metadata": {...}, "rooms": {...}}

or the engine's native envelope (exactly one preset)::

    {"presets": {"<name>": {...}}, "metadata": {...}}

Both are normalized to the engine envelope before storage so that
``load_presets`` / ``load_catalog_metadata`` keep working unchanged.
"""
import hashlib
import json
import re
from datetime import date
from typing import Any

from src.presets.schemas import PresetDocument

KNOWN_PILOT_CURRENCIES = {
    "IDR", "USD", "EUR", "GBP", "SGD", "AUD", "CNY", "JPY", "MYR", "THB", "INR", "AED",
}
SUSPICIOUS_SOURCE_TERMS = ("placeholder", "dummy", "lorem", "test data", "sample rates")
COMPONENT_KEYS = ("walls", "floors", "doors", "windows")


class PresetValidationError(ValueError):
    """Structural problem with an uploaded rate sheet."""

    def __init__(self, message: str, loc: tuple[str | int, ...] = ()):
        super().__init__(message)
        self.message = message
        self.loc = loc


class PresetTooLargeError(ValueError):
    """The uploaded sheet exceeds the configured size limit."""


def slugify(name: str) -> str:
    """Return a filesystem-safe slug for a preset name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "preset"


def normalize_payload(raw: Any, name_override: str | None = None) -> dict[str, Any]:
    """Extract ``{name, metadata, rooms}`` from either accepted document shape."""
    if not isinstance(raw, dict):
        raise PresetValidationError("rate sheet must be a JSON object")

    if "presets" in raw:
        presets = raw.get("presets")
        if not isinstance(presets, dict) or not presets:
            raise PresetValidationError("'presets' must be a non-empty object", ("presets",))
        if len(presets) != 1:
            raise PresetValidationError(
                "upload exactly one preset per file (one rate sheet per source)",
                ("presets",),
            )
        preset_name, rooms = next(iter(presets.items()))
        if name_override is None and isinstance(raw.get("name"), str) and raw["name"].strip() != preset_name:
            raise PresetValidationError(
                "top-level 'name' and the single 'presets' key disagree",
                ("name",),
            )
        name = name_override or raw.get("name") or preset_name
        metadata = raw.get("metadata")
    else:
        name = name_override or raw.get("name")
        rooms = raw.get("rooms")
        metadata = raw.get("metadata")

    if not isinstance(rooms, dict):
        raise PresetValidationError("'rooms' must be an object keyed by room type", ("rooms",))
    if metadata is None:
        raise PresetValidationError("'metadata' is required (currency, as_of, source)", ("metadata",))

    cleaned_rooms: dict[str, Any] = {}
    for key, room in rooms.items():
        if not isinstance(key, str) or not key.strip():
            raise PresetValidationError("room names must be non-empty strings", ("rooms",))
        cleaned_key = key.strip()
        if cleaned_key.casefold() in {existing.casefold() for existing in cleaned_rooms}:
            raise PresetValidationError(
                f"duplicate room type (case-insensitive): {cleaned_key}", ("rooms", cleaned_key)
            )
        cleaned_rooms[cleaned_key] = room

    return {"name": name, "metadata": metadata, "rooms": cleaned_rooms}


def parse_document(raw: Any, name_override: str | None = None) -> tuple[PresetDocument, list[str]]:
    """Validate a raw upload and return the document plus advisory warnings."""
    normalized = normalize_payload(raw, name_override=name_override)
    document = PresetDocument.model_validate(normalized)
    return document, collect_warnings(document)


def collect_warnings(document: PresetDocument) -> list[str]:
    """Advisory checks that should not block a technically valid sheet."""
    warnings: list[str] = []
    metadata = document.metadata

    if metadata.currency not in KNOWN_PILOT_CURRENCIES:
        warnings.append(
            f"currency {metadata.currency} is outside the known pilot set; confirm it is an ISO-4217 code"
        )
    if metadata.as_of > date.today():
        warnings.append("as_of is in the future; confirm the rate sheet date")
    if any(term in metadata.source.casefold() for term in SUSPICIOUS_SOURCE_TERMS):
        warnings.append("source looks like test/placeholder data; do not quote clients from it")
    if len(document.rooms) > 30:
        warnings.append("more than 30 room types supplied; verify the sheet is not a full database export")

    canonical_names = {key.strip().casefold() for key in document.rooms}
    if "living room" not in canonical_names:
        warnings.append(
            "no 'Living Room' room; unmatched CAD rooms will fall back to the first room type"
        )
    return warnings


def canonicalize(document: PresetDocument) -> dict[str, Any]:
    """Build the engine-native ``{presets, metadata}`` representation."""
    rooms: dict[str, Any] = {}
    for room_name, room in document.rooms.items():
        entry: dict[str, Any] = {}
        if room.aliases:
            entry["aliases"] = list(room.aliases)
        for component_name in COMPONENT_KEYS:
            component = getattr(room, component_name)
            if component is None:
                continue
            rate: dict[str, Any] = {"material": component.material}
            if component.cost_per_m2 is not None:
                rate["cost_per_m2"] = component.cost_per_m2
            if component.cost_per_unit is not None:
                rate["cost_per_unit"] = component.cost_per_unit
            entry[component_name] = rate
        rooms[room_name] = entry

    metadata: dict[str, Any] = {
        "currency": document.metadata.currency,
        "as_of": document.metadata.as_of.isoformat(),
        "source": document.metadata.source,
    }
    if document.metadata.note:
        metadata["note"] = document.metadata.note

    return {"presets": {document.name: rooms}, "metadata": metadata}


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic JSON representation used for content hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_version(payload: dict[str, Any], length: int = 12) -> str:
    """Content-addressed version: identical sheets share a version."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:length]


def build_preset_id(name: str, version: str) -> str:
    """Stable identifier combining a readable slug and the content hash."""
    return f"{slugify(name)}-{version}"


__all__ = [
    "PresetValidationError",
    "PresetTooLargeError",
    "normalize_payload",
    "parse_document",
    "collect_warnings",
    "canonicalize",
    "canonical_json",
    "content_version",
    "build_preset_id",
    "slugify",
]
