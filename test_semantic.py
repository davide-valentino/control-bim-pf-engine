import subprocess
import json
import os
from semantic_classification import (
    point_in_polygon,
    classify_rooms,
    normalize_label,
    polygon_centroid
)


def test_normalize_label():
    assert normalize_label("  living   room  ") == "Living Room"
    assert normalize_label("KITCHEN") == "Kitchen"
    assert normalize_label("BR") == "Bedroom"
    assert normalize_label("KITCH") == "Kitchen"
    assert normalize_label("MBR") == "Master Bedroom"
    assert normalize_label("wc") == "WC"
    assert normalize_label("%%uBEDROOM%%u") == "Bedroom"
    assert normalize_label("{\\fArial;Dining Room}") == "Dining Room"
    assert normalize_label("Utility\\PStorage") == "Utility Storage"
    assert normalize_label("") == ""


def test_point_in_polygon():
    polygon = [
        [0.0, 0.0],
        [5000.0, 0.0],
        [5000.0, 4000.0],
        [0.0, 4000.0],
        [0.0, 0.0]
    ]
    # Points inside
    assert point_in_polygon([2500.0, 2000.0], polygon) is True
    assert point_in_polygon([100.0, 100.0], polygon) is True
    # Points outside
    assert point_in_polygon([-10.0, 2000.0], polygon) is False
    assert point_in_polygon([6000.0, 2000.0], polygon) is False
    assert point_in_polygon([2500.0, 5000.0], polygon) is False


def test_polygon_centroid():
    polygon = [
        [0.0, 0.0],
        [4000.0, 0.0],
        [4000.0, 2000.0],
        [0.0, 2000.0],
        [0.0, 0.0]
    ]
    cx, cy = polygon_centroid(polygon)
    assert abs(cx - 2000.0) < 1e-3
    assert abs(cy - 1000.0) < 1e-3


def test_multi_label_handling():
    raw_data = {
        "walls": [
            {"start": [0.0, 0.0], "end": [6000.0, 0.0]},
            {"start": [6000.0, 0.0], "end": [6000.0, 4000.0]},
            {"start": [6000.0, 4000.0], "end": [0.0, 4000.0]},
            {"start": [0.0, 4000.0], "end": [0.0, 0.0]}
        ],
        "doors": [],
        "labels": [
            {"text": "KIT", "position": [1500.0, 2000.0]},
            {"text": "DIN", "position": [4500.0, 2000.0]},
            {"text": "KIT", "position": [1600.0, 2000.0]}  # Duplicate to test deduplication
        ]
    }
    result = classify_rooms(raw_data)
    assert len(result["rooms"]) == 1
    assert result["rooms"][0]["name"] == "Kitchen / Dining"
    assert result["rooms"][0]["room_id"] == 1


def test_multi_room_classification():
    # Two adjacent rooms: Room 1 [0,0] to [3000, 3000], Room 2 [3000, 0] to [6000, 3000]
    raw_data = {
        "walls": [
            # Room 1
            {"start": [0.0, 0.0], "end": [3000.0, 0.0]},
            {"start": [3000.0, 0.0], "end": [3000.0, 3000.0]},
            {"start": [3000.0, 3000.0], "end": [0.0, 3000.0]},
            {"start": [0.0, 3000.0], "end": [0.0, 0.0]},
            # Room 2
            {"start": [3000.0, 0.0], "end": [6000.0, 0.0]},
            {"start": [6000.0, 0.0], "end": [6000.0, 3000.0]},
            {"start": [6000.0, 3000.0], "end": [3000.0, 3000.0]},
            {"start": [3000.0, 3000.0], "end": [3000.0, 0.0]}
        ],
        "doors": [],
        "labels": [
            {"text": "BR", "position": [1500.0, 1500.0]},
            {"text": "BA", "position": [4500.0, 1500.0]}
        ]
    }
    result = classify_rooms(raw_data)
    assert len(result["rooms"]) == 2
    assert result["rooms"][0]["room_id"] == 1
    assert result["rooms"][0]["name"] == "Bedroom"
    assert result["rooms"][1]["room_id"] == 2
    assert result["rooms"][1]["name"] == "Bathroom"


def test_semantic_fallback_when_no_label():
    raw_data = {
        "walls": [
            {"start": [0.0, 0.0], "end": [5000.0, 0.0]},
            {"start": [5000.0, 0.0], "end": [5000.0, 4000.0]},
            {"start": [5000.0, 4000.0], "end": [0.0, 4000.0]},
            {"start": [0.0, 4000.0], "end": [0.0, 0.0]}
        ],
        "doors": [],
        "labels": []
    }
    result = classify_rooms(raw_data)
    assert len(result["rooms"]) == 1
    assert result["rooms"][0]["name"] == "Room 1"
    assert result["rooms"][0]["room_id"] == 1


def test_semantic_classification():
    # Run the semantic classification script to regenerate output
    result = subprocess.run(["python", "semantic_classification.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Semantic classification failed: {result.stderr}"

    # Ensure output file exists
    output_path = os.path.join(".output", "semantic.json")
    assert os.path.exists(output_path), "semantic.json not found after running classification"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Expected room boundary and door
    expected_boundary = [
        [0.0, 0.0],
        [5000.0, 0.0],
        [5000.0, 4000.0],
        [0.0, 4000.0],
        [0.0, 0.0]
    ]
    expected_door = {"start": [1000.0, 0.0], "end": [1900.0, 0.0]}

    # Validate rooms
    assert "rooms" in data, "Missing 'rooms' key"
    assert len(data["rooms"]) == 1, f"Expected 1 room, got {len(data['rooms'])}"
    room = data["rooms"][0]
    assert room["name"] == "Living Room", f"Room name mismatch: expected 'Living Room', got {room.get('name')}"
    assert room["boundary"] == expected_boundary, f"Room boundary mismatch: expected {expected_boundary}, got {room['boundary']}"

    # Validate doors
    assert "doors" in data, "Missing 'doors' key"
    assert len(data["doors"]) == 1, f"Expected 1 door, got {len(data['doors'])}"
    assert data["doors"][0] == expected_door, f"Door mismatch: expected {expected_door}, got {data['doors'][0]}"
