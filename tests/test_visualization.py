import json
import os
from src.visualization import generate_svg


def test_visualization_svg_generation():
    test_data = {
        "rooms": [
            {
                "room_id": 1,
                "name": "Living Room",
                "boundary": [
                    [0.0, 0.0],
                    [5000.0, 0.0],
                    [5000.0, 4000.0],
                    [0.0, 4000.0],
                    [0.0, 0.0]
                ]
            },
            {
                "room_id": 2,
                "name": "Kitchen / Dining",
                "boundary": [
                    [5000.0, 0.0],
                    [8000.0, 0.0],
                    [8000.0, 4000.0],
                    [5000.0, 4000.0],
                    [5000.0, 0.0]
                ]
            }
        ],
        "doors": [
            {"start": [1000.0, 0.0], "end": [1900.0, 0.0]}
        ]
    }
    output_path = ".output/test_visualization.svg"
    svg_content = generate_svg(test_data, output_path)

    assert os.path.exists(output_path), "SVG output file was not created"
    assert "<svg" in svg_content, "Missing <svg> tag"
    assert "</svg>" in svg_content, "Missing </svg> closing tag"
    assert "Living Room" in svg_content, "Missing 'Living Room' label in SVG"
    assert "Kitchen / Dining" in svg_content, "Missing 'Kitchen / Dining' label in SVG"
    assert "20.0 m²" in svg_content, "Missing 20.0 m² area text"
    assert "12.0 m²" in svg_content, "Missing 12.0 m² area text"
    assert "polygon" in svg_content, "Missing polygon elements"
    assert "line" in svg_content, "Missing door line element"
