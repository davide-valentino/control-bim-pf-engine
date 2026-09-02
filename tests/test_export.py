import os
from src.pipeline.export import export_csv_summary


def test_export_csv_summary():
    report = {
        "summary": {
            "rooms_breakdown": [
                {
                    "room_id": 1,
                    "name": "Living Room",
                    "area_m2": 20.0,
                    "materials": {
                        "wall": {"material": "Drywall 12mm", "cost": 300.0},
                        "door": {"material": "Oak Door", "cost": 120.0}
                    },
                    "total_cost": 420.0
                }
            ]
        }
    }
    out_path = ".output/test_summary.csv"
    res = export_csv_summary(report, out_path)
    assert os.path.exists(out_path)
    with open(out_path) as f:
        content = f.read()
    assert "Room ID,Room Name,Area (m2)" in content
    assert '1,"Living Room",20.00,"Drywall 12mm",300.00,"Oak Door",120.00,420.00' in content
