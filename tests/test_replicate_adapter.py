"""Unit tests for ReplicateAdapter, payload builders, and parameter validation."""
import os
import pytest

from src.pipeline.controlnet_utils import (
    build_facade_payload,
    build_floorplan_payload,
    build_interior_payload,
    normalize_seed,
    select_model_id,
    validate_overrides,
)
from src.pipeline.replicate_adapter import EvalPayload, ReplicateAdapter


def test_normalize_seed_valid_and_random():
    assert normalize_seed(123456) == 123456
    assert normalize_seed(1) == 1
    assert normalize_seed(2147483647) == 2147483647

    random_seed = normalize_seed(None)
    assert isinstance(random_seed, int)
    assert 1 <= random_seed <= 2147483647


def test_normalize_seed_invalid():
    with pytest.raises(ValueError):
        normalize_seed(0)
    with pytest.raises(ValueError):
        normalize_seed(-5)
    with pytest.raises(ValueError):
        normalize_seed(2147483648)
    with pytest.raises(ValueError):
        normalize_seed("abc")
    with pytest.raises(ValueError):
        normalize_seed(True)


def test_validate_overrides_ranges():
    valid = {
        "controlnetConditioningScale": 0.85,
        "guidanceScale": 6.0,
        "numInferenceSteps": 30,
        "lowThreshold": 50,
        "highThreshold": 150,
        "controlGuidanceStart": 0.0,
        "controlGuidanceEnd": 1.0,
        "seed": 999999,
    }
    assert validate_overrides(valid) == valid

    with pytest.raises(ValueError):
        validate_overrides({"controlnetConditioningScale": 2.5})
    with pytest.raises(ValueError):
        validate_overrides({"guidanceScale": 0.5})
    with pytest.raises(ValueError):
        validate_overrides({"numInferenceSteps": 5})
    with pytest.raises(ValueError):
        validate_overrides({"lowThreshold": 300})
    with pytest.raises(ValueError):
        validate_overrides({"controlGuidanceStart": -0.1})


def test_build_facade_payload_sdxl_and_canny():
    source = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    seed = 123456
    sdxl_model = "lucataco/sdxl-controlnet:db2ff457004d85f737578b14f89100ebf85bce4f9ab327eab14b132832b0555b"
    canny_model = "jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613"

    sdxl_payload = build_facade_payload(
        source, sdxl_model, "Facade prompt", "Negative", seed, {"guidanceScale": 6.5, "numInferenceSteps": 35}
    )
    assert sdxl_payload["image"] == source
    assert sdxl_payload["guidance_scale"] == 6.5
    assert sdxl_payload["num_inference_steps"] == 35
    assert sdxl_payload["seed"] == seed
    assert "controlnet_conditioning_scale" in sdxl_payload

    canny_payload = build_facade_payload(
        source, canny_model, "Facade prompt", "Negative", seed, {"guidanceScale": 4.5, "numInferenceSteps": 40}
    )
    assert canny_payload["image"] == source
    assert canny_payload["scale"] == 4.5
    assert canny_payload["ddim_steps"] == 40
    assert canny_payload["seed"] == seed
    assert "a_prompt" in canny_payload


def test_build_floorplan_payload():
    source = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    seed = 777777
    model = "jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613"

    payload = build_floorplan_payload(
        source, model, "Floorplan prompt", "Negative", seed, {"guidanceScale": 7.5, "numInferenceSteps": 35}
    )
    assert payload["image"] == source
    assert payload["scale"] == 7.5
    assert payload["ddim_steps"] == 35
    assert payload["seed"] == seed
    assert payload["low_threshold"] == 100
    assert payload["high_threshold"] == 200


def test_build_interior_payload():
    source = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    seed = 555555
    model = "lucataco/sdxl-controlnet-depth:465fb41789dc2203a9d7158be11d1d2570606a039c65e0e236fd329b5eecb10c"

    payload = build_interior_payload(
        source, model, "Interior prompt", "Negative", seed, {"controlnetConditioningScale": 0.80, "guidanceScale": 6.0}
    )
    assert payload["image"] == source
    assert payload["controlnet_conditioning_scale"] == 0.80
    assert payload["guidance_scale"] == 6.0
    assert payload["num_inference_steps"] == 30
    assert payload["seed"] == seed


def test_replicate_adapter_fails_fast_without_token(monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="REPLICATE_API_TOKEN is required"):
        ReplicateAdapter()


def test_model_selection():
    assert "canny" in select_model_id("floorplan").lower()
    assert "depth" in select_model_id("interior").lower()
    assert "custom-model" == select_model_id("facade", {"model": "custom-model"})


def test_extract_output_and_control_map():
    from src.pipeline.replicate_adapter import (
        extract_debug_control_map,
        extract_output_and_control_map,
        extract_output_image_url,
    )

    # Multi-item list (canny edge map + generated image)
    multi_list = ["https://replicate.delivery/canny.png", "https://replicate.delivery/render.png"]
    out, ctrl = extract_output_and_control_map(multi_list)
    assert out == "https://replicate.delivery/render.png"
    assert ctrl == "https://replicate.delivery/canny.png"
    assert extract_output_image_url(multi_list) == "https://replicate.delivery/render.png"
    assert extract_debug_control_map(multi_list) == "https://replicate.delivery/canny.png"

    # Single-item list (depth generated image)
    single_list = ["https://replicate.delivery/depth_render.png"]
    out_s, ctrl_s = extract_output_and_control_map(single_list)
    assert out_s == "https://replicate.delivery/depth_render.png"
    assert ctrl_s is None
    assert extract_output_image_url(single_list) == "https://replicate.delivery/depth_render.png"
    assert extract_debug_control_map(single_list) is None

    # Dict response
    dict_resp = {
        "output": "https://replicate.delivery/dict_render.png",
        "control_map": "https://replicate.delivery/dict_control.png",
    }
    out_d, ctrl_d = extract_output_and_control_map(dict_resp)
    assert out_d == "https://replicate.delivery/dict_render.png"
    assert ctrl_d == "https://replicate.delivery/dict_control.png"
