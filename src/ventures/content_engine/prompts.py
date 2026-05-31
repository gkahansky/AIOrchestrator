"""System prompts for the Content Engine.

These prompts are pillar-aware but brand-agnostic — the brand's voice profile
is injected at call time as a structured guide block.
"""
from __future__ import annotations

import json


def strategy_system_prompt() -> str:
    return (
        "You are an editorial strategist for a B2B content team. You design "
        "30-day social calendars that look hand-written, not algorithmic.\n\n"
        "Hard rules:\n"
        " - Every calendar slot must reference a SPECIFIC angle (a WCAG number, "
        "a real failure pattern, a regulator, a named tool) — never a generic "
        "topic like 'accessibility tips'.\n"
        " - Distribute formats sensibly across the week. No more than one "
        "post per channel per day.\n"
        " - Respect the brand's theme_weights — if accessibility weight is 0.7, "
        "at least 70% of slots must be accessibility-centric.\n"
        " - Never invent statistics. If a slot needs a number, mark it "
        "'NEEDS_CITATION' in the brief.\n"
        "Output strict JSON only."
    )


def brief_system_prompt() -> str:
    return (
        "You turn a single calendar slot into a content brief a writer would "
        "use. The brief must include: the specific angle, the audience, the "
        "channel + format, the length target, the call-to-action, and 2–4 "
        "cited sources (URL + 1-sentence relevance). Sources MUST come from "
        "the live search results provided. Output strict JSON only."
    )


def critic_system_prompt() -> str:
    return (
        "You are a brutal editor who screens copy for AI-generated tells.\n"
        "Score the draft 0–100 (100 = indistinguishable from a senior human writer).\n"
        "Penalise heavily:\n"
        "  - Cliché openers ('In today's fast-paced world', 'Let's dive into…').\n"
        "  - Generic verbs (embrace, leverage, unlock, navigate, harness).\n"
        "  - The 'It's not just X, it's Y' pattern.\n"
        "  - Em-dash overuse (>1 per 80 words).\n"
        "  - Perfect parallelism in a list of 3 ('Faster, smarter, simpler.').\n"
        "  - Adjective stacking with no concrete noun.\n"
        "  - Hedging filler ('It's important to note', 'In essence').\n"
        "  - Closing 'In conclusion…' or 'To wrap up…'.\n"
        "Reward:\n"
        "  - Concrete specifics (a real screen-reader transcript, a real "
        "WCAG number, a named tool).\n"
        "  - Varied sentence length.\n"
        "  - A point of view, not a summary.\n"
        "Return strict JSON with: score, flagged_spans (list of {text, reason}), "
        "rewrite_suggestion (1–2 sentence rewrite of the worst offender)."
    )


def render_voice_block(voice_profile: dict | None) -> str:
    """Render the brand voice profile as a prompt-ready block.

    Mirrors the shape produced by `generate_brand_voice.py` and seeded in
    `config.ECHOFORGE_ACCESSIBILITY_SEED.voice_profile_json`. Empty profile
    yields an empty string so callers don't have to guard.
    """
    if not voice_profile:
        return ""

    sections: list[str] = ["BRAND VOICE GUIDE:"]
    label_map = {
        "tone":              "Tone & Personality",
        "vocabulary":        "Vocabulary & Language",
        "sentence_style":    "Sentence Style",
        "rhetorical_moves":  "Rhetorical Moves",
        "content_principles": "Content Principles",
        "topics_to_avoid":   "Topics to Avoid",
    }
    for key, label in label_map.items():
        value = voice_profile.get(key)
        if not value:
            continue
        sections.append(f"\n{label}:")
        if isinstance(value, list):
            sections.extend(f"  - {item}" for item in value)
        else:
            sections.append(f"  {value}")
    return "\n".join(sections)


def render_brief_for_generation(brief: dict, voice_profile: dict | None) -> str:
    """Compose the per-item generation prompt body (caller adds system prompt)."""
    voice = render_voice_block(voice_profile)
    sources = brief.get("sources") or []
    source_block = "\n".join(
        f"  [{i+1}] {s.get('url', '')} — {s.get('relevance', '')}"
        for i, s in enumerate(sources)
    ) or "  (no sources cited — flag this in the draft)"

    return (
        f"{voice}\n\n"
        f"BRIEF:\n{json.dumps(brief, indent=2, ensure_ascii=False)}\n\n"
        f"CITED SOURCES (you MUST reference at least one explicitly):\n{source_block}"
    )
