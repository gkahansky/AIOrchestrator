"""
Platform skill: generate_thumbnail_headline

Generates a YouTube-style clickbait thumbnail headline and the single word
to visually emphasise (bold/colour) from a clip hook + transcript excerpt.
Venture-agnostic.
"""

import json
import os
import re

from anthropic import Anthropic


def generate_thumbnail_headline(
    hook: str,
    transcript_chunk: str = "",
    show_name: str = "",
    guest_name: str = "",
    host_name: str = "",
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
    platform: str = "default",
) -> dict:
    """
    Generate a viral thumbnail headline and emphasis word for a short clip.

    Args:
        hook:              One-line viral hook from virality scoring.
        transcript_chunk:  Clip transcript text (first 300 chars used).
        show_name:         Podcast / show name (optional context).
        guest_name:        Guest name (optional context).
        host_name:         Host name (optional context).
        anthropic_api_key: Anthropic API key (falls back to ANTHROPIC_API_KEY env var).
        model:             Claude model to use.
        platform:          Target platform ("default" | "youtube" | "tiktok" | etc.).
                           Reserved for future per-platform style rules; currently
                           all platforms share the same compositor.

    Returns:
        {
            "headline":       str,   # 4-7 ALL-CAPS words, e.g. "AI WILL MAKE YOU DUMB"
            "highlight_word": str,   # single word to render in accent colour
            "platform":       str,   # echoes the input platform param
        }
    """
    api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)

    context_parts = []
    if show_name:
        context_parts.append(f"Show: {show_name}")
    if host_name:
        context_parts.append(f"Host: {host_name}")
    if guest_name:
        context_parts.append(f"Guest: {guest_name}")
    context_line = " | ".join(context_parts)

    prompt = (
        "You are a YouTube thumbnail designer. Generate three things for a short video clip.\n\n"
        + (f"Context: {context_line}\n" if context_line else "")
        + f"Clip hook: {hook}\n"
        + (f"Transcript: {transcript_chunk[:300]}\n\n" if transcript_chunk else "\n")
        + "1. HEADLINE — 4 to 7 words, ALL CAPS, clickbait/curiosity-gap style.\n"
        "   No full sentences, no punctuation except one optional em-dash.\n\n"
        "2. HIGHLIGHT_WORD — ONE word from the headline to render in bold accent colour.\n\n"
        "3. BG_PROMPT — 40-60 words describing a unique cinematic background image for Gemini Imagen.\n"
        "   Rules for bg_prompt:\n"
        "   - Visually represent the clip topic with SPECIFIC imagery (not generic podcast/studio)\n"
        "   - Specify dominant colours, lighting mood, and one concrete visual metaphor\n"
        "   - Abstract/environmental — no people, no faces, no readable text\n"
        "   - Vary style dramatically: could be neon cityscape, deep space, stormy ocean, \n"
        "     ancient ruins, molten lava, digital matrix, golden hour desert, etc.\n"
        "   - Match the emotional tone: tense=dark/red, inspirational=warm/gold, \n"
        "     tech=blue neon, nature=greens, luxury=black/gold\n"
        "   - Always end with: 'Vertical portrait 9:16. No people. No text.'\n\n"
        "Respond with ONLY valid JSON:\n"
        '{"headline": "YOUR HEADLINE HERE", "highlight_word": "WORD", '
        '"bg_prompt": "Specific cinematic description... Vertical portrait 9:16. No people. No text."}'
    )

    response = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    # Extract JSON robustly
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            headline = str(data.get("headline", hook[:50])).upper()
            highlight = str(data.get("highlight_word", "")).upper()
            bg_prompt = str(data.get("bg_prompt", "")).strip()
            # Ensure highlight_word is actually in the headline
            if highlight not in headline:
                words = headline.split()
                highlight = words[-1] if words else ""
            return {
                "headline": headline,
                "highlight_word": highlight,
                "bg_prompt": bg_prompt,
                "platform": platform,
            }
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: truncate hook, no custom bg_prompt
    fallback = hook[:50].upper()
    words = fallback.split()
    return {
        "headline": fallback,
        "highlight_word": words[-1] if words else "",
        "bg_prompt": "",
        "platform": platform,
    }
