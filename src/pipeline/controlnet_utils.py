"""ControlNet parameter validation, model selection, and payload builders."""
import os
import random

CANNY_MODEL_DEFAULT = (
    "jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613"
)
DEPTH_MODEL_DEFAULT = (
    "lucataco/sdxl-controlnet-depth:465fb41789dc2203a9d7158be11d1d2570606a039c65e0e236fd329b5eecb10c"
)
FACADE_MODEL_DEFAULT = CANNY_MODEL_DEFAULT

STYLE_PROMPTS = {
    "tropical-boutique": (
        "biophilic architecture, polished teak wood, local limestone, lush monstera landscaping, "
        "premium tropical resort facade aesthetic, contextual landscaping"
    ),
    "midrange-modern": (
        "clean stucco finish, composite timber cladding, double-glazed minimalist windows, "
        "practical residential landscaping, bright daylight"
    ),
    "luxury-minimal": (
        "raw architectural concrete, expansive seamless floor-to-ceiling glass, monolithic structures, "
        "dramatic structural shadows, ultra-premium finish"
    ),
    "budget-functional": (
        "efficient modular architecture, durable low-maintenance materials, practical fenestration, "
        "cost-optimized finishes, bright natural lighting, clean construction lines"
    ),
}

FACADE_PROMPT_PREFIX = (
    "Exterior architectural photography of a building facade, preserve original massing and openings, "
    "maintain wall and window alignment, wide-angle street-level perspective"
)
FLOORPLAN_PROMPT_PREFIX = (
    "Architectural rendering from floorplan guidance, preserve room boundaries, wall placement, "
    "circulation logic, and structural layout scale"
)
INTERIOR_PROMPT_PREFIX = (
    "Interior architectural photography, eye-level 35mm perspective, room-scale, photorealistic, "
    "preserve room boundaries, natural daylight through floor-to-ceiling openings, detailed materials, "
    "close-up interior perspective"
)

FACADE_NEGATIVE_PROMPT = (
    "interior room, bedroom, indoor furniture, bed, pillows, enclosed ceiling over sky, "
    "interior lighting setup, distorted architecture, warped walls, unstable structures, "
    "blurry textures, low quality, hand-drawn artifacts, extra windows"
)
FLOORPLAN_NEGATIVE_PROMPT = (
    "distorted architecture, warped walls, unstable structures, blurry textures, "
    "low quality, hand-drawn artifacts, extra windows"
)
INTERIOR_NEGATIVE_PROMPT = (
    "floorplan, blueprint, bird-eye view, aerial view, exterior view, facade, outside perspective, "
    "white background, black border, furniture artifacts, distorted walls, warped architecture, "
    "low quality, blurry textures, noise, exterior leakage"
)


def normalize_seed(seed=None):
    """Validate or generate an integer seed in [1, 2147483647]."""
    if seed is None:
        return random.SystemRandom().randint(1, 2147483647)
    if isinstance(seed, bool) or not isinstance(seed, (int, float)) or not float(seed).is_integer():
        raise ValueError("seed must be an integer between 1 and 2147483647")
    seed = int(seed)
    if not 1 <= seed <= 2147483647:
        raise ValueError("seed must be between 1 and 2147483647")
    return seed


def validate_overrides(overrides=None):
    """Validate parameter ranges for ControlNet overrides."""
    overrides = overrides or {}
    ranges = {
        "controlnetConditioningScale": (0.0, 2.0),
        "controlnet_conditioning_scale": (0.0, 2.0),
        "guidanceScale": (1.0, 20.0),
        "guidance_scale": (1.0, 20.0),
        "numInferenceSteps": (10, 80),
        "num_inference_steps": (10, 80),
        "lowThreshold": (1, 255),
        "low_threshold": (1, 255),
        "highThreshold": (1, 255),
        "high_threshold": (1, 255),
        "controlGuidanceStart": (0.0, 1.0),
        "control_guidance_start": (0.0, 1.0),
        "controlGuidanceEnd": (0.0, 1.0),
        "control_guidance_end": (0.0, 1.0),
    }
    for key, (lower, upper) in ranges.items():
        if key in overrides and overrides[key] is not None:
            val = overrides[key]
            if not isinstance(val, (int, float)) or not (lower <= val <= upper):
                raise ValueError(f"{key} must be between {lower} and {upper}")
    if "seed" in overrides and overrides["seed"] is not None:
        normalize_seed(overrides["seed"])
    return overrides


def select_model_id(input_type, overrides=None):
    """Select the appropriate Replicate model ID based on inputType and env vars."""
    overrides = overrides or {}
    if overrides.get("model"):
        return overrides["model"]

    if input_type == "floorplan":
        return (
            overrides.get("cannyModel")
            or os.getenv("REPLICATE_CONTROLNET_CANNY_MODEL")
            or CANNY_MODEL_DEFAULT
        )
    elif input_type == "facade":
        return (
            overrides.get("facadeModel")
            or os.getenv("REPLICATE_CONTROLNET_FACADE_MODEL")
            or os.getenv("REPLICATE_CONTROLNET_CANNY_MODEL")
            or FACADE_MODEL_DEFAULT
        )
    elif input_type == "interior":
        return (
            overrides.get("depthModel")
            or os.getenv("REPLICATE_CONTROLNET_DEPTH_MODEL")
            or DEPTH_MODEL_DEFAULT
        )
    else:
        return (
            overrides.get("model")
            or os.getenv("REPLICATE_CONTROLNET_DEPTH_MODEL")
            or DEPTH_MODEL_DEFAULT
        )


def build_facade_payload(image_source, model_identifier, prompt, negative_prompt, seed, overrides=None):
    """Construct facade provider payload exactly matching reference replicateAdapter."""
    overrides = overrides or {}
    facade_overrides = overrides.get("facade", {}) if isinstance(overrides.get("facade"), dict) else overrides
    lower_model = model_identifier.lower()

    ccs = (
        facade_overrides.get("controlnetConditioningScale")
        or facade_overrides.get("controlnet_conditioning_scale")
        or overrides.get("controlnetConditioningScale")
        or overrides.get("controlnet_conditioning_scale")
        or 0.8
    )
    cg_start = (
        facade_overrides.get("controlGuidanceStart")
        or facade_overrides.get("control_guidance_start")
        or overrides.get("controlGuidanceStart")
        or overrides.get("control_guidance_start")
        or 0.0
    )
    cg_end = (
        facade_overrides.get("controlGuidanceEnd")
        or facade_overrides.get("control_guidance_end")
        or overrides.get("controlGuidanceEnd")
        or overrides.get("control_guidance_end")
        or 1.0
    )
    guidance = (
        facade_overrides.get("guidanceScale")
        or facade_overrides.get("guidance_scale")
        or overrides.get("guidanceScale")
        or overrides.get("guidance_scale")
        or 6.0
    )
    steps = (
        facade_overrides.get("numInferenceSteps")
        or facade_overrides.get("num_inference_steps")
        or overrides.get("numInferenceSteps")
        or overrides.get("num_inference_steps")
        or 30
    )
    low_th = (
        facade_overrides.get("lowThreshold")
        or facade_overrides.get("low_threshold")
        or overrides.get("lowThreshold")
        or overrides.get("low_threshold")
        or 50
    )
    high_th = (
        facade_overrides.get("highThreshold")
        or facade_overrides.get("high_threshold")
        or overrides.get("highThreshold")
        or overrides.get("high_threshold")
        or 150
    )

    if "sdxl-controlnet" in lower_model or "controlnet-depth" in lower_model:
        return {
            "image": image_source,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "controlnet_conditioning_scale": float(ccs),
            "control_guidance_start": float(cg_start),
            "control_guidance_end": float(cg_end),
            "guidance_scale": float(guidance),
            "num_inference_steps": int(steps),
            "seed": seed,
            "low_threshold": int(low_th),
            "high_threshold": int(high_th),
            "image_resolution": "768",
        }

    return {
        "image": image_source,
        "prompt": prompt,
        "n_prompt": f"indoor room, bedroom, bed, pillows, mattress, indoor furniture, ceiling panels, {negative_prompt}",
        "a_prompt": "exterior facade, open sky, architectural edge preservation",
        "num_samples": "1",
        "ddim_steps": int(steps),
        "scale": float(guidance),
        "seed": seed,
        "low_threshold": int(low_th),
        "high_threshold": int(high_th),
        "image_resolution": "768",
        "controlnet_conditioning_scale": float(ccs),
    }


def build_floorplan_payload(image_source, model_identifier, prompt, negative_prompt, seed, overrides=None):
    """Construct floorplan provider payload matching reference replicateAdapter."""
    overrides = overrides or {}
    steps = (
        overrides.get("numInferenceSteps")
        or overrides.get("num_inference_steps")
        or overrides.get("ddim_steps")
        or 35
    )
    scale = (
        overrides.get("guidanceScale")
        or overrides.get("guidance_scale")
        or overrides.get("scale")
        or 7.5
    )
    low_th = (
        overrides.get("lowThreshold")
        or overrides.get("low_threshold")
        or 100
    )
    high_th = (
        overrides.get("highThreshold")
        or overrides.get("high_threshold")
        or 200
    )
    ccs = (
        overrides.get("controlnetConditioningScale")
        or overrides.get("controlnet_conditioning_scale")
        or 0.8
    )

    lower_model = model_identifier.lower()
    if "sdxl-controlnet" in lower_model or "controlnet-depth" in lower_model:
        return {
            "image": image_source,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "controlnet_conditioning_scale": float(ccs),
            "control_guidance_start": float(overrides.get("controlGuidanceStart", 0.0)),
            "control_guidance_end": float(overrides.get("controlGuidanceEnd", 1.0)),
            "guidance_scale": float(scale),
            "num_inference_steps": int(steps),
            "seed": seed,
            "low_threshold": int(low_th),
            "high_threshold": int(high_th),
            "image_resolution": "768",
        }

    return {
        "image": image_source,
        "prompt": prompt,
        "n_prompt": negative_prompt,
        "a_prompt": "best quality, extremely detailed",
        "num_samples": "1",
        "ddim_steps": int(steps),
        "scale": float(scale),
        "seed": seed,
        "low_threshold": int(low_th),
        "high_threshold": int(high_th),
        "image_resolution": "768",
    }


def build_interior_payload(image_source, model_identifier, prompt, negative_prompt, seed, overrides=None):
    """Construct interior depth/structure payload with validated Phase 1 defaults."""
    overrides = overrides or {}
    ccs = (
        overrides.get("controlnetConditioningScale")
        or overrides.get("controlnet_conditioning_scale")
        or 0.80
    )
    cg_start = (
        overrides.get("controlGuidanceStart")
        or overrides.get("control_guidance_start")
        or 0.0
    )
    cg_end = (
        overrides.get("controlGuidanceEnd")
        or overrides.get("control_guidance_end")
        or 1.0
    )
    guidance = (
        overrides.get("guidanceScale")
        or overrides.get("guidance_scale")
        or 6.0
    )
    steps = (
        overrides.get("numInferenceSteps")
        or overrides.get("num_inference_steps")
        or 30
    )
    low_th = (
        overrides.get("lowThreshold")
        or overrides.get("low_threshold")
        or 50
    )
    high_th = (
        overrides.get("highThreshold")
        or overrides.get("high_threshold")
        or 150
    )

    return {
        "image": image_source,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "controlnet_conditioning_scale": float(ccs),
        "control_guidance_start": float(cg_start),
        "control_guidance_end": float(cg_end),
        "guidance_scale": float(guidance),
        "num_inference_steps": int(steps),
        "seed": seed,
        "low_threshold": int(low_th),
        "high_threshold": int(high_th),
        "image_resolution": "768",
    }