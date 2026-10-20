"""Pydantic schemas for partner-uploaded rate sheets.

A rate sheet is deliberately strict: unknown keys are rejected so a typo in a
column name cannot silently fall back to placeholder pricing.
"""
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PositiveFloat = Annotated[float, Field(gt=0)]


class RateMetadata(BaseModel):
    """Provenance for a rate sheet. Every uploaded sheet must carry all three."""

    model_config = ConfigDict(extra="forbid")

    currency: str = Field(min_length=3, max_length=3, description="ISO-4217 code, e.g. IDR")
    as_of: date = Field(description="Date the rates are valid from (YYYY-MM-DD)")
    source: str = Field(min_length=3, max_length=200, description="Who supplied these rates")
    note: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str) -> str:
        code = value.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("currency must be a 3-letter ISO-4217 code (e.g. IDR)")
        return code


class MaterialRate(BaseModel):
    """One material line: a label plus exactly one cost basis."""

    model_config = ConfigDict(extra="forbid")

    material: str = Field(min_length=1, max_length=160)
    cost_per_m2: PositiveFloat | None = None
    cost_per_unit: PositiveFloat | None = None

    @field_validator("cost_per_m2", "cost_per_unit", mode="before")
    @classmethod
    def _reject_booleans(cls, value):
        if isinstance(value, bool):
            raise ValueError("rate must be a positive number, not a boolean")
        return value

    @field_validator("material")
    @classmethod
    def _strip_material(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("material must not be blank")
        return stripped


class RoomRates(BaseModel):
    """Rates for one canonical room type, with optional localized aliases."""

    model_config = ConfigDict(extra="forbid")

    aliases: list[str] = Field(default_factory=list, max_length=20)
    walls: MaterialRate | None = None
    floors: MaterialRate | None = None
    doors: MaterialRate | None = None
    windows: MaterialRate | None = None

    @field_validator("aliases")
    @classmethod
    def _clean_aliases(cls, aliases: list[str]) -> list[str]:
        cleaned: list[str] = []
        for alias in aliases:
            text = alias.strip()
            if text and text.casefold() not in {item.casefold() for item in cleaned}:
                cleaned.append(text)
        return cleaned

    @model_validator(mode="after")
    def _validate_component_rates(self):
        components = {
            "walls": self.walls,
            "floors": self.floors,
            "doors": self.doors,
            "windows": self.windows,
        }
        if not any(components.values()):
            raise ValueError("room must define at least one of walls, floors, doors, windows")

        for name in ("walls", "floors", "windows"):
            component = components[name]
            if component is None:
                continue
            if component.cost_per_m2 is None:
                raise ValueError(f"{name} requires cost_per_m2")
            if component.cost_per_unit is not None:
                raise ValueError(f"{name} must not define cost_per_unit")

        if self.doors is not None:
            if self.doors.cost_per_unit is None:
                raise ValueError("doors requires cost_per_unit")
            if self.doors.cost_per_m2 is not None:
                raise ValueError("doors must not define cost_per_m2")
        return self


class PresetDocument(BaseModel):
    """A single partner rate sheet."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    metadata: RateMetadata
    rooms: dict[str, RoomRates]

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("preset name must not be blank")
        return stripped

    @model_validator(mode="after")
    def _validate_rooms(self):
        if not self.rooms:
            raise ValueError("at least one room type is required")
        if len(self.rooms) > 50:
            raise ValueError("a rate sheet may define at most 50 room types")

        seen: dict[str, str] = {}
        for key in self.rooms:
            normalized = key.strip().casefold()
            if not normalized:
                raise ValueError("room names must not be blank")
            if len(key.strip()) > 60:
                raise ValueError(f"room name too long: {key[:40]}...")
            if normalized in seen:
                raise ValueError(f"duplicate room type (case-insensitive): {seen[normalized]} / {key}")
            seen[normalized] = key
        return self
