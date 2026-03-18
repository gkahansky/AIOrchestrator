"""
Skill: create_mockup
Generate photorealistic product mockups using DALL-E 2 outpainting.

Approach — two steps per mockup:
  1. Place the actual artwork (with a thin frame) on a 1024x1024 canvas.
     Everything outside the artwork is left transparent (the mask).
  2. Call DALL-E 2's image edit (inpaint) endpoint:
       - image = canvas with artwork centred and framed
       - mask  = transparent everywhere EXCEPT the artwork+frame area
       - prompt = room scene description
     DALL-E 2 fills the transparent area with a matching room, leaving
     our artwork pixel-perfect.

Result: exact artwork + photorealistic room — generated together so
lighting and context are consistent.

Three scenes per listing:
  1. living_room — modern Scandinavian living room
  2. office      — minimal home office / study
  3. bedroom     — cosy bedroom

Cost: DALL-E 2 1024x1024 = $0.020/image → $0.06 total (vs $0.12 before).

Input:
    artwork_path        (str | Path)
    artwork_description (str)         — informs the room style prompt
    output_dir          (str | Path)
    slug                (str)
    aspect_ratio        (str)         — unused at this tier (DALL-E 2 is always 1024²)

Output:
    { "living_room": str, "office": str, "bedroom": str, "cost": float }
"""

import io
import os
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter


CANVAS_SIZE   = 1024          # DALL-E 2 edit max
ARTWORK_FRAC  = 0.46          # artwork takes this fraction of canvas (each side)
FRAME_PX      = 14            # frame border thickness in pixels
MAT_PX        = 18            # white mat thickness in pixels
COST_PER_IMG  = 0.020         # DALL-E 2 1024x1024

_SCENES = [
    {
        "key":    "living_room",
        "suffix": "mockup-1-livingroom",
        "prompt": (
            "A framed fine art print hanging on a light wall in a bright modern Scandinavian "
            "living room. Soft natural daylight, neutral warm tones, stylish sofa visible below. "
            "Photorealistic interior design photography. No people, no text."
        ),
    },
    {
        "key":    "office",
        "suffix": "mockup-2-office",
        "prompt": (
            "A framed fine art print hanging on the wall in an elegant minimal home office. "
            "Warm desk lamp, wooden desk below, books, calm professional atmosphere. "
            "Photorealistic interior photography. No people, no text."
        ),
    },
    {
        "key":    "bedroom",
        "suffix": "mockup-3-bedroom",
        "prompt": (
            "A framed fine art print hanging on the wall in a cosy stylish bedroom. "
            "Soft warm lighting, neutral linen bedding, small potted plant nearby. "
            "Photorealistic interior photography. No people, no text."
        ),
    },
]


def create_mockup(
    artwork_path: str | Path,
    artwork_description: str,
    output_dir: str | Path,
    slug: str = "listing",
    aspect_ratio: str = "1:1",   # reserved — DALL-E 2 edit is always square
) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set.")

    artwork_path = Path(artwork_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    artwork = Image.open(artwork_path).convert("RGBA")
    result = {"cost": 0.0}

    for scene in _SCENES:
        print(f"  Outpainting {scene['key']}...")

        image_buf, mask_buf = _build_canvas_and_mask(artwork)
        mockup_img = _call_dalle2_edit(api_key, image_buf, mask_buf, scene["prompt"])
        result["cost"] += COST_PER_IMG

        out_path = output_dir / f"{slug}-{scene['suffix']}.jpg"
        mockup_img.convert("RGB").save(out_path, "JPEG", quality=92)
        result[scene["key"]] = str(out_path)
        print(f"    Saved: {out_path}")

    return result


# ─── Step 1: Build canvas + mask ─────────────────────────────────────────────

def _build_canvas_and_mask(artwork: Image.Image) -> tuple[io.BytesIO, io.BytesIO]:
    """
    Returns two PNG byte buffers:
      image — artwork centred and framed on a white 1024x1024 canvas
      mask  — fully transparent EXCEPT over the artwork+frame (which is kept)

    DALL-E 2 edit semantics:
      mask transparent (alpha=0)   → generate here (the room)
      mask opaque     (alpha=255)  → keep original (artwork + frame)
    """
    C = CANVAS_SIZE
    art_px = int(C * ARTWORK_FRAC)  # artwork display size (square)

    # Scale artwork to fit within art_px × art_px (no crop)
    art_w, art_h = artwork.size
    scale = art_px / max(art_w, art_h)
    new_w, new_h = int(art_w * scale), int(art_h * scale)
    art_resized = artwork.resize((new_w, new_h), Image.LANCZOS)

    # Centre coordinates for the artwork
    total_half = (art_px // 2) + MAT_PX + FRAME_PX
    cx, cy = C // 2, C // 2
    art_x = cx - new_w // 2
    art_y = cy - new_h // 2

    # ── Build image canvas ──────────────────────────────────────────────────
    # Start transparent so DALL-E 2 knows where to paint
    canvas = Image.new("RGBA", (C, C), (0, 0, 0, 0))

    # Drop shadow (behind frame)
    shadow_layer = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    frame_total_w = new_w + (MAT_PX + FRAME_PX) * 2
    frame_total_h = new_h + (MAT_PX + FRAME_PX) * 2
    fx = art_x - MAT_PX - FRAME_PX
    fy = art_y - MAT_PX - FRAME_PX
    shadow_layer.paste(
        Image.new("RGBA", (frame_total_w + 12, frame_total_h + 12), (0, 0, 0, 110)),
        (fx + 8, fy + 10),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=12))
    canvas = Image.alpha_composite(canvas, shadow_layer)

    # Black frame
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([fx, fy, fx + frame_total_w, fy + frame_total_h], fill=(22, 18, 14, 255))

    # White mat
    mx, my = fx + FRAME_PX, fy + FRAME_PX
    mw, mh = frame_total_w - FRAME_PX * 2, frame_total_h - FRAME_PX * 2
    draw.rectangle([mx, my, mx + mw, my + mh], fill=(252, 251, 249, 255))

    # Artwork
    canvas.paste(art_resized, (art_x, art_y), art_resized)

    # ── Build mask ──────────────────────────────────────────────────────────
    # Fully transparent = DALL-E 2 fills here (the room)
    mask = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    # Opaque over the entire framed region (frame + mat + artwork + shadow area)
    keep_x = max(0, fx - 20)
    keep_y = max(0, fy - 20)
    keep_w = min(C - keep_x, frame_total_w + 40)
    keep_h = min(C - keep_y, frame_total_h + 40)
    mask.paste(Image.new("RGBA", (keep_w, keep_h), (255, 255, 255, 255)), (keep_x, keep_y))

    # ── Serialise to PNG bytes ──────────────────────────────────────────────
    img_buf = io.BytesIO()
    canvas.save(img_buf, format="PNG")
    img_buf.seek(0)

    mask_buf = io.BytesIO()
    mask.save(mask_buf, format="PNG")
    mask_buf.seek(0)

    return img_buf, mask_buf


# ─── Step 2: DALL-E 2 edit ───────────────────────────────────────────────────

def _call_dalle2_edit(
    api_key: str,
    image_buf: io.BytesIO,
    mask_buf: io.BytesIO,
    prompt: str,
) -> Image.Image:
    resp = requests.post(
        "https://api.openai.com/v1/images/edits",
        headers={"Authorization": f"Bearer {api_key}"},
        data={"model": "dall-e-2", "prompt": prompt, "n": "1", "size": "1024x1024", "response_format": "url"},
        files={
            "image": ("image.png", image_buf, "image/png"),
            "mask":  ("mask.png",  mask_buf,  "image/png"),
        },
        timeout=120,
    )
    resp.raise_for_status()
    url = resp.json()["data"][0]["url"]
    r = requests.get(url, timeout=60, stream=True)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGBA")
