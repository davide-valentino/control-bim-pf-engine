"""Unit tests for image_io source normalization."""
import pytest
from PIL import Image

from src.pipeline.image_io import normalize_source


def test_normalize_source_hosted_url():
    url = "https://example.com/sample.png"
    assert normalize_source(imageUrl=url) == url


def test_normalize_source_local_image(tmp_path):
    img_path = tmp_path / "test.png"
    Image.new("RGB", (32, 32), color="blue").save(img_path)

    data_url = normalize_source(localImagePath=str(img_path))
    assert data_url.startswith("data:image/png;base64,")


def test_normalize_source_missing_both():
    with pytest.raises(ValueError, match="required"):
        normalize_source()


def test_normalize_source_providing_both():
    with pytest.raises(ValueError, match="only one"):
        normalize_source(imageUrl="https://example.com/test.png", localImagePath="test.png")


def test_normalize_source_file_not_found():
    with pytest.raises(FileNotFoundError):
        normalize_source(localImagePath="nonexistent_file_path_12345.png")


def test_normalize_source_size_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_DATA_URL_SIZE_BYTES", "100")
    img_path = tmp_path / "large.png"
    img_path.write_bytes(b"A" * 200)

    with pytest.raises(ValueError, match="limit"):
        normalize_source(localImagePath=str(img_path))
