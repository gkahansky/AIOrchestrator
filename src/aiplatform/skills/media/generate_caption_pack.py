"""
Platform skill: generate_caption_pack

Generates per-platform social media captions from a transcript + episode context.
Each platform has its own tone, format, and length constraints.
Venture-agnostic — never references any specific venture.
"""

import os

import anthropic


_SYSTEM_PROMPT = """\
You are an expert social media copywriter who creates platform-native captions \
from audio and video content. You know exactly what performs on each platform and \
write with precision, impact, and platform-appropriate style. \
Follow output structure instructions exactly.\
"""

_PLATFORM_SPECS = {
    "linkedin": {
        "label": "LinkedIn",
        "instruction": (
            "Professional tone. 150–300 words. Start with a thought-provoking hook. "
            "3–4 insight sentences. End with a question or CTA. Max 5 hashtags at the end. "
            "No emoji overload — 0–2 tasteful emojis max."
        ),
    },
    "facebook": {
        "label": "Facebook",
        "instruction": (
            "Conversational, approachable tone aimed at small-to-mid business owners. "
            "80–180 words. Open with a relatable hook (a question or a small observation). "
            "2–4 short paragraphs with concrete examples. End with a CTA that links to "
            "the most relevant landing page. 0–3 hashtags only. 1–2 emojis allowed if natural."
        ),
    },
    "instagram": {
        "label": "Instagram",
        "instruction": (
            "Conversational, warm tone. 100–150 words. Strong hook in first line. "
            "3–5 sentences of value. CTA in last line. End with 8–12 relevant hashtags "
            "on a new line. 3–5 emojis woven in naturally."
        ),
    },
    "twitter": {
        "label": "Twitter/X",
        "instruction": (
            "Punchy and direct. Max 270 characters (excluding hashtags). "
            "Lead with a bold statement or question. 1–2 hashtags. "
            "End with [LINK]. No filler words."
        ),
    },
    "tiktok": {
        "label": "TikTok",
        "instruction": (
            "Hook in the first 3 words — make it urgent or surprising. "
            "80–100 words total. Casual, energetic tone. "
            "3–5 trending-style hashtags. 3–5 emojis. "
            "CTA: 'Follow for more' or 'Watch the full episode'."
        ),
    },
    "youtube": {
        "label": "YouTube",
        "instruction": (
            "Keyword-rich description, 100–150 words. "
            "First 2 sentences contain primary keywords. "
            "Summarise what viewers will learn. "
            "CTA: subscribe or watch next video. "
            "Include 3–5 relevant keywords at the end prefixed with #."
        ),
    },
}


def generate_caption_pack(
    transcript: str,
    context: dict,
    platforms: list[str] | None = None,
    captions_per_platform: int = 3,
    brand_voice_injection: str = "",
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> dict:
    """
    Generate per-platform social media captions.

    Args:
        transcript:            Full transcript text.
        context: {
            title:             Episode or video title.
            host_name:         Host name.
            guest_name:        Guest name (optional).
            niche:             Content niche.
            audience:          Target audience.
            show_name:         Podcast/channel name.
            show_notes:        Summary of the episode (optional, speeds up generation).
        }
        platforms:             List from ["linkedin","instagram","twitter","tiktok","youtube"].
                               Defaults to all five.
        captions_per_platform: Number of caption variants per platform (1–5).
        brand_voice_injection: Brand voice context to prepend (optional).
        anthropic_api_key:     Falls back to ANTHROPIC_API_KEY env var.
        model:                 Claude model.
        max_tokens:            Max output tokens.

    Returns:
        {
            "captions": {
                "linkedin":  [str, ...],
                "instagram": [str, ...],
                ...
            },
            "cost_usd": float,
        }
    """
    if platforms is None:
        platforms = list(_PLATFORM_SPECS.keys())

    unknown = [p for p in platforms if p not in _PLATFORM_SPECS]
    if unknown:
        raise ValueError(f"Unknown platforms: {unknown}. Valid: {list(_PLATFORM_SPECS)}")

    api_key = anthropic_api_key or os.environ["ANTHROPIC_API_KEY"]
    client = anthropic.Anthropic(api_key=api_key)

    brand_block = ""
    if brand_voice_injection:
        brand_block = f"\nBRAND VOICE (apply throughout):\n{brand_voice_injection}\n"

    show_notes = context.get("show_notes", "")
    content_block = (
        f"EPISODE SUMMARY:\n{show_notes[:1500]}\n\nTRANSCRIPT EXCERPT:\n{transcript[:4000]}"
        if show_notes
        else f"TRANSCRIPT:\n{transcript[:6000]}"
    )

    platform_blocks = ""
    for platform in platforms:
        spec = _PLATFORM_SPECS[platform]
        platform_blocks += (
            f"\n===PLATFORM: {platform.upper()}===\n"
            f"({spec['label']} — {captions_per_platform} variant(s))\n"
            f"{spec['instruction']}\n"
            f"Write {captions_per_platform} distinct caption variant(s), "
            f"each preceded by 'VARIANT N:' on its own line.\n"
        )

    prompt = f"""\
Create social media caption packs for the content below.

TITLE: {context.get("title", "Episode")}
SHOW: {context.get("show_name", "")}
HOST: {context.get("host_name", "")}
GUEST: {context.get("guest_name", "") or "N/A"}
NICHE: {context.get("niche", "general")}
AUDIENCE: {context.get("audience", "general audience")}
{brand_block}
{content_block}

---
Generate captions for each platform below. Each platform section starts with its \
===PLATFORM: NAME=== marker. Write exactly {captions_per_platform} variant(s) per platform.

{platform_blocks}
"""

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    captions = _parse_response(raw, platforms, captions_per_platform)

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )
    return {"captions": captions, "cost_usd": cost_usd}


def _parse_response(text: str, platforms: list[str], count: int) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {p: [] for p in platforms}
    current_platform: str | None = None
    current_variant_lines: list[str] = []
    current_variants: list[str] = []

    def flush_variant():
        if current_variant_lines:
            current_variants.append("\n".join(current_variant_lines).strip())
            current_variant_lines.clear()

    def flush_platform():
        if current_platform and current_platform in result:
            flush_variant()
            result[current_platform] = current_variants[:]
            current_variants.clear()

    for line in text.split("\n"):
        stripped = line.strip()

        # Platform marker
        if stripped.startswith("===PLATFORM:") and stripped.endswith("==="):
            flush_platform()
            current_variant_lines.clear()
            current_variants.clear()
            name = stripped[len("===PLATFORM:"):].rstrip("=").strip().lower()
            current_platform = name if name in platforms else None
            continue

        # Variant marker
        if current_platform and stripped.startswith("VARIANT ") and stripped.endswith(":"):
            flush_variant()
            current_variant_lines.clear()
            continue

        if current_platform:
            current_variant_lines.append(line)

    flush_platform()
    return result
