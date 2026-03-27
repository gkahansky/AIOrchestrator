"""
Skill: generate_promo_copy
Generate four pieces of episode promotional copy from a single podcast episode.

Outputs:
    1. platform_description  — 250-char podcast app description (Apple, Spotify)
    2. audiogram_caption     — short punchy caption for an audiogram clip (Instagram/TikTok)
    3. newsletter_teaser     — 100-150 word email teaser driving listens
    4. linkedin_post         — full LinkedIn post (150-250 words) with hook, insight, CTA

Input:
    episode_context     dict with keys:
                            show_name, episode_title, host_name,
                            niche, audience,
                            transcript (full text),
                            show_notes (optional),
                            brand_voice_injection (optional — from generate_brand_voice cache)

Output:
    {
        "platform_description": str,
        "audiogram_caption":    str,
        "newsletter_teaser":    str,
        "linkedin_post":        str,
        "cost_usd":             float,
    }
"""

from __future__ import annotations

import os


SYSTEM_PROMPT = """\
You are a podcast content strategist who writes promotional copy that converts browsers
into listeners. Your copy is specific, benefit-led, and sounds like a human wrote it —
not a press release. You lead with the most compelling hook from the episode, not a
generic description of topics covered.
"""


def generate_promo_copy(episode_context: dict) -> dict:
    """
    Generate four promo copy pieces for a single episode.
    Requires ANTHROPIC_API_KEY.

    episode_context keys:
        show_name, episode_title, host_name, niche, audience,
        transcript, show_notes (optional), brand_voice_injection (optional)
    """
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_message = _build_prompt(episode_context)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )

    pieces = _parse_response(raw)
    pieces["cost_usd"] = cost_usd
    return pieces


# ─── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(ctx: dict) -> str:
    show        = ctx.get("show_name", "the podcast")
    episode     = ctx.get("episode_title", "this episode")
    host        = ctx.get("host_name", "")
    niche       = ctx.get("niche", "general")
    audience    = ctx.get("audience", "general audience")
    transcript  = (ctx.get("transcript") or "")[:5000]  # cap to keep tokens manageable
    show_notes  = (ctx.get("show_notes") or "").strip()
    brand_voice = (ctx.get("brand_voice_injection") or "").strip()

    host_line       = f"Host: {host}\n" if host else ""
    show_notes_block = f"\nSHOW NOTES:\n{show_notes}\n" if show_notes else ""
    brand_voice_block = f"\n{brand_voice}\n" if brand_voice else ""

    return f"""\
Write four promotional copy pieces for the following podcast episode.

Show: {show}
Episode: {episode}
{host_line}Niche: {niche}
Audience: {audience}
{brand_voice_block}
TRANSCRIPT (excerpt):
{transcript}
{show_notes_block}

Write each piece under its exact label. Do not add any other text between pieces.

PLATFORM DESCRIPTION:
(Exactly 230-250 characters. Used on Apple Podcasts and Spotify. Must fit in one paragraph,
lead with the most compelling hook, and end with a clear benefit.)

AUDIOGRAM CAPTION:
(2-4 lines max. Designed for an Instagram/TikTok audiogram clip. Lead with a punchy quote
or insight from the episode. One CTA line at the end — e.g. "Full episode link in bio.")

NEWSLETTER TEASER:
(100-150 words. Written in first person as if from the host. Shares one specific insight
from the episode that makes the reader want to listen. Ends with a "listen here: [LINK]"
placeholder.)

LINKEDIN POST:
(150-250 words. Hook line first (no "I" opener). Then 2-3 short paragraphs sharing a
specific insight or story from the episode. End with a CTA to listen. Use line breaks
between paragraphs. No hashtag spam — max 3 relevant hashtags at the very end.)
"""


# ─── Response parser ───────────────────────────────────────────────────────────

def _parse_response(text: str) -> dict:
    """
    Extract the four labelled sections from Claude's response.
    Returns whatever was found; missing sections default to empty string.
    """
    labels = {
        "platform_description": "PLATFORM DESCRIPTION:",
        "audiogram_caption":    "AUDIOGRAM CAPTION:",
        "newsletter_teaser":    "NEWSLETTER TEASER:",
        "linkedin_post":        "LINKEDIN POST:",
    }

    result: dict[str, str] = {k: "" for k in labels}
    order = list(labels.keys())

    for i, key in enumerate(order):
        label = labels[key]
        start_idx = text.find(label)
        if start_idx == -1:
            continue
        content_start = start_idx + len(label)
        # Find the start of the next section (or end of text)
        next_start = len(text)
        for next_key in order[i + 1:]:
            nidx = text.find(labels[next_key], content_start)
            if nidx != -1:
                next_start = nidx
                break
        result[key] = text[content_start:next_start].strip()

    return result
