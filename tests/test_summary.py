"""Unit tests for summary aggregation."""
import pytest
from src.summary import generate_summary


def test_generate_summary():
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
            ],
            "total_cost": 420.0
        }
    }

    summary = generate_summary(report)
    assert summary["rooms"] == 1
    assert summary["doors"] == 1
    assert abs(summary["wall_area_m2"] - 20.0) < 1e-6
    assert abs(summary["total_cost"] - 420.0) < 1e-6
    assert "Drywall 12mm" in summary["materials_breakdown"]
    assert "Oak Door" in summary["materials_breakdown"]
    assert len(summary["rooms_breakdown"]) == 1
