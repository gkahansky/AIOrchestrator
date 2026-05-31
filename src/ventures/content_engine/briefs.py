"""Brief generation — turn a calendar slot into a content brief.

The brief is what the per-channel generator skills (generate_caption_pack,
generate_blog_post, etc.) consume. It bundles: the angle, the audience, the
length budget, the cited sources (from a live web search), and the CTA.
"""
from __future__ import annotations

import os
from typing import Any

from ventures.content_engine.config import (
    CHANNEL_LENGTH_BUDGETS,
    MIN_SOURCES_PER_BRIEF,
)


def _fetch_sources(topic: str, max_results: int = 5) -> list[dict]:
    """Pull cited sources from SerpAPI for the topic. Degrades to empty list.

    Reuses the existing `aiplatform.skills.research.web_search.web_search`
    skill — graceful no-op when SERPAPI_KEY isn't set.
    """
    if not topic or not os.environ.get("SERPAPI_KEY"):
        return []

    try:
        from aiplatform.skills.research.web_search import google_search
    except ImportError:
        return []

    try:
        # Bias toward fresh (past 12 months) so cited stats aren't stale.
        data = google_search(query=topic, num_results=max_results, tbs="qdr:y")
    except Exception:
        return []

    results = (data or {}).get("organic_results") or []

    out: list[dict] = []
    for r in results[:max_results]:
        snippet = r.get("snippet") or r.get("description") or ""
        out.append({
            "url":       r.get("link") or r.get("url") or "",
            "title":     r.get("title") or "",
            "relevance": snippet[:240],
            "date":      r.get("date") or "",
        })
    return out


def build_brief(
    slot: dict,
    brand: dict,
    target_persona: dict | None = None,
) -> dict[str, Any]:
    """Compose a brief for one calendar slot.

    `slot` is one entry from `ContentStrategy.calendar_json`.
    `brand` is the `ContentBrand` row as a dict (or the seed dict).
    """
    channel = slot.get("channel", "linkedin_page")
    fmt     = slot.get("format", "post")
    topic   = slot.get("topic") or slot.get("pillar") or "Accessibility"

    sources = _fetch_sources(topic, max_results=4)
    audience = target_persona or (brand.get("target_personas") or [{}])[0]
    budget = CHANNEL_LENGTH_BUDGETS.get(channel, {"min_chars": 300, "max_chars": 1500})

    cta_map = {
        "linkedin_page":      "End with a single question that invites a reply, not a sales pitch.",
        "facebook_page":      "End with a short call-to-action linking to the relevant echoforge.biz page.",
        "instagram_business": "End with a single-line CTA + 5–10 relevant hashtags.",
        "youtube_channel":    "End with 'Subscribe for one accessibility tip per week' and link the audit page in the description.",
    }

    return {
        "slot_index": slot.get("index"),
        "channel":    channel,
        "format":     fmt,
        "pillar":     slot.get("pillar"),
        "topic":      topic,
        "angle":      slot.get("angle"),
        "hook":       slot.get("hook"),
        "audience":   {
            "name":        audience.get("name"),
            "description": audience.get("description"),
        },
        "length":     {"min_chars": budget.get("min_chars"), "max_chars": budget.get("max_chars")},
        "cta":        cta_map.get(channel, ""),
        "sources":    sources,
        "min_sources": MIN_SOURCES_PER_BRIEF,
        "needs_more_sources": len(sources) < MIN_SOURCES_PER_BRIEF,
    }
