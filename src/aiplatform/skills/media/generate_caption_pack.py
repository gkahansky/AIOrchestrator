"""
Platform skill: generate_caption_pack

Generates per-platform social media captions from a transcript + episode context.
Each platform has its own tone, format, and length constraints.
Venture-agnostic — never references any specific venture.

Response format: JSON. The model returns
    {"linkedin": ["...", "..."], "instagram": ["..."], ...}
and we fall back to the legacy `===PLATFORM:` text parser when JSON is malformed,
so existing callers see the same `{"captions": {...}}` shape regardless of which
path produced it.
"""

import json
import os
import re

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

    platform_specs_block = ""
    for platform in platforms:
        spec = _PLATFORM_SPECS[platform]
        platform_specs_block += (
            f'\n- "{platform}" ({spec["label"]}): {spec["instruction"]}'
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
PLATFORM SPECS (write {captions_per_platform} distinct caption variant(s) for each):
{platform_specs_block}

OUTPUT FORMAT — strict JSON only, no markdown fences, no prose before or after:

{{
{','.join(f'  "{p}": [string, ...]' for p in platforms)}
}}

Each key MUST match the lowercase platform id exactly. Each value MUST be an \
array of {captions_per_platform} caption string(s). The caption strings are the \
final copy — no preamble, no headers, no labels."""

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    captions, parse_note = _parse_response(raw, platforms, captions_per_platform)

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )
    return {
        "captions":   captions,
        "cost_usd":   cost_usd,
        "raw":        raw,         # always returned so the caller can persist on parse failure
        "parse_note": parse_note,  # "json" | "text_fallback" | "neither" — describes which path won
    }


def _parse_response(
    text: str, platforms: list[str], count: int,
) -> tuple[dict[str, list[str]], str]:
    """Parse Claude's response. Returns (captions_by_platform, parse_note).

    parse_note ∈ {"json", "text_fallback", "neither"} — describes which path
    produced the result. Callers can persist this for debugging when the
    captions list is empty.

    Tries JSON first (current prompt asks for JSON). Falls back to the
    legacy `===PLATFORM:` text parser for resilience if the model wraps the
    JSON in markdown fences or omits a platform key.
    """
    json_result = _parse_json(text, platforms, count)
    if json_result and any(json_result.get(p) for p in platforms):
        # JSON parse populated at least one platform — trust it.
        return json_result, "json"

    text_result = _parse_text(text, platforms, count)
    if any(text_result.get(p) for p in platforms):
        return text_result, "text_fallback"

    # Both parsers came up empty — return the JSON result shape so the caller
    # has the expected keys, plus a parse_note the caller can surface in
    # error_message alongside the raw response snippet.
    empty: dict[str, list[str]] = {p: [] for p in platforms}
    return empty, "neither"


# ── JSON path ────────────────────────────────────────────────────────────────

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _parse_json(text: str, platforms: list[str], count: int) -> dict[str, list[str]] | None:
    """Try to extract a JSON object mapping platform → list[str]."""
    candidate = text.strip()
    # If the model wrapped it in markdown, strip the fence first.
    m = _JSON_FENCE_RE.search(candidate)
    if m:
        candidate = m.group(1).strip()

    # Find the first { ... } block in the candidate.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    candidate = candidate[start:end + 1]

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    result: dict[str, list[str]] = {p: [] for p in platforms}
    for key, value in data.items():
        normalized = (key or "").strip().lower()
        if normalized not in result:
            continue
        if isinstance(value, str):
            result[normalized] = [value.strip()] if value.strip() else []
        elif isinstance(value, list):
            result[normalized] = [str(v).strip() for v in value if str(v).strip()]
    return result


# ── Legacy text path ─────────────────────────────────────────────────────────

def _parse_text(text: str, platforms: list[str], count: int) -> dict[str, list[str]]:
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

        # Platform marker — accept several variants the model may produce.
        marker_name = _extract_platform_marker(stripped)
        if marker_name is not None:
            flush_platform()
            current_variant_lines.clear()
            current_variants.clear()
            current_platform = marker_name if marker_name in platforms else None
            continue

        # Variant marker — accept "VARIANT 1:", "Variant 1.", "1.", "1)".
        if current_platform and _is_variant_marker(stripped):
            flush_variant()
            current_variant_lines.clear()
            continue

        if current_platform:
            current_variant_lines.append(line)

    flush_platform()
    return result


_VARIANT_LINE_RE = re.compile(r"^(?:variant\s*\d+\s*[:.\-)]|\d+\s*[.)])\s*$", re.IGNORECASE)


def _is_variant_marker(stripped: str) -> bool:
    return bool(_VARIANT_LINE_RE.match(stripped))


def _extract_platform_marker(stripped: str) -> str | None:
    """Return the lowercase platform name if `stripped` looks like a marker."""
    # Strip leading markdown emphasis / heading / fences.
    cleaned = stripped.lstrip("#*_>` ").rstrip("*_`")
    if not cleaned:
        return None
    # `===PLATFORM: FACEBOOK===` (original spec)
    if cleaned.upper().startswith("===PLATFORM:") and cleaned.endswith("==="):
        name = cleaned[len("===PLATFORM:"):].rstrip("=").strip().lower()
        return name or None
    # `PLATFORM: facebook`
    if cleaned.upper().startswith("PLATFORM:"):
        name = cleaned.split(":", 1)[1].strip().lower()
        return name or None
    return None
