"""
Skill: generate_email_sequence
Generate a podcast listener nurture email sequence.

Produces a 5-email welcome series designed to turn new subscribers into loyal listeners.
Sequence structure (from ai-marketing-claude methodology):
  1. Welcome + best episode to start with
  2. What the show is really about (positioning)
  3. Most-shared / most-valuable episode highlight
  4. Community / social proof
  5. Re-engagement / what's coming next

Input:
    transcripts           list[str]  — 1-5 episode transcript texts (capped at 2500 chars each)
    episode_context       dict       — {show_name, niche, audience, host_name}
    brand_voice_injection str        — optional; ensures on-brand voice
    sequence_length       int        — default 5; max 7
    max_tokens            int        — default 6144

Output:
    {
        "emails":    list[dict],   # [{number, subject, preview_text, body_text}]
        "cost_usd":  float,
    }
"""

from __future__ import annotations

import os
import re


SYSTEM_PROMPT = """\
You are an email copywriter specialising in podcast audience growth.
Your sequences follow a "value before ask" framework: 3 parts value for every 1 part CTA.
Write in the host's voice — conversational, direct, and personal.
Each email must feel like a message from a friend, not a newsletter.
Subject lines must be curiosity-driven or specific — never generic ("Welcome!", "Episode 1").
"""

_EMAIL_TEMPLATES = [
    "Welcome — introduce yourself, tell the listener the ONE episode they must start with, "
    "set expectations for what's coming. Warm, personal, no hard sell.",
    "Positioning — explain what the show is REALLY about (the deeper mission, not just the topic). "
    "Address a misconception or hidden benefit. End with a discussion question.",
    "Highlight — share the single most impactful insight or moment from your library. "
    "Quote a specific line or story from an episode. Drive a replay listen.",
    "Social proof + community — share a listener result, quote, or transformation. "
    "Invite them to reply, join a community, or share the show.",
    "Re-engagement / what's next — tease upcoming content, share what's behind the scenes, "
    "or ask what topic they want next. Give them a reason to stay subscribed.",
]

_EMAIL_PATTERN = re.compile(
    r"\[EMAIL\s+(\d+)\](.*?)\[/EMAIL\]",
    re.DOTALL | re.IGNORECASE,
)
_FIELD_PATTERN = re.compile(
    r"^(Subject|Preview-Text|Body):\s*(.+?)(?=\n(?:Subject|Preview-Text|Body):|$)",
    re.MULTILINE | re.DOTALL,
)


def generate_email_sequence(
    transcripts: list[str],
    episode_context: dict,
    brand_voice_injection: str = "",
    sequence_length: int = 5,
    max_tokens: int = 6144,
) -> dict:
    """
    Generate a podcast listener nurture email sequence.
    Requires ANTHROPIC_API_KEY.
    """
    import anthropic

    sequence_length = min(max(sequence_length, 1), 7)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_message = _build_prompt(transcripts, episode_context, brand_voice_injection, sequence_length)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    emails = _parse_emails(raw)

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )

    return {"emails": emails, "cost_usd": cost_usd}


# ─── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    transcripts: list[str],
    ctx: dict,
    brand_voice_injection: str,
    sequence_length: int,
) -> str:
    show = ctx.get("show_name", "this podcast")
    niche = ctx.get("niche", "general")
    audience = ctx.get("audience", "general audience")
    host = ctx.get("host_name", "")

    templates = _EMAIL_TEMPLATES[:sequence_length]
    email_specs = "\n".join(
        f"  Email {i+1}: {spec}" for i, spec in enumerate(templates)
    )

    transcript_block = "\n\n".join(
        f"--- EPISODE {i+1} EXCERPT ---\n{t.strip()[:2500]}"
        for i, t in enumerate(transcripts[:5])
    )

    bv = f"\nBRAND VOICE:\n{brand_voice_injection.strip()}\n" if brand_voice_injection.strip() else ""
    host_line = f"Host: {host}\n" if host else ""

    return f"""\
Write a {sequence_length}-email welcome/nurture sequence for new subscribers of the podcast below.

SHOW DETAILS:
Show: {show}
Niche: {niche}
Audience: {audience}
{host_line}{bv}
EMAIL SEQUENCE SPECS:
{email_specs}

WRITING RULES:
- Subject lines: specific, curiosity-driven, no clickbait. Max 60 characters.
- Preview text: 90-110 characters. Expand the subject, don't repeat it.
- Body: 150-250 words. Short paragraphs. Conversational. One clear CTA per email.
- Draw on real content from the transcripts — specific quotes, episode titles, insights.
- Emails are spaced: Day 0, Day 2, Day 5, Day 9, Day 14.

EPISODE CONTENT:
{transcript_block}

OUTPUT FORMAT — output exactly {sequence_length} entries, each in this format with no extra text:

[EMAIL 1]
Subject: [subject line]
Preview-Text: [preview text]
Body:
[full email body — use blank lines between paragraphs]
[/EMAIL]

[EMAIL 2]
...
[/EMAIL]
"""


# ─── Parser ───────────────────────────────────────────────────────────────────

def _parse_emails(raw: str) -> list[dict]:
    emails = []
    for match in _EMAIL_PATTERN.finditer(raw):
        num = int(match.group(1))
        block = match.group(2).strip()
        fields: dict[str, str] = {}
        for m in _FIELD_PATTERN.finditer(block):
            fields[m.group(1).lower().replace("-", "_")] = m.group(2).strip()
        emails.append({
            "number":       num,
            "subject":      fields.get("subject", ""),
            "preview_text": fields.get("preview_text", ""),
            "body_text":    fields.get("body", ""),
        })
    emails.sort(key=lambda e: e["number"])
    return emails
