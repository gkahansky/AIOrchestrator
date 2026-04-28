"""
Platform skill: generate_video_description

Generates a platform-appropriate description, hashtags, and CTA for a short clip.
Venture-agnostic.
"""

import json
import os
import re

import anthropic


_PLATFORM_CAPS = {
    "tiktok":         {"max_chars": 2200, "hashtags": 5,  "style": "casual, energetic, community-driven"},
    "instagram":      {"max_chars": 2200, "hashtags": 10, "style": "inspirational, story-driven, hashtag-rich"},
    "youtube_shorts": {"max_chars": 5000, "hashtags": 3,  "style": "SEO-optimised, clear value prop, subscribe CTA"},
    "linkedin":       {"max_chars": 3000, "hashtags": 3,  "style": "professional, insight-focused, thought leadership"},
}
_DEFAULT = {"max_chars": 2000, "hashtags": 5, "style": "engaging, clear"}


def generate_video_description(
    transcript_chunk: str,
    title: str,
    platform: str = "tiktok",
    brand_voice: str = "",
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """
    Generate a platform-appropriate description for a short-form clip.

    Args:
        transcript_chunk:  Clip transcript text.
        title:             The clip title (already generated).
        platform:          "tiktok" | "instagram" | "youtube_shorts" | "linkedin".
        brand_voice:       Optional brand voice guide injection.
        anthropic_api_key: Optional override.
        model:             Claude model.

    Returns:
        {
            "description": str,
            "hashtags": List[str],
            "cta": str,
            "platform": str,
            "cost_usd": float,
        }
    """
    client = anthropic.Anthropic(api_key=anthropic_api_key or os.environ["ANTHROPIC_API_KEY"])

    caps = _PLATFORM_CAPS.get(platform, _DEFAULT)
    voice_block = f"\n\nBRAND VOICE:\n{brand_voice}" if brand_voice else ""

    prompt = f"""\
Write a {platform} description for this short-form video clip.

CLIP TITLE: {title}
TRANSCRIPT: {transcript_chunk[:600]}{voice_block}

REQUIREMENTS:
- Max {caps["max_chars"]} characters total
- Include exactly {caps["hashtags"]} relevant hashtags
- Style: {caps["style"]}
- End with a clear call-to-action (follow, comment, share, etc.)

Return JSON only:
{{"description": "...", "hashtags": ["#tag1", "#tag2"], "cta": "..."}}"""

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed = json.loads(raw)

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = round(input_tokens * 3e-6 + output_tokens * 15e-6, 4)

    return {
        "description": parsed.get("description", ""),
        "hashtags": parsed.get("hashtags", []),
        "cta": parsed.get("cta", ""),
        "platform": platform,
        "cost_usd": cost_usd,
    }
