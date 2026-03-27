"""
Skill: generate_brand_voice
Analyse 2-3 podcast episode transcripts and produce a structured Brand Voice Guide.

The guide captures tone, vocabulary patterns, sentence style, content principles,
and topics-to-avoid — everything a writer needs to produce on-brand content without
hearing the episodes themselves.

Output is cached as JSON so future orders for the same client can reuse the guide
without another API call.

Input:
    transcripts         list[str]  — 2-3 episode transcript texts
    show_name           str
    niche               str        — e.g. "business", "tech", "health"
    audience            str        — e.g. "early-stage SaaS founders"
    host_name           str        — optional
    cache_path          str|Path   — optional; if set, guide is saved here as JSON

Output:
    {
        "guide":     str,   # full Brand Voice Guide as formatted text
        "summary":   dict,  # structured extract for downstream prompt injection
        "cost_usd":  float,
        "cached":    bool,  # True if loaded from cache rather than generated
    }
"""

from __future__ import annotations

import json
import os
from pathlib import Path


SYSTEM_PROMPT = """\
You are a brand voice analyst specialising in podcast content. Your job is to analyse
episode transcripts and extract a reusable Brand Voice Guide that any writer can follow
to produce content that sounds authentically like the show — without ever having listened
to an episode.

Be specific. Generic observations ("conversational tone", "friendly voice") are useless.
Surface the actual vocabulary, sentence structures, and rhetorical moves this host uses.
"""


def generate_brand_voice(
    transcripts: list[str],
    show_name: str,
    niche: str = "general",
    audience: str = "general audience",
    host_name: str = "",
    cache_path: str | Path | None = None,
) -> dict:
    """
    Analyse transcripts and produce a Brand Voice Guide.
    Returns cached result if cache_path exists and is readable.
    Requires ANTHROPIC_API_KEY.
    """
    # ── Cache check ──────────────────────────────────────────────────────────
    if cache_path:
        cache_path = Path(cache_path)
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return {**cached, "cached": True}

    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    transcript_block = _format_transcripts(transcripts)
    user_message = _build_prompt(show_name, niche, audience, host_name, transcript_block)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # Claude Sonnet 4.6: $3/M input + $15/M output
    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )

    summary = _extract_summary(raw)

    result = {
        "guide":    raw,
        "summary":  summary,
        "cost_usd": cost_usd,
        "cached":   False,
    }

    # ── Write cache ──────────────────────────────────────────────────────────
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


# ─── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    show_name: str,
    niche: str,
    audience: str,
    host_name: str,
    transcript_block: str,
) -> str:
    host_line = f"Host: {host_name}\n" if host_name else ""
    return f"""\
Analyse the following podcast transcripts and produce a Brand Voice Guide for "{show_name}".

Show details:
- Niche: {niche}
- Audience: {audience}
{host_line}
TRANSCRIPTS:
{transcript_block}

Produce the Brand Voice Guide with exactly these sections:

## Tone & Personality
Describe the overall tone in 3-5 specific adjectives, each followed by a one-sentence
explanation with a direct example from the transcripts.

## Vocabulary & Language Patterns
List 10-15 words or phrases this show uses frequently or distinctively.
Note any words or expressions they conspicuously avoid.

## Sentence Style
Describe typical sentence length (short/medium/long), rhythm, and structure.
Give 2-3 verbatim examples that best capture the style.

## How the Host Frames Ideas
Describe the rhetorical moves used to introduce topics, make arguments, or land points.
Examples: anecdote-first, question-led, direct assertion, counter-argument structure.

## Content Principles
3-5 beliefs or rules this show consistently operates by. What does it always do?
What does it never do?

## Topics to Avoid
Subjects, framings, or angles this show steers clear of — based on what's absent
from the transcripts or contradicted by the tone.

## Prompt Injection Block
Write a concise 3-5 sentence paragraph (labelled BRAND VOICE INJECTION) that can be
prepended to any content generation prompt to ensure on-brand output. This is the
distilled version writers and AI tools will use directly.
"""


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _format_transcripts(transcripts: list[str]) -> str:
    parts = []
    for i, t in enumerate(transcripts[:3], 1):
        trimmed = t.strip()[:6000]  # cap each transcript to avoid token overflow
        parts.append(f"--- TRANSCRIPT {i} ---\n{trimmed}")
    return "\n\n".join(parts)


def _extract_summary(guide_text: str) -> dict:
    """
    Pull the BRAND VOICE INJECTION paragraph out of the guide for downstream use.
    Falls back to the first 500 chars of the guide if the section isn't found.
    """
    marker = "BRAND VOICE INJECTION"
    lower = guide_text.lower()
    idx = lower.find(marker.lower())
    if idx != -1:
        block = guide_text[idx + len(marker):].strip().lstrip(":").strip()
        # Take up to the next ## heading or 800 chars
        end = block.find("\n##")
        injection = block[:end].strip() if end != -1 else block[:800].strip()
    else:
        injection = guide_text[:500].strip()

    return {"brand_voice_injection": injection}
