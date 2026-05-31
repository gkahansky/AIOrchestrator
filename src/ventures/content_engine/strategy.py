"""Strategy generation — turn a brand into a 30-day editorial calendar.

Reuses `generate_social_calendar.py` where it fits, but the Content Engine
needs richer per-slot structure (pillar, channel, format, theme tag) than
the shared skill returns, so this module wraps it.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ventures.content_engine.config import (
    CHANNEL_FORMATS,
    DEFAULT_PILLARS,
    DEFAULT_STRATEGY_PERIOD_DAYS,
    VALID_CHANNELS,
)
from ventures.content_engine.prompts import strategy_system_prompt


def _pillar_for_index(i: int, theme_weights: dict) -> str:
    """Pick a pillar respecting the theme weight (default 70% accessibility)."""
    accessibility_weight = float((theme_weights or {}).get("accessibility", 0.7))
    # First N% of slots are accessibility pillars, remainder are adjacent.
    # Pillar 4 ("Mythbuster") and 0–2 are accessibility; 4 is the swing slot.
    accessibility_pillars = DEFAULT_PILLARS[:4]
    adjacent_pillars = DEFAULT_PILLARS[4:]
    # Deterministic interleave so the first 70% of indices map to accessibility.
    threshold = max(1, int(accessibility_weight * 10))
    bucket = i % 10
    if bucket < threshold:
        return accessibility_pillars[i % len(accessibility_pillars)]
    return adjacent_pillars[i % max(1, len(adjacent_pillars))]


def _default_calendar(
    period_days: int,
    channel_cadence: dict[str, int],
    theme_weights: dict,
    start_date: datetime,
) -> list[dict]:
    """Build a deterministic calendar skeleton with no LLM call.

    Used as the fallback when ANTHROPIC_API_KEY isn't set, and as the seed
    when the LLM enrichment runs (the LLM fills `topic` / `angle` / `hook`
    per slot but does NOT reshape the cadence).
    """
    slots: list[dict] = []
    weeks = max(1, period_days // 7)

    slot_idx = 0
    for week in range(weeks):
        for channel, posts_per_week in (channel_cadence or {}).items():
            if channel not in VALID_CHANNELS:
                continue
            allowed_formats = CHANNEL_FORMATS.get(channel, ("post",))
            for n in range(int(posts_per_week or 0)):
                day_offset = week * 7 + (n * (7 // max(1, posts_per_week)))
                slot_date = start_date + timedelta(days=day_offset)
                slots.append({
                    "index":   slot_idx,
                    "date":    slot_date.date().isoformat(),
                    "channel": channel,
                    "format":  allowed_formats[n % len(allowed_formats)],
                    "pillar":  _pillar_for_index(slot_idx, theme_weights),
                    "topic":   None,    # filled by LLM enrichment
                    "angle":   None,
                    "hook":    None,
                })
                slot_idx += 1
    return slots


def _enrich_with_llm(slots: list[dict], brand_seed: dict) -> list[dict]:
    """Ask Claude to fill in topic/angle/hook per slot. Falls back to skeleton."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not slots:
        return slots

    try:
        from anthropic import Anthropic
    except ImportError:
        return slots

    client = Anthropic(api_key=api_key)
    skeleton = [
        {"index": s["index"], "channel": s["channel"], "format": s["format"], "pillar": s["pillar"]}
        for s in slots
    ]
    user_msg = (
        f"BRAND:\n{json.dumps({k: brand_seed.get(k) for k in ('name', 'description', 'target_personas', 'theme_weights')}, ensure_ascii=False)}\n\n"
        f"SLOTS TO FILL ({len(skeleton)}):\n{json.dumps(skeleton, ensure_ascii=False)}\n\n"
        "For each slot, return: index, topic (specific — e.g. 'WCAG 2.5.3 Label in Name failure on accordion buttons'), "
        "angle (one sentence about the point of view), hook (the first line of the post).\n"
        "Return strict JSON: a list of objects with those four keys. No prose, no code fences."
    )

    try:
        resp = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=4096,
            system=strategy_system_prompt(),
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL)
        enrichment = json.loads(raw)
        by_index = {int(e["index"]): e for e in enrichment if "index" in e}
        for slot in slots:
            extra = by_index.get(slot["index"])
            if extra:
                slot["topic"] = extra.get("topic") or slot["topic"]
                slot["angle"] = extra.get("angle") or slot["angle"]
                slot["hook"]  = extra.get("hook")  or slot["hook"]
    except Exception:
        # Fall back to skeleton — the human will fill topics in the UI.
        pass

    return slots


def generate_calendar(
    brand_seed: dict,
    channel_cadence: dict[str, int] | None = None,
    period_days: int = DEFAULT_STRATEGY_PERIOD_DAYS,
    start_date: datetime | None = None,
) -> dict[str, Any]:
    """Build a draft strategy for a brand.

    Returns the shape stored on `ContentStrategy.calendar_json` (list of slots)
    + the sibling fields the router uses to populate the row.
    """
    cadence = channel_cadence or brand_seed.get("channel_cadence") or {}
    start = start_date or datetime.now(timezone.utc)
    theme_weights = brand_seed.get("theme_weights") or {}

    slots = _default_calendar(period_days, cadence, theme_weights, start)
    slots = _enrich_with_llm(slots, brand_seed)

    return {
        "title": f"{brand_seed.get('name', 'Brand')} — {period_days}-day calendar",
        "period_days": period_days,
        "pillars": list(DEFAULT_PILLARS),
        "channel_cadence": cadence,
        "calendar": slots,
    }
