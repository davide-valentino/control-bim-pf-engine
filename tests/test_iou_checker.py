"""Unit tests for binary mask operations and IoU computation."""
import numpy as np
from PIL import Image

from tools.iou_checker import compute_iou, load_mask_array, save_binary_mask


def test_compute_iou_identical_and_disjoint(tmp_path):
    mask_a = np.zeros((100, 100), dtype=np.uint8)
    mask_a[20:80, 20:80] = 255

    path_a = tmp_path / "mask_a.png"
    save_binary_mask(mask_a, path_a)

    # Identical
    assert compute_iou(path_a, path_a) == 1.0

    # Disjoint
    mask_b = np.zeros((100, 100), dtype=np.uint8)
    mask_b[0:10, 0:10] = 255
    path_b = tmp_path / "mask_b.png"
    save_binary_mask(mask_b, path_b)

    assert compute_iou(path_a, path_b) == 0.0


def test_compute_iou_partial_overlap(tmp_path):
    # A has 100 pixels, B has 100 pixels, overlap 50 pixels
    mask_a = np.zeros((100, 100), dtype=np.uint8)
    mask_a[0:10, 0:10] = 255  # 100 pixels

    mask_b = np.zeros((100, 100), dtype=np.uint8)
    mask_b[0:10, 5:15] = 255  # 100 pixels, overlap is [0:10, 5:10] = 50 pixels

    path_a = tmp_path / "mask_a.png"
    path_b = tmp_path / "mask_b.png"
    save_binary_mask(mask_a, path_a)
    save_binary_mask(mask_b, path_b)

    # Intersection = 50, Union = 150 -> IoU = 50/150 = 1/3
    iou = compute_iou(path_a, path_b)
    assert abs(iou - (1.0 / 3.0)) < 1e-4


def test_compute_iou_different_dimensions(tmp_path):
    mask_a = np.zeros((200, 200), dtype=np.uint8)
    mask_a[50:150, 50:150] = 255

    mask_b = np.zeros((100, 100), dtype=np.uint8)
    mask_b[25:75, 25:75] = 255

    path_a = tmp_path / "mask_a.png"
    path_b = tmp_path / "mask_b.png"
    save_binary_mask(mask_a, path_a)
    save_binary_mask(mask_b, path_b)

    iou = compute_iou(path_a, path_b)
    assert iou >= 0.95
