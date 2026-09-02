"""Unit tests for room breakdown logic."""
import pytest
from src.breakdown import generate_rooms_breakdown


def test_generate_rooms_breakdown():
    report = {
        "semantic": {
            "rooms": [
                {
                    "name": "Living Room",
                    "boundary": [
                        [0.0, 0.0],
                        [5000.0, 0.0],
                        [5000.0, 4000.0],
                        [0.0, 4000.0],
                        [0.0, 0.0]
                    ]
                }
            ],
            "doors": [{"start": [1000.0, 0.0], "end": [1900.0, 0.0]}]
        },
        "costs": {
            "items": [
                {
                    "type": "wall",
                    "room_id": 1,
                    "material": "Drywall 12mm",
                    "area_m2": 20.0,
                    "cost": 300.0
                },
                {
                    "type": "door",
                    "material": "Oak Door",
                    "count": 1,
                    "cost": 120.0
                }
            ]
        }
    }

    breakdown = generate_rooms_breakdown(report)
    assert len(breakdown) == 1
    room = breakdown[0]
    assert room["room_id"] == 1
    assert room["name"] == "Living Room"
    assert abs(room["area_m2"] - 20.0) < 1e-6
    assert room["materials"]["wall"]["material"] == "Drywall 12mm"
    assert abs(room["materials"]["wall"]["cost"] - 300.0) < 1e-6
    assert room["materials"]["door"]["material"] == "Oak Door"
    assert room["materials"]["door"]["count"] == 1
    assert abs(room["materials"]["door"]["cost"] - 120.0) < 1e-6
    assert abs(room["total_cost"] - 420.0) < 1e-6
