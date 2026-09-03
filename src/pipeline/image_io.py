"""Input image normalization for real provider calls."""
import base64
import mimetypes
import os
from pathlib import Path


def normalize_source(imageUrl=None, localImagePath=None):
    """Return a hosted URL or a data URL for a local image."""
    if imageUrl and localImagePath:
        raise ValueError("Provide only one of imageUrl or localImagePath.")
    if imageUrl:
        return imageUrl
    if not localImagePath:
        raise ValueError("An imageUrl or localImagePath is required.")
    path = Path(localImagePath).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Local image does not exist: {path}")
    max_size = int(os.getenv("MAX_DATA_URL_SIZE_BYTES", "5000000"))
    file_size = path.stat().st_size
    if file_size > max_size:
        raise ValueError(
            f"Local image is {file_size} bytes, above the {max_size}-byte data URL limit; "
            "use a signed URL upload instead."
        )
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"