"""Strict Replicate ControlNet adapter for real evaluations."""
import json
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
import replicate

from src.pipeline.controlnet_utils import (
    FACADE_NEGATIVE_PROMPT,
    FACADE_PROMPT_PREFIX,
    FLOORPLAN_NEGATIVE_PROMPT,
    FLOORPLAN_PROMPT_PREFIX,
    INTERIOR_NEGATIVE_PROMPT,
    INTERIOR_PROMPT_PREFIX,
    STYLE_PROMPTS,
    build_facade_payload,
    build_floorplan_payload,
    build_interior_payload,
    normalize_seed,
    select_model_id,
    validate_overrides,
)
from src.pipeline.image_io import normalize_source


@dataclass
class EvalPayload:
    caseId: str
    inputType: str  # 'facade' | 'floorplan' | 'interior'
    targetStyle: str
    localImagePath: str | None = None
    imageUrl: str | None = None
    silhouettePath: str | None = None


@dataclass
class RenderResult:
    provider: str
    latencyMs: int
    outputImageUrl: str
    debugControlMapUrl: str
    seed: int
    modelId: str
    payload: dict
    warning: str | None = None


def extract_output_image_url(response: Any) -> str:
    """Extract output image URL from Replicate response."""
    if isinstance(response, str):
        return response
    if hasattr(response, "url"):
        url_attr = getattr(response, "url")
        return str(url_attr() if callable(url_attr) else url_attr)
    if isinstance(response, list) and len(response) > 0:
        return extract_output_image_url(response[0])
    if isinstance(response, dict):
        if "output" in response:
            return extract_output_image_url(response["output"])
    if hasattr(response, "read"):
        # File-like with string representation
        return str(response)
    raise RuntimeError("Replicate response did not contain a usable output image URL.")


def extract_debug_control_map(response: Any) -> str | None:
    """Extract debug control map URL from Replicate response if provided by model."""
    if isinstance(response, dict):
        for key in ("debugControlMapUrl", "debug_control_map", "controlMap", "control_map"):
            if response.get(key) is not None:
                return extract_output_image_url(response[key])
        if isinstance(response.get("output"), dict):
            return extract_debug_control_map(response["output"])
    return None


class ReplicateAdapter:
    """Direct client for Replicate ControlNet models."""

    def __init__(self, artifact_dir: str | None = None):
        auth_token = os.getenv("REPLICATE_API_TOKEN")
        if not auth_token or not auth_token.strip():
            raise RuntimeError("REPLICATE_API_TOKEN is required for Replicate evaluation runs.")
        timeout_config = httpx.Timeout(300.0, connect=60.0)
        self.client = replicate.Client(api_token=auth_token, timeout=timeout_config)
        self.artifact_dir = artifact_dir

    def build_prompts(self, payload: EvalPayload, overrides: dict | None = None):
        """Construct positive and negative prompts based on inputType and targetStyle."""
        overrides = overrides or {}
        style_prompt = STYLE_PROMPTS.get(payload.targetStyle, payload.targetStyle)

        if payload.inputType == "facade":
            default_prompt = f"{FACADE_PROMPT_PREFIX}, {style_prompt}, daylight, highly detailed photorealistic exterior, correct structural scale"
            default_negative = FACADE_NEGATIVE_PROMPT
        elif payload.inputType == "floorplan":
            default_prompt = f"{FLOORPLAN_PROMPT_PREFIX}, {style_prompt}, highly detailed architectural visualization, correct structural scale"
            default_negative = FLOORPLAN_NEGATIVE_PROMPT
        else:  # interior
            default_prompt = f"{INTERIOR_PROMPT_PREFIX}, {style_prompt}, ambient lighting, photorealistic finish"
            default_negative = INTERIOR_NEGATIVE_PROMPT

        prompt = overrides.get("prompt") or default_prompt
        negative_prompt = (
            overrides.get("negativePrompt")
            or overrides.get("negative_prompt")
            or overrides.get("n_prompt")
            or default_negative
        )
        return prompt, negative_prompt

    def run(
        self,
        payload: EvalPayload | dict,
        overrides: dict | None = None,
        run_id: int = 1,
        local_control_map_path: str | None = None,
    ) -> RenderResult:
        """Execute a single real Replicate ControlNet inference call."""
        if isinstance(payload, dict):
            payload = EvalPayload(**payload)

        overrides = validate_overrides(overrides or {})
        model_id = select_model_id(payload.inputType, overrides)
        seed = normalize_seed(overrides.get("seed"))
        image_source = normalize_source(payload.imageUrl, payload.localImagePath)

        prompt, negative_prompt = self.build_prompts(payload, overrides)

        if payload.inputType == "facade":
            provider_input = build_facade_payload(
                image_source, model_id, prompt, negative_prompt, seed, overrides
            )
        elif payload.inputType == "floorplan":
            provider_input = build_floorplan_payload(
                image_source, model_id, prompt, negative_prompt, seed, overrides
            )
        else:
            provider_input = build_interior_payload(
                image_source, model_id, prompt, negative_prompt, seed, overrides
            )

        # Log sanitized payload (contains no API tokens)
        if self.artifact_dir:
            os.makedirs(self.artifact_dir, exist_ok=True)
            payload_log_path = os.path.join(
                self.artifact_dir, f"payload-{payload.caseId}-run{run_id}.json"
            )
            # Truncate large data URL for clean json logging
            sanitized_input = dict(provider_input)
            if sanitized_input.get("image", "").startswith("data:"):
                sanitized_input["image"] = sanitized_input["image"][:64] + "... [data url truncated]"
            with open(payload_log_path, "w") as f:
                json.dump({"modelId": model_id, "input": sanitized_input}, f, indent=2)

        start_time = time.perf_counter()
        last_error = None
        response = None
        for attempt in range(1, 4):
            try:
                response = self.client.run(model_id, input=provider_input)
                break
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(2 ** attempt)

        if response is None:
            raise RuntimeError(f"Replicate execution failed after 3 attempts: {last_error}") from last_error

        latency_ms = round((time.perf_counter() - start_time) * 1000)

        output_image_url = extract_output_image_url(response)

        # Provider control map if returned, otherwise canonical conditioning control map
        remote_control_map = extract_debug_control_map(response)
        control_map_url = remote_control_map or local_control_map_path or image_source

        return RenderResult(
            provider=f"Replicate ({model_id.split(':')[0]})",
            latencyMs=latency_ms,
            outputImageUrl=output_image_url,
            debugControlMapUrl=control_map_url,
            seed=seed,
            modelId=model_id,
            payload=provider_input,
        )