"""
Skill: create_mockup
Generate three photorealistic product mockup images for an Etsy wall art listing.

Primary approach — Gemini Imagen 3 (create_mockup_gemini):
    Generates each scene end-to-end from a rich text prompt that describes
    both the room and the artwork style. Produces cohesive, photorealistic
    results without compositing artefacts.

Fallback approach — Pillow composite (create_mockup_pillow):
    Composites the actual artwork (framed) onto a clean neutral background.
    Used when Gemini is unavailable or as a lower-cost option.

Three scenes per listing:
    1. product_shot — art print on a clean neutral wall, professional product photo
    2. living_room  — Scandinavian living room lifestyle scene
    3. flat_lay     — overhead desk / flat lay styling scene

Input:
    artwork_path        (str | Path)  — path to the generated artwork PNG
    artwork_description (str)         — title + style notes; informs scene prompt
    output_dir          (str | Path)
    slug                (str)
    aspect_ratio        (str)         — '1:1' | '2:3' | '3:2' | '16:9'

Output (both functions):
    {
        "product_shot": str,    # path to mockup PNG
        "living_room":  str,
        "flat_lay":     str,
        "cost":         float,
    }
"""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


# ─── Scene definitions ────────────────────────────────────────────────────────

def _scene_prompts(artwork_description: str) -> list[dict]:
    """
    Build the three scene prompts for a given artwork description.
    Each prompt describes the room + the artwork's style so Gemini
    generates a fully integrated, photorealistic scene.
    """
    art = artwork_description.strip().rstrip(".")
    return [
        {
            "key":    "product_shot",
            "suffix": "mockup-1-product",
            "prompt": (
                f"Professional product photography of a framed fine art print: {art}. "
                "The print is mounted in a thin black frame with a white mat board, hanging on a "
                "clean, smooth light grey wall. Soft even studio lighting from the upper left. "
                "The frame is centred in the image, sharply in focus. No other objects. "
                "Photorealistic, high-end e-commerce product photography style."
            ),
        },
        {
            "key":    "living_room",
            "suffix": "mockup-2-livingroom",
            "prompt": (
                f"A bright, airy modern Scandinavian living room featuring a framed wall art print of: {art}. "
                "The print hangs prominently on a warm white wall above a minimal linen sofa. "
                "Soft natural daylight streams in from the left. Styling details: a small ceramic vase "
                "with dried pampas grass, a light oak coffee table, a neutral woven rug. "
                "Professional interior design photography, wide shot showing the full room context. "
                "No people, no text."
            ),
        },
        {
            "key":    "flat_lay",
            "suffix": "mockup-3-flatlay",
            "prompt": (
                f"Professional top-down flat lay product photography featuring a rolled or unframed art print of: {art}. "
                "Laid on a smooth light concrete or linen surface. Styled with minimal props: a small "
                "succulent in a white pot, two or three natural pebbles, a thin wooden pencil. "
                "Even soft overhead lighting, no shadows, clean and fresh aesthetic. "
                "High-end lifestyle product photography. No people, no text."
            ),
        },
    ]


# ─── Gemini mockup generator (primary) ───────────────────────────────────────

GEMINI_COST_PER_IMAGE = 0.02   # Imagen 4 Fast rate (used for mockups)


def create_mockup_gemini(
    artwork_path: str | Path,
    artwork_description: str,
    output_dir: str | Path,
    slug: str = "listing",
    aspect_ratio: str = "1:1",
) -> dict:
    """
    Generate 3 mockup scenes using Gemini Imagen 3.

    Each scene is generated end-to-end from a text prompt describing
    both the room setting and the artwork style. Requires GOOGLE_AI_API_KEY.
    """
    api_key = os.environ.get("GOOGLE_AI_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_AI_API_KEY is not set.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scenes = _scene_prompts(artwork_description)
    result: dict = {"cost": 0.0}

    for scene in scenes:
        print(f"    Gemini mockup: {scene['key']}...")
        response = client.models.generate_images(
            model="imagen-4.0-fast-generate-001",
            prompt=scene["prompt"],
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
                output_mime_type="image/png",
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
                person_generation="DONT_ALLOW",
            ),
        )

        if not response.generated_images:
            raise RuntimeError(
                f"Gemini returned no image for scene '{scene['key']}'. "
                "Check safety filters or simplify the prompt."
            )

        image_bytes = response.generated_images[0].image.image_bytes
        out_path = output_dir / f"{slug}-{scene['suffix']}.png"
        out_path.write_bytes(image_bytes)

        # Convert to JPG for smaller file size (Etsy accepts both)
        jpg_path = out_path.with_suffix(".jpg")
        Image.open(out_path).convert("RGB").save(jpg_path, "JPEG", quality=92)
        out_path.unlink()   # remove PNG, keep JPG

        result[scene["key"]] = str(jpg_path)
        result["cost"] += GEMINI_COST_PER_IMAGE
        print(f"      Saved: {jpg_path}")

    return result


# ─── Pillow composite mockup (fallback) ──────────────────────────────────────

CANVAS_SIZE  = 1200
ARTWORK_FRAC = 0.52
FRAME_PX     = 16
MAT_PX       = 22


def create_mockup_pillow(
    artwork_path: str | Path,
    artwork_description: str,
    output_dir: str | Path,
    slug: str = "listing",
    aspect_ratio: str = "1:1",
) -> dict:
    """
    Composite the actual artwork into a clean framed product shot using Pillow.
    Produces a neutral, professional result with no AI cost.
    Used as a fallback when Gemini is unavailable.
    """
    artwork_path = Path(artwork_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    artwork = Image.open(artwork_path).convert("RGBA")
    result: dict = {"cost": 0.0}

    # Scene 1: product shot — framed on neutral gradient wall
    product_img = _composite_framed(artwork, bg_color=(240, 238, 234))
    p1 = output_dir / f"{slug}-mockup-1-product.jpg"
    product_img.convert("RGB").save(p1, "JPEG", quality=92)
    result["product_shot"] = str(p1)

    # Scene 2 & 3: same composite on slightly different backgrounds
    # (full lifestyle scenes require Gemini; these are acceptable fallbacks)
    warm_img = _composite_framed(artwork, bg_color=(232, 228, 220))
    p2 = output_dir / f"{slug}-mockup-2-livingroom.jpg"
    warm_img.convert("RGB").save(p2, "JPEG", quality=92)
    result["living_room"] = str(p2)

    cool_img = _composite_framed(artwork, bg_color=(224, 228, 232))
    p3 = output_dir / f"{slug}-mockup-3-flatlay.jpg"
    cool_img.convert("RGB").save(p3, "JPEG", quality=92)
    result["flat_lay"] = str(p3)

    return result


def create_mockup(
    artwork_path: str | Path,
    artwork_description: str,
    output_dir: str | Path,
    slug: str = "listing",
    aspect_ratio: str = "1:1",
) -> dict:
    """
    Public entry point — routed via the Tool Router from skills.json.
    Delegates to create_mockup_gemini or create_mockup_pillow.
    """
    from aiplatform.registry.tool_router import get_tool_function
    fn, tool_meta = get_tool_function("mockup-creation")
    result = fn(
        artwork_path=artwork_path,
        artwork_description=artwork_description,
        output_dir=output_dir,
        slug=slug,
        aspect_ratio=aspect_ratio,
    )
    result["tool_used"] = tool_meta["id"]
    return result


# ─── Pillow helpers ───────────────────────────────────────────────────────────

def _composite_framed(artwork: Image.Image, bg_color: tuple) -> Image.Image:
    """
    Composite the artwork inside a black frame + white mat onto a solid background.
    Returns a CANVAS_SIZE × CANVAS_SIZE RGBA image.
    """
    C = CANVAS_SIZE
    art_px = int(C * ARTWORK_FRAC)

    art_w, art_h = artwork.size
    scale = art_px / max(art_w, art_h)
    new_w, new_h = int(art_w * scale), int(art_h * scale)
    art_resized = artwork.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (C, C), (*bg_color, 255))

    cx, cy = C // 2, C // 2
    art_x = cx - new_w // 2
    art_y = cy - new_h // 2

    frame_total_w = new_w + (MAT_PX + FRAME_PX) * 2
    frame_total_h = new_h + (MAT_PX + FRAME_PX) * 2
    fx = art_x - MAT_PX - FRAME_PX
    fy = art_y - MAT_PX - FRAME_PX

    # Drop shadow
    shadow = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    shadow.paste(
        Image.new("RGBA", (frame_total_w + 16, frame_total_h + 16), (0, 0, 0, 90)),
        (fx + 10, fy + 12),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=14))
    canvas = Image.alpha_composite(canvas, shadow)

    draw = ImageDraw.Draw(canvas)

    # Black frame
    draw.rectangle([fx, fy, fx + frame_total_w, fy + frame_total_h], fill=(22, 18, 14, 255))

    # White mat
    mx, my = fx + FRAME_PX, fy + FRAME_PX
    mw, mh = frame_total_w - FRAME_PX * 2, frame_total_h - FRAME_PX * 2
    draw.rectangle([mx, my, mx + mw, my + mh], fill=(252, 251, 249, 255))

    # Artwork
    canvas.paste(art_resized, (art_x, art_y), art_resized)

    return canvas
