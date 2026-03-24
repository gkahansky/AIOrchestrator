"""
Skill: create_mockup
Generate three photorealistic product mockup images for an Etsy wall art listing.

Primary approach — Gemini multimodal (create_mockup_gemini):
    Passes the actual artwork image as input to gemini-2.5-flash-image.
    The model sees the real artwork and places it into each scene.
    Result: mockups are visually consistent with the actual artwork.

Fallback approach — Pillow composite (create_mockup_pillow):
    Composites the actual artwork (framed) onto a clean neutral background.
    No AI cost, guaranteed consistency, but no photorealistic room context.

Three scenes per listing:
    1. product_shot — framed print on clean neutral wall, professional product photo
    2. living_room  — Scandinavian living room lifestyle scene
    3. flat_lay     — overhead desk / flat lay styling scene

Input:
    artwork_path        (str | Path)  — path to the generated artwork PNG
    artwork_description (str)         — title + style notes; used in prompts
    output_dir          (str | Path)
    slug                (str)
    aspect_ratio        (str)         — '1:1' | '2:3' | '3:2' | '16:9'

Output (both functions):
    {
        "product_shot": str,    # path to mockup JPG
        "living_room":  str,
        "flat_lay":     str,
        "cost":         float,
    }
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


# ─── Scene prompts ────────────────────────────────────────────────────────────

def _scene_prompts() -> list[dict]:
    """
    Prompts for the three mockup scenes.
    Each prompt instructs Gemini to incorporate the attached artwork image
    into the described scene — the actual artwork is passed as image input.
    """
    return [
        {
            "key":    "product_shot",
            "suffix": "mockup-1-product",
            "prompt": (
                "I am attaching a digital wall art print. "
                "Create a photorealistic e-commerce product mockup: "
                "mount this exact print in a thin black frame with a white mat board, "
                "hanging centred on a clean smooth light-grey wall. "
                "Soft even studio lighting from the upper left. No other objects. "
                "The artwork inside the frame must exactly match the attached image. "
                "High-end product photography style."
            ),
        },
        {
            "key":    "living_room",
            "suffix": "mockup-2-livingroom",
            "prompt": (
                "I am attaching a digital wall art print. "
                "Create a photorealistic lifestyle interior mockup: "
                "show this exact print in a thin black frame with a white mat board, "
                "hanging on a warm white wall above a minimal linen sofa in a bright "
                "Scandinavian living room. Natural daylight from the left. "
                "Styling: small ceramic vase with dried pampas grass, light oak coffee table, "
                "neutral woven rug. The artwork inside the frame must exactly match the attached image. "
                "Wide interior shot. No people, no text."
            ),
        },
        {
            "key":    "flat_lay",
            "suffix": "mockup-3-flatlay",
            "prompt": (
                "I am attaching a digital wall art print. "
                "Create a photorealistic flat lay product mockup: "
                "show this exact print as an unframed rolled or flat art print "
                "laid on a smooth light concrete surface. "
                "Styled props: small succulent in white pot, two or three natural pebbles, "
                "a thin wooden pencil. Even soft overhead lighting, clean fresh aesthetic. "
                "The artwork on the print must exactly match the attached image. "
                "No people, no text."
            ),
        },
    ]


# ─── Gemini multimodal mockup generator (primary) ────────────────────────────

GEMINI_MOCKUP_MODEL  = "gemini-2.5-flash-image"
GEMINI_COST_PER_IMAGE = 0.02


def create_mockup_gemini(
    artwork_path: str | Path,
    artwork_description: str,
    output_dir: str | Path,
    slug: str = "listing",
    aspect_ratio: str = "1:1",
) -> dict:
    """
    Generate 3 mockup scenes by passing the actual artwork image to Gemini.
    Gemini sees the real artwork and renders it into each scene.
    Requires GOOGLE_AI_API_KEY.
    """
    api_key = os.environ.get("GOOGLE_AI_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_AI_API_KEY is not set.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    output_dir  = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    artwork_bytes = Path(artwork_path).read_bytes()

    scenes = _scene_prompts()
    result: dict = {"cost": 0.0}

    for scene in scenes:
        print(f"    Gemini mockup: {scene['key']}...")

        response = client.models.generate_content(
            model=GEMINI_MOCKUP_MODEL,
            contents=[
                types.Content(parts=[
                    types.Part.from_text(text=scene["prompt"]),
                    types.Part.from_bytes(data=artwork_bytes, mime_type="image/png"),
                ])
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        image_bytes = _extract_image_bytes(response)
        if not image_bytes:
            raise RuntimeError(
                f"Gemini returned no image for scene '{scene['key']}'. "
                "Check model availability and prompt."
            )

        out_path = output_dir / f"{slug}-{scene['suffix']}.png"
        out_path.write_bytes(image_bytes)

        jpg_path = out_path.with_suffix(".jpg")
        Image.open(out_path).convert("RGB").save(jpg_path, "JPEG", quality=92)
        out_path.unlink()

        result[scene["key"]] = str(jpg_path)
        result["cost"] += GEMINI_COST_PER_IMAGE
        print(f"      Saved: {jpg_path}")

    return result


def _extract_image_bytes(response) -> bytes | None:
    """Pull image bytes out of a Gemini generateContent response."""
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if not hasattr(part, "inline_data") or not part.inline_data:
                continue
            data = part.inline_data.data
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
            if isinstance(data, str):
                return base64.b64decode(data)
    return None


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
    Guaranteed visual consistency — the real artwork is always used.
    No AI cost. Used as fallback when Gemini is unavailable.
    """
    artwork_path = Path(artwork_path)
    output_dir   = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    artwork = Image.open(artwork_path).convert("RGBA")
    result: dict = {"cost": 0.0}

    product_img = _composite_framed(artwork, bg_color=(240, 238, 234))
    p1 = output_dir / f"{slug}-mockup-1-product.jpg"
    product_img.convert("RGB").save(p1, "JPEG", quality=92)
    result["product_shot"] = str(p1)

    warm_img = _composite_framed(artwork, bg_color=(232, 228, 220))
    p2 = output_dir / f"{slug}-mockup-2-livingroom.jpg"
    warm_img.convert("RGB").save(p2, "JPEG", quality=92)
    result["living_room"] = str(p2)

    cool_img = _composite_framed(artwork, bg_color=(224, 228, 232))
    p3 = output_dir / f"{slug}-mockup-3-flatlay.jpg"
    cool_img.convert("RGB").save(p3, "JPEG", quality=92)
    result["flat_lay"] = str(p3)

    return result


# ─── Public entry point ───────────────────────────────────────────────────────

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
    C      = CANVAS_SIZE
    art_px = int(C * ARTWORK_FRAC)

    art_w, art_h = artwork.size
    scale        = art_px / max(art_w, art_h)
    new_w, new_h = int(art_w * scale), int(art_h * scale)
    art_resized  = artwork.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (C, C), (*bg_color, 255))

    cx, cy = C // 2, C // 2
    art_x  = cx - new_w // 2
    art_y  = cy - new_h // 2

    frame_total_w = new_w + (MAT_PX + FRAME_PX) * 2
    frame_total_h = new_h + (MAT_PX + FRAME_PX) * 2
    fx = art_x - MAT_PX - FRAME_PX
    fy = art_y - MAT_PX - FRAME_PX

    shadow = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    shadow.paste(
        Image.new("RGBA", (frame_total_w + 16, frame_total_h + 16), (0, 0, 0, 90)),
        (fx + 10, fy + 12),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=14))
    canvas = Image.alpha_composite(canvas, shadow)

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([fx, fy, fx + frame_total_w, fy + frame_total_h], fill=(22, 18, 14, 255))

    mx, my = fx + FRAME_PX, fy + FRAME_PX
    mw, mh = frame_total_w - FRAME_PX * 2, frame_total_h - FRAME_PX * 2
    draw.rectangle([mx, my, mx + mw, my + mh], fill=(252, 251, 249, 255))

    canvas.paste(art_resized, (art_x, art_y), art_resized)
    return canvas
