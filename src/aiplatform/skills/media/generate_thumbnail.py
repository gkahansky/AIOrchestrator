"""
Platform skill: generate_thumbnail

Composites a thumbnail image from a video frame using Pillow.
Free/Starter/Pro: Pillow gradient bar + title text overlay.
Studio: Creatomate API branded template (falls back to Pillow if unconfigured).
Venture-agnostic.
"""

import io
import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


_THUMB_W = 1080
_THUMB_H = 1920   # portrait 9:16 — matches the transcoded clip format
_GRADIENT_HEIGHT_RATIO = 0.25   # bottom 25% of the thumbnail
_FONT_SIZE = 80
_PADDING = 40


def generate_thumbnail(
    frame_path: str,
    title: str,
    show_name: str = "",
    plan: str = "starter",
    output_path: str | None = None,
    creatomate_api_key: str | None = None,
    creatomate_template_id: str | None = None,
) -> dict:
    """
    Generate a thumbnail image from a selected video frame.

    Args:
        frame_path:              Path to the best frame JPEG.
        title:                   Clip title text to overlay.
        show_name:               Show name (optional, added as smaller subtitle).
        plan:                    "free" | "starter" | "pro" | "studio".
        output_path:             Where to write the .jpg. Defaults to <frame_stem>_thumb.jpg.
        creatomate_api_key:      Creatomate API key (Studio only; falls back to Pillow if absent).
        creatomate_template_id:  Creatomate template ID (Studio only).

    Returns:
        {"thumbnail_path": str, "engine": str}  — engine is "pillow" or "creatomate".
    """
    frame = Path(frame_path)
    if output_path is None:
        output_path = str(frame.parent / f"{frame.stem}_thumb.jpg")

    # Studio plan with Creatomate configured
    if (
        plan == "studio"
        and (creatomate_api_key or os.getenv("CREATOMATE_API_KEY"))
        and (creatomate_template_id or os.getenv("CREATOMATE_TEMPLATE_REEL"))
    ):
        path = _creatomate_thumbnail(
            frame_path, title, show_name, output_path,
            creatomate_api_key or os.getenv("CREATOMATE_API_KEY"),
            creatomate_template_id or os.getenv("CREATOMATE_TEMPLATE_REEL"),
        )
        return {"thumbnail_path": path, "engine": "creatomate"}

    path = _pillow_thumbnail(frame_path, title, show_name, output_path)
    return {"thumbnail_path": path, "engine": "pillow"}


def _pillow_thumbnail(frame_path: str, title: str, show_name: str, output_path: str) -> str:
    img = Image.open(frame_path).convert("RGB")
    # Smart-crop to portrait 9:16 without distortion (preserves aspect ratio via centre crop)
    img = ImageOps.fit(img, (_THUMB_W, _THUMB_H), Image.LANCZOS)

    draw = ImageDraw.Draw(img, "RGBA")

    # Gradient bar: semi-transparent dark gradient at bottom
    grad_h = int(_THUMB_H * _GRADIENT_HEIGHT_RATIO)
    grad_top = _THUMB_H - grad_h
    for y in range(grad_h):
        alpha = int(210 * (y / grad_h))  # fade in from top of bar
        draw.rectangle([(0, grad_top + y), (_THUMB_W, grad_top + y + 1)], fill=(0, 0, 0, alpha))

    # Load font — try system fonts, fall back to PIL default
    font_title = _load_font(_FONT_SIZE)
    font_show = _load_font(int(_FONT_SIZE * 0.5))

    # Wrap title to fit width
    max_chars = max(15, int(_THUMB_W / (_FONT_SIZE * 0.55)))
    wrapped = textwrap.fill(title, width=max_chars)

    text_y = grad_top + _PADDING
    # Shadow
    draw.text((_PADDING + 3, text_y + 3), wrapped, font=font_title, fill=(0, 0, 0, 180))
    # Main text
    draw.text((_PADDING, text_y), wrapped, font=font_title, fill=(255, 255, 255, 255))

    if show_name:
        _, _, _, text_h = draw.textbbox((0, 0), wrapped, font=font_title)
        show_y = text_y + text_h + 10
        draw.text((_PADDING, show_y), show_name, font=font_show, fill=(200, 200, 200, 220))

    img.save(output_path, "JPEG", quality=92)
    return output_path


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _creatomate_thumbnail(
    frame_path: str,
    title: str,
    show_name: str,
    output_path: str,
    api_key: str,
    template_id: str,
) -> str:
    """Call Creatomate API to render a branded thumbnail. Falls back to Pillow on error."""
    import base64
    try:
        import requests  # type: ignore
    except ImportError:
        return _pillow_thumbnail(frame_path, title, show_name, output_path)

    img_b64 = base64.b64encode(Path(frame_path).read_bytes()).decode()

    payload = {
        "template_id": template_id,
        "modifications": {
            "title": title,
            "show_name": show_name,
            "background_image": f"data:image/jpeg;base64,{img_b64}",
        },
        "output_format": "jpg",
    }
    try:
        resp = requests.post(
            "https://api.creatomate.com/v1/renders",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )
        resp.raise_for_status()
        renders = resp.json()
        if renders and renders[0].get("url"):
            img_resp = requests.get(renders[0]["url"], timeout=30)
            img_resp.raise_for_status()
            Path(output_path).write_bytes(img_resp.content)
            return output_path
    except Exception:
        pass

    # Fallback
    return _pillow_thumbnail(frame_path, title, show_name, output_path)
