"""Unit tests for geometry utilities."""
import pytest
from src.geometry import polygon_area, polygon_centroid, point_in_polygon


def test_polygon_area_rectangle():
    boundary = [
        [0.0, 0.0],
        [5000.0, 0.0],
        [5000.0, 4000.0],
        [0.0, 4000.0],
        [0.0, 0.0]
    ]
    # Area = 5000 * 4000 = 20,000,000 mm^2
    assert abs(polygon_area(boundary) - 20_000_000.0) < 1e-6


def test_polygon_area_empty_and_small():
    assert polygon_area([]) == 0.0
    assert polygon_area([[0.0, 0.0], [1.0, 1.0]]) == 0.0


def test_polygon_centroid():
    boundary = [
        [0.0, 0.0],
        [4000.0, 0.0],
        [4000.0, 2000.0],
        [0.0, 2000.0],
        [0.0, 0.0]
    ]
    cx, cy = polygon_centroid(boundary)
    assert abs(cx - 2000.0) < 1e-3
    assert abs(cy - 1000.0) < 1e-3


def test_point_in_polygon():
    polygon = [
        [0.0, 0.0],
        [5000.0, 0.0],
        [5000.0, 4000.0],
        [0.0, 4000.0],
        [0.0, 0.0]
    ]
    # Inside
    assert point_in_polygon([2500.0, 2000.0], polygon) is True
    assert point_in_polygon([100.0, 100.0], polygon) is True
    # Outside
    assert point_in_polygon([-10.0, 2000.0], polygon) is False
    assert point_in_polygon([6000.0, 2000.0], polygon) is False
    assert point_in_polygon([2500.0, 5000.0], polygon) is False
    # Empty
    assert point_in_polygon([0, 0], []) is False
