"""
Skill: generate_social_calendar
Generate a 30-day social media content calendar from podcast episode transcripts.

Implements the content pillar framework: 40% Educational, 20% Behind-the-scenes,
20% Social proof, 10% Engagement, 10% Promotional.  Hook formulas are platform-specific.

Input:
    transcripts           list[str]  — 1-4 episode transcript texts (capped at 3000 chars each)
    episode_context       dict       — {show_name, niche, audience, host_name}
    brand_voice_injection str        — optional; prepended to ensure on-brand output
    platforms             list[str]  — subset of: linkedin instagram twitter tiktok youtube
    max_tokens            int        — default 8192

Output:
    {
        "calendar":  list[dict],   # [{day, platform, pillar, hook, post, hashtags}]
        "cost_usd":  float,
    }
"""

from __future__ import annotations

import os
import re


SYSTEM_PROMPT = """\
You are a social media content strategist specialising in podcast growth.
Your job is to turn podcast episode content into a ready-to-post 30-day social calendar.
Every post must feel native to its platform — not copy-pasted across channels.
Use the host's actual language and stories from the transcripts wherever possible.
Never use generic filler like "great episode" or "amazing conversation".
"""

_PLATFORM_GUIDES = {
    "linkedin": (
        "Professional, thought-leadership tone. "
        "Open with a bold claim, counter-intuitive insight, or 'I did X and here's what happened' hook. "
        "Use short paragraphs, white space, occasional numbered lists. "
        "End with a question or call-to-comment. 3-5 relevant hashtags."
    ),
    "instagram": (
        "Hook in the first 125 characters (shown before 'more'). "
        "Story-driven or carousel-teaser format. Emoji used sparingly for visual breaks. "
        "3-5 hashtags — mix niche, medium, and broad. CTA to listen/save/share."
    ),
    "twitter": (
        "Punchy single-sentence hook. Max 260 chars per tweet. "
        "Can be a thread opener ('Thread: [hook] 🧵'). Conversational tone. "
        "1-2 hashtags maximum. End with a question or retweet prompt."
    ),
    "tiktok": (
        "Start with a hook that stops the scroll in 1 second: a bold statement or 'POV:' opener. "
        "Trend-aware language. Short punchy sentences. 'Comment X if you agree' CTA. "
        "3-5 relevant hashtags including at least one trending tag."
    ),
    "youtube": (
        "Community post style. 'Did you know...' or 'We're curious...' opener. "
        "Subscriber-focused language ('you', 'our community'). "
        "Link to the episode in the first comment note. 1-3 hashtags."
    ),
}

_PILLARS = [
    ("Educational", 12),        # 40%
    ("Behind-the-scenes", 6),   # 20%
    ("Social proof", 6),        # 20%
    ("Engagement", 4),          # ~13%
    ("Promotional", 2),         # ~7%
]

_ENTRY_PATTERN = re.compile(
    r"\[DAY\s+(\d+)\](.*?)\[/DAY\]",
    re.DOTALL | re.IGNORECASE,
)
_FIELD_PATTERN = re.compile(
    r"^(Platform|Pillar|Hook|Post|Hashtags):\s*(.+?)(?=\n(?:Platform|Pillar|Hook|Post|Hashtags):|$)",
    re.MULTILINE | re.DOTALL,
)


def generate_social_calendar(
    transcripts: list[str],
    episode_context: dict,
    brand_voice_injection: str = "",
    platforms: list[str] | None = None,
    max_tokens: int = 8192,
) -> dict:
    """
    Generate a 30-day social calendar from podcast transcripts.
    Requires ANTHROPIC_API_KEY.
    """
    import anthropic

    platforms = platforms or ["linkedin", "instagram", "twitter"]
    valid_platforms = list(_PLATFORM_GUIDES.keys())
    platforms = [p.lower() for p in platforms if p.lower() in valid_platforms] or ["linkedin"]

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_message = _build_prompt(transcripts, episode_context, brand_voice_injection, platforms)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        temperature=0.4,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    calendar = _parse_calendar(raw)

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )

    return {"calendar": calendar, "cost_usd": cost_usd}


# ─── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    transcripts: list[str],
    ctx: dict,
    brand_voice_injection: str,
    platforms: list[str],
) -> str:
    show = ctx.get("show_name", "this podcast")
    niche = ctx.get("niche", "general")
    audience = ctx.get("audience", "general audience")
    host = ctx.get("host_name", "")

    platform_block = "\n".join(
        f"  {p.title()}: {_PLATFORM_GUIDES[p]}" for p in platforms
    )

    pillar_block = "\n".join(
        f"  {name}: {count} posts" for name, count in _PILLARS
    )

    # Rotate platforms across 30 days
    platform_schedule = [platforms[i % len(platforms)] for i in range(30)]
    day_platform_lines = "\n".join(
        f"  Day {i+1}: {platform_schedule[i].title()}"
        for i in range(30)
    )

    transcript_block = "\n\n".join(
        f"--- EPISODE {i+1} EXCERPT ---\n{t.strip()[:3000]}"
        for i, t in enumerate(transcripts[:4])
    )

    bv = f"\nBRAND VOICE:\n{brand_voice_injection.strip()}\n" if brand_voice_injection.strip() else ""

    host_line = f"Host: {host}\n" if host else ""

    return f"""\
Create a 30-day social media content calendar for the podcast below.

SHOW DETAILS:
Show: {show}
Niche: {niche}
Audience: {audience}
{host_line}Platforms: {', '.join(p.title() for p in platforms)}
{bv}
PLATFORM GUIDELINES:
{platform_block}

CONTENT PILLAR TARGET (distribute across 30 days):
{pillar_block}

PLATFORM SCHEDULE (follow this exactly):
{day_platform_lines}

EPISODE CONTENT (draw hooks, quotes, and stories from these transcripts):
{transcript_block}

OUTPUT FORMAT — output exactly 30 entries, each in this format with no extra text:

[DAY 1]
Platform: LinkedIn
Pillar: Educational
Hook: [scroll-stopping opening line — max 150 chars]
Post: [full ready-to-post copy — line breaks where needed — 150-300 words for LinkedIn, shorter for Twitter]
Hashtags: #tag1 #tag2 #tag3
[/DAY]

[DAY 2]
...
[/DAY]

Draw directly from the episode content. Use real quotes, specific insights, and actual story beats — not generic marketing filler.
"""


# ─── Parser ───────────────────────────────────────────────────────────────────

def _parse_calendar(raw: str) -> list[dict]:
    entries = []
    for match in _ENTRY_PATTERN.finditer(raw):
        day_num = int(match.group(1))
        block = match.group(2).strip()
        fields = {}
        for m in _FIELD_PATTERN.finditer(block):
            fields[m.group(1).lower()] = m.group(2).strip()
        entries.append({
            "day":       day_num,
            "platform":  fields.get("platform", ""),
            "pillar":    fields.get("pillar", ""),
            "hook":      fields.get("hook", ""),
            "post":      fields.get("post", ""),
            "hashtags":  fields.get("hashtags", ""),
        })
    # Sort by day number in case Claude output them out of order
    entries.sort(key=lambda e: e["day"])
    return entries
