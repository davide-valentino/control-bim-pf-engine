"""Debug control map generation, normalization, and mask persistence."""
import io
import os
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import scipy.ndimage as ndi
from PIL import Image
from skimage.feature import canny


def load_image(source):
    """Load an image from a filepath, URL, bytes, or PIL Image."""
    if isinstance(source, Image.Image):
        return source
    if isinstance(source, (str, Path)):
        src_str = str(source)
        if src_str.startswith("http://") or src_str.startswith("https://"):
            with urlopen(src_str, timeout=60) as resp:
                return Image.open(io.BytesIO(resp.read()))
        elif src_str.startswith("data:"):
            import base64
            encoded = src_str.split(",", 1)[1]
            return Image.open(io.BytesIO(base64.b64decode(encoded)))
        else:
            return Image.open(src_str)
    if isinstance(source, bytes):
        return Image.open(io.BytesIO(source))
    raise ValueError(f"Unsupported image source type: {type(source)}")


def generate_canny_control_map(image_source, output_path=None, low_threshold=50, high_threshold=150, sigma=1.0):
    """Generate a Canny edge control map from an image and optionally save it."""
    pil_img = load_image(image_source).convert("L")
    arr = np.asarray(pil_img, dtype=np.float32) / 255.0

    low_t = max(0.001, min(0.999, float(low_threshold) / 255.0))
    high_t = max(low_t + 0.001, min(1.0, float(high_threshold) / 255.0))

    edges = canny(arr, sigma=sigma, low_threshold=low_t, high_threshold=high_t)
    edge_img = Image.fromarray((edges * 255).astype(np.uint8), mode="L")

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        edge_img.save(output_path)
    return edge_img


def generate_control_map(image_source, output_path, input_type="interior", low_threshold=50, high_threshold=150):
    """Generate and persist a canonical debug control map appropriate for the input type."""
    img = load_image(image_source).convert("L")
    arr = np.asarray(img)

    # For interior depth conditioning from binary silhouettes, preserve structure
    if input_type == "interior" and len(np.unique(arr)) <= 4:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        img.save(output_path)
        return img

    return generate_canny_control_map(
        image_source=image_source,
        output_path=output_path,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
        sigma=1.0,
    )


def save_control_map_and_mask(control_map_source, out_control_path, out_mask_path, threshold=128):
    """Persist the control map image and its binary threshold silhouette mask."""
    img = load_image(control_map_source).convert("L")
    os.makedirs(os.path.dirname(out_control_path) or ".", exist_ok=True)
    img.save(out_control_path)

    arr = np.asarray(img)

    # Determine polarity: check if image has a white canvas / inverted background (e.g. provider canny output)
    border_pixels = np.concatenate([arr[0, :], arr[-1, :], arr[:, 0], arr[:, -1]])
    if (border_pixels > threshold).mean() > 0.8 and (arr > threshold).mean() > 0.6:
        # Inverted polarity (white canvas with dark line edges)
        edge_mask = arr < threshold
    else:
        # Standard polarity (dark canvas with white line edges/shapes)
        edge_mask = arr >= threshold
        if edge_mask.sum() == 0 and arr.max() > 0:
            edge_mask = arr > 0

    # Fill closed boundary holes to ensure valid silhouette mask
    filled = ndi.binary_fill_holes(edge_mask)
    if filled.sum() > edge_mask.sum():
        mask = filled
    else:
        mask = edge_mask

    os.makedirs(os.path.dirname(out_mask_path) or ".", exist_ok=True)
    mask_img = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    mask_img.save(out_mask_path)
    return out_control_path, out_mask_path
