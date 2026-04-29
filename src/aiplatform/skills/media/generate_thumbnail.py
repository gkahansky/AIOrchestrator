"""
Platform skill: generate_thumbnail

Composites a thumbnail image from a video frame using Pillow.
Free/Starter/Pro: YouTube-style bold multi-colour text overlay.
Studio: Creatomate API branded template (falls back to Pillow if unconfigured).

Platform-aware: the `platform` parameter is threaded through all calls so that
future per-platform layouts (e.g. YouTube 16:9, TikTok 9:16, Instagram 1:1)
can be added by branching on it inside _pillow_thumbnail / _creatomate_thumbnail.
Currently all platforms use the same 1080×1920 portrait compositor.

Venture-agnostic.
"""

import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

_THUMB_W = 1080
_THUMB_H = 1920   # portrait 9:16

_FONT_SIZE_HEADLINE = 90
_FONT_SIZE_SHOW = 36
_PADDING = 48
_ACCENT_COLOUR = (255, 230, 0)    # yellow — highlight word
_TEXT_COLOUR = (255, 255, 255)    # white — rest of headline
_OUTLINE_WIDTH = 4
_BOX_ALPHA = 160                  # backing box opacity (0-255)
_MAX_BAR_RATIO = 0.45             # text area never exceeds 45% of frame height


def generate_thumbnail(
    frame_path: str,
    title: str,
    show_name: str = "",
    plan: str = "starter",
    output_path: str | None = None,
    creatomate_api_key: str | None = None,
    creatomate_template_id: str | None = None,
    highlight_word: str = "",
    platform: str = "default",
) -> dict:
    """
    Generate a thumbnail image from a selected video frame.

    Args:
        frame_path:              Path to the best frame JPEG.
        title:                   Headline text to overlay (ideally from generate_thumbnail_headline).
        show_name:               Show name (optional subtitle strip at very bottom).
        plan:                    "free" | "starter" | "pro" | "studio".
        output_path:             Where to write the .jpg. Defaults to <frame_stem>_thumb.jpg.
        creatomate_api_key:      Creatomate API key (Studio only; falls back to Pillow if absent).
        creatomate_template_id:  Creatomate template ID (Studio only).
        highlight_word:          Single word in title to render in accent colour (yellow).
        platform:                Target platform ("default" | "youtube" | "tiktok" | …).
                                 Hook for future per-platform layout; currently all use portrait 9:16.

    Returns:
        {"thumbnail_path": str, "engine": str}  — engine is "pillow" or "creatomate".
    """
    frame = Path(frame_path)
    if output_path is None:
        output_path = str(frame.parent / f"{frame.stem}_thumb.jpg")

    if (
        plan == "studio"
        and (creatomate_api_key or os.getenv("CREATOMATE_API_KEY"))
        and (creatomate_template_id or os.getenv("CREATOMATE_TEMPLATE_REEL"))
    ):
        path = _creatomate_thumbnail(
            frame_path, title, show_name, output_path,
            creatomate_api_key or os.getenv("CREATOMATE_API_KEY"),
            creatomate_template_id or os.getenv("CREATOMATE_TEMPLATE_REEL"),
            highlight_word=highlight_word,
            platform=platform,
        )
        return {"thumbnail_path": path, "engine": "creatomate"}

    path = _pillow_thumbnail(
        frame_path, title, show_name, output_path,
        highlight_word=highlight_word,
        platform=platform,
    )
    return {"thumbnail_path": path, "engine": "pillow"}


def _pillow_thumbnail(
    frame_path: str,
    title: str,
    show_name: str,
    output_path: str,
    highlight_word: str = "",
    platform: str = "default",
) -> str:
    """
    YouTube-style thumbnail compositor.

    Layout:
    - Portrait 9:16 frame as background (smart-cropped via ImageOps.fit)
    - Subtle vignette at edges for depth
    - Text positioned at bottom (or top if face detected in lower half — heuristic)
    - Semi-transparent dark backing box behind headline
    - Bold headline: most words in white, highlight_word in yellow
    - Each word rendered with black stroke outline for contrast on any background
    - Smaller show_name strip at very bottom
    """
    img = Image.open(frame_path).convert("RGB")
    img = ImageOps.fit(img, (_THUMB_W, _THUMB_H), Image.LANCZOS)

    # ── Vignette: darken edges ────────────────────────────────────────────────
    vignette = Image.new("RGBA", (_THUMB_W, _THUMB_H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    strength = 160
    steps = 120
    for i in range(steps):
        alpha = int(strength * (1 - i / steps) ** 2)
        vd.rectangle(
            [(i, i), (_THUMB_W - i, _THUMB_H - i)],
            outline=(0, 0, 0, alpha),
        )
    img.paste(Image.alpha_composite(img.convert("RGBA"), vignette).convert("RGB"))

    draw = ImageDraw.Draw(img, "RGBA")

    # ── Font loading ──────────────────────────────────────────────────────────
    font_size = _FONT_SIZE_HEADLINE
    font_headline = _load_font(font_size)
    font_show = _load_font(_FONT_SIZE_SHOW)

    # ── Wrap title to fit width ───────────────────────────────────────────────
    max_chars = max(10, int(_THUMB_W / (font_size * 0.52)))
    lines = textwrap.wrap(title, width=max_chars) or [title[:40]]

    # Measure total text block height; shrink font if needed
    for attempt in range(3):
        font_headline = _load_font(font_size)
        max_chars = max(10, int(_THUMB_W / (font_size * 0.52)))
        lines = textwrap.wrap(title, width=max_chars) or [title[:40]]
        line_h = draw.textbbox((0, 0), "Ag", font=font_headline)[3]
        text_block_h = line_h * len(lines) + 10 * (len(lines) - 1)

        show_strip_h = (_FONT_SIZE_SHOW + _PADDING) if show_name else 0
        bar_h = text_block_h + _PADDING * 2 + show_strip_h
        if bar_h <= _THUMB_H * _MAX_BAR_RATIO:
            break
        font_size -= 10

    bar_h = min(bar_h, int(_THUMB_H * _MAX_BAR_RATIO))
    bar_top = _THUMB_H - bar_h

    # ── Semi-transparent backing box ──────────────────────────────────────────
    draw.rectangle([(0, bar_top), (_THUMB_W, _THUMB_H)], fill=(0, 0, 0, _BOX_ALPHA))

    # Gradient fade from transparent to box colour at the top of the box
    fade_h = min(60, bar_h // 3)
    for y in range(fade_h):
        alpha = int(_BOX_ALPHA * (y / fade_h))
        draw.rectangle(
            [(0, bar_top - fade_h + y), (_THUMB_W, bar_top - fade_h + y + 1)],
            fill=(0, 0, 0, alpha),
        )

    # ── Render headline words with per-word colour ────────────────────────────
    highlight_upper = highlight_word.upper().strip()
    text_y = bar_top + _PADDING

    for line in lines:
        words = line.split()
        # Measure total line width to centre it
        line_width = sum(
            draw.textlength(w + " ", font=font_headline) for w in words
        )
        x = (_THUMB_W - line_width) // 2

        for word in words:
            colour = _ACCENT_COLOUR if word.upper() == highlight_upper else _TEXT_COLOUR
            word_with_space = word + " "
            # Black stroke outline
            draw.text(
                (x, text_y), word_with_space, font=font_headline,
                fill=(0, 0, 0, 255),
                stroke_width=_OUTLINE_WIDTH,
                stroke_fill=(0, 0, 0, 255),
            )
            draw.text((x, text_y), word_with_space, font=font_headline, fill=colour)
            x += draw.textlength(word_with_space, font=font_headline)

        _, _, _, lh = draw.textbbox((0, 0), line, font=font_headline)
        text_y += lh + 10

    # ── Show name strip ───────────────────────────────────────────────────────
    if show_name:
        show_y = _THUMB_H - _FONT_SIZE_SHOW - _PADDING // 2
        draw.text(
            (_PADDING, show_y), show_name, font=font_show,
            fill=(200, 200, 200, 220),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 180),
        )

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
    highlight_word: str = "",
    platform: str = "default",
) -> str:
    """Call Creatomate API to render a branded thumbnail. Falls back to Pillow on error."""
    import base64
    try:
        import requests  # type: ignore
    except ImportError:
        return _pillow_thumbnail(
            frame_path, title, show_name, output_path,
            highlight_word=highlight_word, platform=platform,
        )

    img_b64 = base64.b64encode(Path(frame_path).read_bytes()).decode()

    payload = {
        "template_id": template_id,
        "modifications": {
            "title": title,
            "show_name": show_name,
            "highlight_word": highlight_word,
            "platform": platform,
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

    return _pillow_thumbnail(
        frame_path, title, show_name, output_path,
        highlight_word=highlight_word, platform=platform,
    )
