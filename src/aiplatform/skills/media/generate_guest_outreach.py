"""
Skill: generate_guest_outreach
Generate 3 guest outreach email templates for podcast hosts pitching potential guests.

Templates:
  1. Cold outreach  — no prior relationship; lead with show value + fit
  2. Warm outreach  — via mutual connection or prior engagement with the show
  3. Follow-up      — after no reply to cold outreach (7–14 days later)

Each template uses [PERSONALISATION] placeholders with per-placeholder guidance so
hosts can customise quickly without writing from scratch.

Input:
    episode_context   dict    — {show_name, niche, audience, host_name, show_notes (optional)}
    guest_name        str     — optional; used in placeholders if provided
    guest_expertise   str     — optional; what the target guest is known for
    max_tokens        int     — default 4096

Output:
    {
        "templates":   list[dict],   # [{type, subject, body, personalisation_guide}]
        "cost_usd":    float,
    }
"""

from __future__ import annotations

import os
import re


SYSTEM_PROMPT = """\
You are a podcast outreach specialist. You write cold and warm email templates that
get replies — not because they're clever, but because they're specific, genuine, and
make the guest's decision obvious.

Rules:
- Never open with "I hope this email finds you well" or any generic filler.
- Always lead with something specific about the GUEST (their work, a talk, a post).
- Keep the pitch to one short paragraph. Don't over-explain the show.
- Use [PERSONALISATION: description] placeholders so the host can fill in specifics quickly.
- Subject lines must be specific — no "Quick question" or "Collaboration opportunity".
- Follow-up emails acknowledge the first contact was missed, not that the guest ignored it.
"""

_TEMPLATE_PATTERN = re.compile(
    r"\[TEMPLATE:\s*(COLD|WARM|FOLLOWUP)\](.*?)\[/TEMPLATE\]",
    re.DOTALL | re.IGNORECASE,
)
_FIELD_PATTERN = re.compile(
    r"^(Subject|Body|Personalisation Guide):\s*(.+?)(?=\n(?:Subject|Body|Personalisation Guide):|$)",
    re.MULTILINE | re.DOTALL,
)


def generate_guest_outreach(
    episode_context: dict,
    guest_name: str = "",
    guest_expertise: str = "",
    max_tokens: int = 4096,
) -> dict:
    """
    Generate 3 guest outreach email templates.
    Requires ANTHROPIC_API_KEY.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_message = _build_prompt(episode_context, guest_name, guest_expertise)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    templates = _parse_templates(raw)

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )

    return {"templates": templates, "cost_usd": cost_usd}


# ─── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(ctx: dict, guest_name: str, guest_expertise: str) -> str:
    show = ctx.get("show_name", "the podcast")
    niche = ctx.get("niche", "general")
    audience = ctx.get("audience", "general audience")
    host = ctx.get("host_name", "the host")
    show_notes_excerpt = ctx.get("show_notes", "")[:1000]

    guest_line = f"Target guest: {guest_name}\n" if guest_name else ""
    expertise_line = f"Guest expertise: {guest_expertise}\n" if guest_expertise else ""
    excerpt_line = (
        f"\nRecent episode excerpt (for context and show voice):\n{show_notes_excerpt}\n"
        if show_notes_excerpt else ""
    )

    return f"""\
Write 3 guest outreach email templates for the podcast described below.

SHOW DETAILS:
Show: {show}
Niche: {niche}
Audience: {audience}
Host: {host}
{guest_line}{expertise_line}{excerpt_line}
TEMPLATE REQUIREMENTS:

Template 1 — Cold Outreach
- Host has no prior relationship with the guest
- Lead with something specific about the guest's work (use [PERSONALISATION] placeholder)
- One short paragraph about why this guest fits this audience specifically
- Clear, low-friction ask — a single recording session, 45-60 mins
- Subject: specific to the guest, not the show

Template 2 — Warm Outreach (Mutual Connection)
- Host knows the guest through someone in common, or guest has engaged with the show
- Reference the shared connection or the guest's prior engagement
- Slightly warmer, shorter — the connection does the work
- Use [PERSONALISATION: mutual connection name] placeholder

Template 3 — Follow-Up (No Reply to Cold)
- Sent 10-14 days after Template 1 with no reply
- Acknowledge the previous email briefly, don't apologize
- New angle or hook — a different reason why the guest would find it valuable
- Very short (4-6 sentences max)

[PERSONALISATION] placeholder format: write [PERSONALISATION: what to fill in here]
e.g. [PERSONALISATION: title/topic of a recent talk or article by the guest]

Personalisation Guide: after each template, list every placeholder and what the host
should research or write to fill it in.

OUTPUT FORMAT — exactly 3 templates, each in this structure:

[TEMPLATE: COLD]
Subject: [subject line]
Body:
[full email body]

Personalisation Guide:
- [PERSONALISATION: placeholder description] → [what to research/write]
[/TEMPLATE]

[TEMPLATE: WARM]
...
[/TEMPLATE]

[TEMPLATE: FOLLOWUP]
...
[/TEMPLATE]
"""


# ─── Parser ───────────────────────────────────────────────────────────────────

def _parse_templates(raw: str) -> list[dict]:
    type_map = {"cold": "Cold Outreach", "warm": "Warm Outreach", "followup": "Follow-Up"}
    templates = []
    for match in _TEMPLATE_PATTERN.finditer(raw):
        template_type = match.group(1).lower()
        block = match.group(2).strip()
        fields: dict[str, str] = {}
        for m in _FIELD_PATTERN.finditer(block):
            key = m.group(1).lower().replace(" ", "_")
            fields[key] = m.group(2).strip()
        templates.append({
            "type":                 type_map.get(template_type, template_type.title()),
            "subject":              fields.get("subject", ""),
            "body":                 fields.get("body", ""),
            "personalisation_guide": fields.get("personalisation_guide", ""),
        })
    return templates
