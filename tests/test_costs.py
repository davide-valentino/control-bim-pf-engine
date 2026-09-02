import subprocess
import json
import os
import sys


def test_cost_estimation():
    # Run the cost estimation script to regenerate output
    result = subprocess.run([sys.executable, "cost_estimation.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"Cost estimation failed: {result.stderr}"

    # Ensure output file exists
    output_path = os.path.join(".output", "costs.json")
    assert os.path.exists(output_path), "costs.json not found after running estimation"

    # Load JSON
    with open(output_path) as f:
        data = json.load(f)

    # Validate items
    assert "items" in data, "Missing 'items' key"
    assert "total_cost" in data, "Missing 'total_cost' key"

    # Expected values
    expected_wall_cost = 300.0  # 20 m2 * 15 cost_per_m2
    expected_door_cost = 120.0  # 1 door * 120 cost_per_unit
    expected_total = expected_wall_cost + expected_door_cost

    # Validate wall item
    wall_item = next((i for i in data["items"] if i["type"] == "wall"), None)
    assert wall_item is not None, "Wall item missing"
    assert abs(wall_item["cost"] - expected_wall_cost) < 1e-6, f"Unexpected wall cost: {wall_item['cost']}"

    # Validate door item
    door_item = next((i for i in data["items"] if i["type"] == "door"), None)
    assert door_item is not None, "Door item missing"
    assert abs(door_item["cost"] - expected_door_cost) < 1e-6, f"Unexpected door cost: {door_item['cost']}"

    # Validate total cost
    assert abs(data["total_cost"] - expected_total) < 1e-6, f"Unexpected total cost: {data['total_cost']}"
