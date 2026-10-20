"""Unit tests for summary aggregation."""
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
            "doors": [{"start": [1000.0, 0.0], "end": [1900.0, 0.0], "type": "door"}]
        },
        "costs": {
            "items": [
                {
                    "type": "wall",
                    "room_id": 1,
                    "material": "Drywall 12mm",
                    "area_m2": 54.0,
                    "cost": 810.0
                },
                {
                    "type": "floor",
                    "room_id": 1,
                    "material": "Ceramic Tile",
                    "area_m2": 20.0,
                    "cost": 500.0
                },
                {
                    "type": "door",
                    "material": "Oak Door",
                    "count": 1,
                    "cost": 120.0
                }
            ],
            "total_cost": 1430.0,
            "currency": "USD",
            "as_of": "2026-08-31",
            "rate_source": "placeholder benchmark rates",
        }
    }

    summary = generate_summary(report)
    assert summary["rooms"] == 1
    assert summary["doors"] == 1
    assert summary["windows"] == 0
    assert abs(summary["wall_area_m2"] - 54.0) < 1e-6
    assert abs(summary["floor_area_m2"] - 20.0) < 1e-6
    assert abs(summary["total_cost"] - 1430.0) < 1e-6
    assert summary["currency"] == "USD"
    assert "Drywall 12mm" in summary["materials_breakdown"]
    assert "Ceramic Tile" in summary["materials_breakdown"]
    assert "Oak Door" in summary["materials_breakdown"]
    assert len(summary["rooms_breakdown"]) == 1
