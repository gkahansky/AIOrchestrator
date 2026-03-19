"""
Skill: generate_image
Generate an image from a text prompt.

This skill is called by the Tool Router — do not call tool-specific functions directly.
Use generate_image() which routes based on skills.json configuration.

Input:
    prompt        (str): Full image generation prompt.
    aspect_ratio  (str): '1:1' | '2:3' | '3:2' | '16:9'. Default: '1:1'.
    quality_tier  (str): 'standard' | 'premium'. Default: 'standard'.
    output_dir    (str | Path): Directory to save the downloaded image.
    filename      (str): Optional filename override (without extension).

Output:
    {
        "image_path": str,   # Local path to the downloaded image
        "tool_used":  str,   # 'dalle3' | 'gemini-imagen'
        "cost":       float, # Estimated cost in USD
        "width":      int,
        "height":     int,
        "prompt":     str,   # Prompt as submitted (may be revised by model)
    }
"""

import os
import time
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from PIL import Image


# ─── Public entry point ──────────────────────────────────────────────────────

def generate_image(
    prompt: str,
    aspect_ratio: str = "1:1",
    quality_tier: str = "standard",
    output_dir: str | Path = "./output",
    filename: Optional[str] = None,
) -> dict:
    """
    Route to the best active image generation tool for the given tier.
    Tool selection logic lives in platform/registry/tool_router.py.
    """
    from aiplatform.registry.tool_router import get_tool_function

    fn, tool_meta = get_tool_function("image-generation", tier=quality_tier)
    result = fn(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        output_dir=output_dir,
        filename=filename,
    )
    result["tool_used"] = tool_meta["id"]
    result["cost"] = tool_meta.get("cost_per_call", 0.0)
    return result


# ─── DALL-E 3 ────────────────────────────────────────────────────────────────

_DALLE_SIZE_MAP = {
    "1:1":  "1024x1024",
    "2:3":  "1024x1792",
    "3:2":  "1792x1024",
    "16:9": "1792x1024",  # closest DALL-E 3 supports
}


def generate_via_dalle3(
    prompt: str,
    aspect_ratio: str = "1:1",
    output_dir: str | Path = "./output",
    filename: Optional[str] = None,
) -> dict:
    """
    Generate an image using DALL-E 3 via the OpenAI API.

    Requires env var: OPENAI_API_KEY
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    size = _DALLE_SIZE_MAP.get(aspect_ratio, "1024x1024")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Force a clean flat digital image — no staging, frames, or mockups
    _CLEAN_IMAGE_SUFFIX = (
        " Flat 2D digital line art only. Background must be pure white #FFFFFF, solid colour, "
        "no texture, no gradient, no off-white, no cream, no grey. "
        "No frame, no border, no wall, no mockup, no shadow, no room, no staging. "
        "The image IS the artwork itself on a pure white background."
    )
    full_prompt = prompt + _CLEAN_IMAGE_SUFFIX

    # Submit generation request
    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "dall-e-3",
            "prompt": full_prompt,
            "n": 1,
            "size": size,
            "quality": "hd",
            "response_format": "url",
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    image_url = data["data"][0]["url"]
    revised_prompt = data["data"][0].get("revised_prompt", prompt)

    # Download image
    stem = filename or f"dalle3-{uuid.uuid4().hex[:8]}"
    local_path = output_dir / f"{stem}.png"
    _download_file(image_url, local_path)

    # Post-process: replace near-white pixels with pure #FFFFFF
    # DALL-E 3 often produces cream/off-white backgrounds even when told not to.
    _whiten_background(local_path, threshold=230)

    w, h = _parse_size(size)
    return {
        "image_path": str(local_path),
        "width": w,
        "height": h,
        "prompt": revised_prompt,
    }


# ─── Gemini Imagen 3 (inactive — pending billing) ────────────────────────────

def generate_via_gemini(
    prompt: str,
    aspect_ratio: str = "1:1",
    output_dir: str | Path = "./output",
    filename: Optional[str] = None,
) -> dict:
    """
    Generate an image using Google Gemini Imagen 3.

    Requires env var: GOOGLE_AI_API_KEY
    Status: inactive — pending Google billing approval.
    Flip active=true in skills.json when billing is confirmed.
    """
    raise NotImplementedError(
        "Gemini Imagen 3 is not yet active. "
        "Waiting on Google billing approval. "
        "Set active=true in platform/registry/skills.json when ready."
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _whiten_background(img_path: Path, threshold: int = 230) -> None:
    """
    Replace near-white pixels with pure #FFFFFF.
    DALL-E 3 frequently produces cream/off-white backgrounds.
    Pixels where R, G, and B are all >= threshold are set to 255, 255, 255.
    threshold=230 catches cream, eggshell, and light grey while preserving line art.
    """
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    mask = np.all(arr >= threshold, axis=2)
    arr[mask] = [255, 255, 255]
    Image.fromarray(arr).save(img_path, format="PNG", optimize=True)


def _download_file(url: str, dest: Path, timeout: int = 60) -> None:
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def _parse_size(size_str: str) -> tuple[int, int]:
    w, h = size_str.split("x")
    return int(w), int(h)
