"""Carousel brief planner — turn one topic into N coordinated slide prompts.

Calling `generate_image` N times with the same prompt + a slide number
produces stylistic drift (different lighting / palette / composition each
time). That's fine for an array of generic illustrations; it's wrong for a
LinkedIn carousel where the slides should look like one set.

This skill asks Claude to plan all N slides up-front, anchored on a single
`style_anchor` block (palette + composition + lighting + character notes) so
every slide carries that prefix into the generator. Each slide also gets:
  - a per-slide role (hook / point_1 / point_2 / .. / cta)
  - a 1-line on-screen caption (the writer's text, not Claude's prose)
  - the actual generator prompt the Tool Router will run.

Falls back to a deterministic per-slide skeleton when no ANTHROPIC_API_KEY
is set so the pipeline keeps working in dev / CI.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any


# Carousel sizes per channel — anchored to what each channel renders well.
DEFAULT_SLIDE_COUNT = 5


def plan_carousel_slides(
    *,
    topic: str,
    pillar: str | None,
    angle: str | None,
    audience: str | None,
    voice_profile: dict | None,
    slide_count: int = DEFAULT_SLIDE_COUNT,
    aspect_ratio: str = "1:1",
) -> list[dict[str, Any]]:
    """Return `slide_count` coordinated slide briefs.

    Each entry: `{role, caption, prompt, slide_index}`.
    """
    slide_count = max(2, min(10, slide_count))

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _default_skeleton(topic, slide_count, aspect_ratio)

    try:
        import anthropic  # noqa: F401
    except ImportError:
        return _default_skeleton(topic, slide_count, aspect_ratio)

    from ventures.content_engine.prompts import render_voice_block

    voice_block = render_voice_block(voice_profile or {})
    style_directive = (
        "STYLE ANCHOR (must apply to every slide):\n"
        "  - Editorial illustration, modern, accessible colour palette.\n"
        "  - One consistent palette across all slides (e.g. deep teal + warm sand + soft red accent).\n"
        "  - No text in the image itself — text overlays are added separately.\n"
        "  - No watermarks, no logos, no stock-photo faces, no body parts cropped at joints.\n"
        f"  - Aspect ratio: {aspect_ratio}.\n"
    )

    user_msg = (
        f"{voice_block}\n\n"
        f"Plan a {slide_count}-slide carousel for the topic below. The slides MUST "
        f"feel like one set: same illustration style, same palette, recurring "
        f"composition motifs.\n\n"
        f"TOPIC: {topic}\n"
        f"PILLAR: {pillar or ''}\n"
        f"ANGLE: {angle or ''}\n"
        f"AUDIENCE: {audience or ''}\n\n"
        f"{style_directive}\n"
        f"For each slide return exactly these keys:\n"
        f"  slide_index (1-based int), "
        f"role ('hook' | 'point_N' | 'cta'), "
        f"caption (the on-screen line a human writer would put on the slide — "
        f"≤80 chars, no emojis), "
        f"prompt (the full image-generation prompt, including the style anchor "
        f"prefix; must reference the slide's specific subject in 1-2 short sentences).\n"
        f"Return strict JSON: a list of {slide_count} objects, no prose, no code fences."
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=2048,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL)
        data = json.loads(raw)
    except Exception:
        return _default_skeleton(topic, slide_count, aspect_ratio)

    slides: list[dict[str, Any]] = []
    for i, entry in enumerate(data[:slide_count]):
        slides.append({
            "slide_index": int(entry.get("slide_index") or (i + 1)),
            "role":        entry.get("role") or _default_role(i, slide_count),
            "caption":     (entry.get("caption") or "")[:120],
            "prompt":      entry.get("prompt") or _default_prompt(topic, i, aspect_ratio),
        })

    # Pad if Claude under-delivered.
    while len(slides) < slide_count:
        slides.append({
            "slide_index": len(slides) + 1,
            "role":        _default_role(len(slides), slide_count),
            "caption":     "",
            "prompt":      _default_prompt(topic, len(slides), aspect_ratio),
        })
    return slides


def _default_role(index: int, total: int) -> str:
    if index == 0:
        return "hook"
    if index == total - 1:
        return "cta"
    return f"point_{index}"


def _default_prompt(topic: str, index: int, aspect_ratio: str) -> str:
    return (
        "Editorial illustration, accessible modern palette (teal + sand + soft red accent), "
        "consistent style across all slides. No text overlays in the image. "
        f"Subject: {topic}, slide {index + 1}. Aspect ratio: {aspect_ratio}."
    )


def _default_skeleton(topic: str, slide_count: int, aspect_ratio: str) -> list[dict[str, Any]]:
    return [
        {
            "slide_index": i + 1,
            "role":        _default_role(i, slide_count),
            "caption":     "",
            "prompt":      _default_prompt(topic, i, aspect_ratio),
        }
        for i in range(slide_count)
    ]
