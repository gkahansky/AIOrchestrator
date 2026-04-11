"""
Skill: compose_outreach
Write outreach messages that feel personal, not AI-generated.

Generates A/B/C variants per campaign. Behaviour is controlled by `platform`:

  email     — subject + HTML + plain-text cold email (original behaviour)
  reddit    — comment reply to a post; adds value first, CTA is secondary
  fiverr    — short conversational message to a buyer request or gig inquiry
  linkedin  — concise connection message or post comment
  facebook  — group comment or short message
  instagram — comment under a relevant post

Each platform has its own tone rules, character limits, and CTA style.
New platforms can be added by extending PLATFORM_RULES.

Input:
    lead          (dict): Lead record
    venture       (str):  marketing_audit | content_studio | accessibility_audit
    variant       (str):  "A" | "B" | "C"
    campaign_goal (str):  e.g. "get them to try the free audit"
    extra_context (str):  any custom context to inject (optional)
    platform      (str):  email | reddit | fiverr | linkedin | facebook | instagram

Output (email):    {subject, body_html, body_text, tone_notes, variant, cost_usd}
Output (non-email): {subject: None, body_html: None, body_text, tone_notes, variant, cost_usd}
"""

from __future__ import annotations

import logging
import os

import anthropic

log = logging.getLogger(__name__)

# ── Venture context ────────────────────────────────────────────────────────────

_VENTURE_CONTEXT = {
    "marketing_audit": {
        "service": "website marketing audit",
        "offer": "free instant website score (no sign-up needed)",
        "cta_url": "https://echoforge.biz/#marketing-audit",
        "value_prop": "We score websites on SEO, messaging clarity, conversion, and competitive positioning — free score before deciding on the full report.",
        "sender_name": os.environ.get("OUTREACH_SENDER_NAME", "Gal"),
        "sender_role": "founder, EchoForge",
    },
    "content_studio": {
        "service": "podcast show notes service",
        "offer": "free sample show notes from a 10-minute clip",
        "cta_url": "https://echoforge.biz/#podcast",
        "value_prop": "We turn podcast audio into show notes, timestamps, transcripts, and social posts automatically. First 10 minutes free.",
        "sender_name": os.environ.get("OUTREACH_SENDER_NAME", "Gal"),
        "sender_role": "founder, EchoForge",
    },
    "accessibility_audit": {
        "service": "WCAG accessibility audit",
        "offer": "free automated accessibility scan report",
        "cta_url": "https://echoforge.biz/#accessibility",
        "value_prop": "We run a WCAG 2.1/2.2 scan and give you a prioritised list of violations with exact code fixes.",
        "sender_name": os.environ.get("OUTREACH_SENDER_NAME", "Gal"),
        "sender_role": "founder, EchoForge",
    },
}

# ── Variant tones ──────────────────────────────────────────────────────────────

_VARIANT_TONES = {
    "A": {
        "tone": "direct and specific",
        "angle": "Lead with one concrete observation about their situation. Sound like you actually looked at their thing.",
        "cta_style": "soft ask — 'worth a look?'",
    },
    "B": {
        "tone": "peer-to-peer, casual",
        "angle": "Sound like a fellow builder sharing something useful, not a vendor pitching. Use 'I' a lot.",
        "cta_style": "curiosity hook — 'curious what your score would be'",
    },
    "C": {
        "tone": "value-first, no pitch",
        "angle": "Lead with a genuinely useful insight about their niche. Mention the service only in passing.",
        "cta_style": "low pressure — 'no obligation, just sharing'",
    },
}

# ── Platform rules ─────────────────────────────────────────────────────────────
# Each entry defines the message format, hard constraints, and CTA guidance.
# Add new platforms here without touching any other code.

PLATFORM_RULES: dict[str, dict] = {
    "email": {
        "label": "Cold email",
        "has_subject": True,
        "has_html": True,
        "char_limit": None,
        "format_note": (
            "Write a cold outreach email: subject line + body. "
            "80–140 words. Short paragraphs. Include one CTA link. "
            "End with sender name. Include {{UNSUBSCRIBE_URL}} placeholder on its own line after signature."
        ),
        "banned": [
            "I hope this email finds you well", "I wanted to reach out",
            "just checking in", "synergy", "leverage", "game-changer",
            "cutting-edge", "revolutionize", "excited to share", "touch base",
            "circle back", "at your earliest convenience",
        ],
        "output_fields": '{"subject": "...", "body_text": "...", "tone_notes": "..."}',
    },
    "reddit": {
        "label": "Reddit comment",
        "has_subject": False,
        "has_html": False,
        "char_limit": 1000,
        "format_note": (
            "Write a Reddit comment reply to a post from the lead. "
            "Start by adding genuine value — answer their question or share a relevant insight. "
            "Mention the service only naturally at the end, if it fits. "
            "Never start with 'Hey' or 'Hi'. No bullet-point lists. No em-dashes. "
            "Under 150 words. Conversational, human, Reddit-native tone. "
            "Avoid anything that reads like an ad or cold pitch."
        ),
        "banned": ["check out our", "we offer", "our service", "sign up", "click here"],
        "output_fields": '{"body_text": "...", "tone_notes": "..."}',
    },
    "fiverr": {
        "label": "Fiverr message",
        "has_subject": False,
        "has_html": False,
        "char_limit": 500,
        "format_note": (
            "Write a short Fiverr message to a buyer who posted a request for a related service. "
            "Be direct and professional — Fiverr buyers want to know: can you do it, how fast, for how much. "
            "Reference exactly what they asked for. Keep it under 100 words. "
            "End with a clear next step (offer to send a sample or ask a clarifying question). "
            "No subject line. Plain text only."
        ),
        "banned": ["I hope this message finds you", "synergy", "game-changer"],
        "output_fields": '{"body_text": "...", "tone_notes": "..."}',
    },
    "linkedin": {
        "label": "LinkedIn message",
        "has_subject": False,
        "has_html": False,
        "char_limit": 300,
        "format_note": (
            "Write a LinkedIn connection request message or post comment. "
            "Connection messages: under 300 characters. Professional but warm. "
            "Reference something specific about their profile or recent post. "
            "One sentence about why you're reaching out. No pitch in the request itself — "
            "save that for after they connect. "
            "Comment style: add a substantive observation or question first, mention the service briefly."
        ),
        "banned": ["I came across your profile", "synergy", "leverage", "excited to connect"],
        "output_fields": '{"body_text": "...", "tone_notes": "..."}',
    },
    "facebook": {
        "label": "Facebook comment/message",
        "has_subject": False,
        "has_html": False,
        "char_limit": 500,
        "format_note": (
            "Write a Facebook group comment or short DM. "
            "Group comments: add value to the thread first — answer the question or share insight. "
            "Mention the service only if directly relevant and only briefly. "
            "Under 120 words. Friendly, casual, community-native. No hard sell."
        ),
        "banned": ["check out my", "DM me", "click the link in bio", "game-changer"],
        "output_fields": '{"body_text": "...", "tone_notes": "..."}',
    },
    "instagram": {
        "label": "Instagram comment",
        "has_subject": False,
        "has_html": False,
        "char_limit": 300,
        "format_note": (
            "Write an Instagram comment under a relevant post. "
            "Under 80 words. Acknowledge the post genuinely first. "
            "If mentioning the service, do it in 1 sentence max — never make it the opener. "
            "No hashtags in the comment. No links (Instagram doesn't allow clickable links in comments). "
            "Conversational and authentic — comments that read like ads get ignored."
        ),
        "banned": ["link in bio", "DM for details", "check out", "game-changer", "hashtag"],
        "output_fields": '{"body_text": "...", "tone_notes": "..."}',
    },
}

# ── Main function ──────────────────────────────────────────────────────────────

def compose_outreach(
    lead: dict,
    venture: str,
    variant: str = "A",
    campaign_goal: str = "",
    extra_context: str = "",
    platform: str = "email",
) -> dict:
    """
    Write an outreach message for a lead on the specified platform.

    Returns a dict with keys: subject, body_html, body_text, tone_notes, variant, cost_usd.
    subject and body_html are None for non-email platforms.
    """
    if venture not in _VENTURE_CONTEXT:
        raise ValueError(f"Unknown venture: {venture}")
    if variant not in _VARIANT_TONES:
        raise ValueError(f"Variant must be A, B, or C. Got: {variant}")
    if platform not in PLATFORM_RULES:
        raise ValueError(f"Unknown platform: {platform}. Known: {list(PLATFORM_RULES)}")

    vc   = _VENTURE_CONTEXT[venture]
    tone = _VARIANT_TONES[variant]
    pr   = PLATFORM_RULES[platform]
    goal = campaign_goal or f"Get them to try the {vc['offer']}"

    lead_name     = lead.get("name", "").split()[0] if lead.get("name") else ""
    lead_notes    = lead.get("notes", "No specific context available.")
    lead_website  = lead.get("website_url", "")
    lead_company  = lead.get("company", "")
    lead_channel  = lead.get("source_channel", "")
    lead_username = lead.get("platform_username", "")
    source_url    = lead.get("source_url", "")

    banned_str = "\n".join(f'   - "{b}"' for b in pr["banned"])

    prompt = f"""You are writing a {pr['label']} for {vc['sender_name']} ({vc['sender_role']}).

SERVICE: {vc['service']}
VALUE PROP: {vc['value_prop']}
FREE OFFER: {vc['offer']}
CTA URL: {vc['cta_url']}

LEAD CONTEXT:
- Name/handle: {lead_name or lead_username or 'not known'}
- Company/site: {lead_company or lead_website or 'not known'}
- Where found: {lead_channel}{f' — {source_url}' if source_url else ''}
- What we know about them: {lead_notes}
{f'- Extra context: {extra_context}' if extra_context else ''}

CAMPAIGN GOAL: {goal}

TONE: {tone['tone']}
ANGLE: {tone['angle']}
CTA STYLE: {tone['cta_style']}

PLATFORM INSTRUCTIONS:
{pr['format_note']}
{f'Character limit: {pr["char_limit"]} characters.' if pr['char_limit'] else ''}

BANNED PHRASES (never use any of these):
{banned_str}

GENERAL RULES:
- Do not invent details about the lead that aren't in the notes above.
- Every sentence starts with a capital letter. Proper nouns capitalised correctly.
- Write like an educated native English speaker — no comma splices, no fragments unless deliberate.
- Sound human. Not like a template. Not like a bot.

Write the message now. Output JSON only:
{pr['output_fields']}"""

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        import json, re
        text = msg.content[0].text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)

        cost_usd = (msg.usage.input_tokens * 3 + msg.usage.output_tokens * 15) / 1_000_000

        subject    = data.get("subject") if pr["has_subject"] else None
        body_text  = data.get("body_text", "")
        body_html  = _text_to_html(body_text) if pr["has_html"] and body_text else None
        tone_notes = data.get("tone_notes", "")

        return {
            "subject":    subject,
            "body_html":  body_html,
            "body_text":  body_text,
            "tone_notes": tone_notes,
            "variant":    variant,
            "platform":   platform,
            "cost_usd":   round(cost_usd, 6),
        }

    except Exception as e:
        log.error("compose_outreach failed (platform=%s venture=%s): %s", platform, venture, e)
        raise


def compose_all_variants(
    lead: dict,
    venture: str,
    campaign_goal: str = "",
    extra_context: str = "",
    platform: str = "email",
) -> list[dict]:
    """Compose A, B, and C variants. Returns list of 3 message dicts."""
    results = []
    total_cost = 0.0
    for variant in ("A", "B", "C"):
        msg = compose_outreach(lead, venture, variant, campaign_goal, extra_context, platform)
        total_cost += msg.get("cost_usd", 0)
        results.append(msg)
    log.info("compose_all_variants: 3 variants composed (platform=%s), total cost $%.4f", platform, total_cost)
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _text_to_html(text: str) -> str:
    """Convert plain text email body to minimal HTML."""
    import html as _html
    lines = text.strip().split("\n")
    html_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p style='margin:0 0 8px 0;'>{_html.escape(stripped)}</p>")
    return "\n".join(html_lines)
