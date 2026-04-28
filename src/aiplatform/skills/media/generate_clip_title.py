"""
Platform skill: generate_clip_title

Generates a platform-optimised title for a short video clip using Claude.
Returns 3 variants and picks the strongest. Venture-agnostic.
"""

import json
import os
import re

import anthropic


_PLATFORM_RULES = {
    "tiktok":         {"max_chars": 100,  "style": "hook word, pattern interrupt, informal"},
    "instagram":      {"max_chars": 80,   "style": "emoji-friendly, punchy, emotional"},
    "youtube_shorts": {"max_chars": 70,   "style": "keyword-rich, curiosity gap, clear value"},
    "linkedin":       {"max_chars": 120,  "style": "professional, insight-driven, no fluff"},
}
_DEFAULT_PLATFORM = {"max_chars": 100, "style": "engaging, clear, direct"}


def generate_clip_title(
    transcript_chunk: str,
    hook: str,
    platform: str = "tiktok",
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """
    Generate a short-form video title for the given clip and platform.

    Args:
        transcript_chunk:  The transcript text for this clip.
        hook:              The virality hook identified during scoring.
        platform:          "tiktok" | "instagram" | "youtube_shorts" | "linkedin".
        anthropic_api_key: Optional override.
        model:             Claude model.

    Returns:
        {
            "title": str,              # Best title
            "variants": List[str],     # All 3 generated variants
            "platform": str,
            "cost_usd": float,
        }
    """
    client = anthropic.Anthropic(api_key=anthropic_api_key or os.environ["ANTHROPIC_API_KEY"])

    rules = _PLATFORM_RULES.get(platform, _DEFAULT_PLATFORM)

    prompt = f"""\
Generate 3 title variants for a {platform} short-form video clip.

CLIP HOOK: {hook}
TRANSCRIPT: {transcript_chunk[:600]}

PLATFORM RULES for {platform}:
- Max {rules["max_chars"]} characters
- Style: {rules["style"]}
- Titles must stand alone (no context needed)
- No generic phrases like "You won't believe..." or "Check this out"

Return JSON only:
{{"titles": ["title 1", "title 2", "title 3"], "best_index": 0}}

Where best_index is the index of the strongest title."""

    response = anthropic.Anthropic(
        api_key=anthropic_api_key or os.environ["ANTHROPIC_API_KEY"]
    ).messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed = json.loads(raw)

    titles = parsed.get("titles", [])
    best_index = int(parsed.get("best_index", 0))
    best_index = max(0, min(best_index, len(titles) - 1)) if titles else 0
    best_title = titles[best_index] if titles else hook[:rules["max_chars"]]

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = round(input_tokens * 3e-6 + output_tokens * 15e-6, 4)

    return {
        "title": best_title,
        "variants": titles,
        "platform": platform,
        "cost_usd": cost_usd,
    }
