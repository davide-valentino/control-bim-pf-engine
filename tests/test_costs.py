import json

from tests.helpers import run_script


def test_cost_estimation(canonical_workspace):
    # Run the cost estimation script inside an isolated workspace
    result = run_script("cost_estimation.py", canonical_workspace)
    assert result.returncode == 0, f"Cost estimation failed: {result.stderr}"

    output_path = canonical_workspace / ".output" / "costs.json"
    assert output_path.exists(), "costs.json not found after running estimation"

    with open(output_path) as f:
        data = json.load(f)

    # Validate items
    assert "items" in data, "Missing 'items' key"
    assert "total_cost" in data, "Missing 'total_cost' key"

    # Expected values for a 5m x 4m room with a 3m default wall height:
    # wall = (2 * (5 + 4)) m perimeter * 3 m * 15/m2 = 810
    # floor = 20 m2 * 25/m2 = 500
    # door = 1 clustered opening * 120 = 120
    expected_wall_cost = 810.0
    expected_floor_cost = 500.0
    expected_door_cost = 120.0
    expected_total = expected_wall_cost + expected_floor_cost + expected_door_cost

    wall_item = next((i for i in data["items"] if i["type"] == "wall"), None)
    assert wall_item is not None, "Wall item missing"
    assert abs(wall_item["area_m2"] - 54.0) < 1e-6, f"Unexpected wall area: {wall_item['area_m2']}"
    assert abs(wall_item["cost"] - expected_wall_cost) < 1e-6, f"Unexpected wall cost: {wall_item['cost']}"

    floor_item = next((i for i in data["items"] if i["type"] == "floor"), None)
    assert floor_item is not None, "Floor item missing"
    assert abs(floor_item["area_m2"] - 20.0) < 1e-6, f"Unexpected floor area: {floor_item['area_m2']}"
    assert abs(floor_item["cost"] - expected_floor_cost) < 1e-6, f"Unexpected floor cost: {floor_item['cost']}"

    door_item = next((i for i in data["items"] if i["type"] == "door"), None)
    assert door_item is not None, "Door item missing"
    assert abs(door_item["cost"] - expected_door_cost) < 1e-6, f"Unexpected door cost: {door_item['cost']}"

    # Validate total cost
    assert abs(data["total_cost"] - expected_total) < 1e-6, f"Unexpected total cost: {data['total_cost']}"

    # Validate rate provenance and quantity assumptions are exported
    assert data["currency"] == "USD"
    assert data["as_of"]
    assert "placeholder" in data["rate_source"].lower()
    assert data["assumptions"]["wall_height_m"] == 3.0
    assert data["assumptions"]["wall_quantity_basis"]
