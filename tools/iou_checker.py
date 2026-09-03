"""Binary mask normalization and silhouette intersection-over-union calculation."""
import io
import os
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from PIL import Image


def load_mask_array(source, threshold=128):
    """Load an image source as a boolean binary numpy array."""
    if isinstance(source, np.ndarray):
        if source.dtype == bool:
            return source
        return source >= threshold

    if isinstance(source, Image.Image):
        img = source.convert("L")
    elif isinstance(source, (str, Path)):
        src_str = str(source)
        if src_str.startswith("http://") or src_str.startswith("https://"):
            with urlopen(src_str, timeout=60) as resp:
                img = Image.open(io.BytesIO(resp.read())).convert("L")
        elif src_str.startswith("data:"):
            import base64
            encoded = src_str.split(",", 1)[1]
            img = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("L")
        else:
            img = Image.open(src_str).convert("L")
    elif isinstance(source, bytes):
        img = Image.open(io.BytesIO(source)).convert("L")
    else:
        raise ValueError(f"Unsupported mask source type: {type(source)}")

    arr = np.asarray(img)
    mask = arr >= threshold
    if mask.sum() == 0 and arr.max() > 0:
        mask = arr > 0
    return mask


def to_binary_mask(source, threshold=128):
    """Convert source to boolean binary mask array."""
    return load_mask_array(source, threshold)


def save_binary_mask(source, output_path, threshold=128):
    """Save binary mask array as a 1-channel PNG."""
    mask = load_mask_array(source, threshold)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    Image.fromarray((mask * 255).astype(np.uint8), mode="L").save(output_path)
    return output_path


def compute_iou(mask_a_source, mask_b_source, threshold=128):
    """Compute Intersection over Union (IoU) between two binary masks.

    Returns float in [0.0, 1.0].
    """
    mask_a = load_mask_array(mask_a_source, threshold)
    mask_b = load_mask_array(mask_b_source, threshold)

    if mask_a.shape != mask_b.shape:
        # Resize mask_b to match mask_a dimensions
        img_b = Image.fromarray((mask_b * 255).astype(np.uint8), mode="L")
        img_b_resized = img_b.resize((mask_a.shape[1], mask_a.shape[0]), Image.NEAREST)
        mask_b = np.asarray(img_b_resized) >= threshold

    intersection = np.logical_and(mask_a, mask_b).sum()
    union = np.logical_or(mask_a, mask_b).sum()

    if union == 0:
        return 1.0 if intersection == 0 else 0.0

    return float(intersection / union)