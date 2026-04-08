"""
Skill: compose_outreach
Write cold outreach emails that feel personal, not AI-generated.

Generates A/B/C variants per campaign. Each variant uses a different
tone and angle but always:
  - References something specific about the lead's situation
  - Leads with value/insight, not a sales pitch
  - Has one clear, low-friction CTA
  - Is short (under 150 words body)

Input:
    lead        (dict): Lead record with notes, website_url, company, name
    venture     (str):  marketing_audit | content_studio | accessibility_audit
    variant     (str):  "A" | "B" | "C"
    campaign_goal (str): e.g. "get them to try the free audit"
    extra_context (str): any custom context to inject (optional)

Output:
    {subject, body_html, body_text, tone_notes, cost_usd}
"""

from __future__ import annotations

import logging
import os

import anthropic

log = logging.getLogger(__name__)

# ── Venture context blocks ─────────────────────────────────────────────────────

_VENTURE_CONTEXT = {
    "marketing_audit": {
        "service": "website marketing audit",
        "offer": "free instant website score (no sign-up needed)",
        "cta_url": "https://echoforge.biz/#marketing-audit",
        "value_prop": "We score websites on SEO, messaging clarity, conversion rate, and competitive positioning — and you get a free score before deciding if you want the full report.",
        "sender_name": os.environ.get("OUTREACH_SENDER_NAME", "Gal"),
        "sender_role": "founder, EchoForge",
    },
    "content_studio": {
        "service": "podcast show notes service",
        "offer": "free sample show notes from a 10-minute clip",
        "cta_url": "https://echoforge.biz/#podcast",
        "value_prop": "We turn podcast audio into professional show notes, timestamps, transcripts, and social posts — automatically. First 10 minutes free, no card needed.",
        "sender_name": os.environ.get("OUTREACH_SENDER_NAME", "Gal"),
        "sender_role": "founder, EchoForge",
    },
    "accessibility_audit": {
        "service": "WCAG accessibility audit",
        "offer": "free automated accessibility scan report",
        "cta_url": "https://echoforge.biz/#accessibility",
        "value_prop": "We run an automated WCAG 2.1/2.2 scan on your site and give you a prioritised list of violations with code examples showing exactly how to fix each one.",
        "sender_name": os.environ.get("OUTREACH_SENDER_NAME", "Gal"),
        "sender_role": "founder, EchoForge",
    },
}

# ── Variant tone guides ────────────────────────────────────────────────────────

_VARIANT_TONES = {
    "A": {
        "tone": "direct and specific",
        "angle": "Lead with one specific observation about their situation from your research. Be concrete. Sound like you actually looked at their thing.",
        "cta_style": "soft ask — 'worth a look?'",
    },
    "B": {
        "tone": "peer-to-peer, casual",
        "angle": "Sound like a fellow builder / podcaster / developer sharing something useful they found, not a vendor pitching. Use 'I' a lot. Keep it conversational.",
        "cta_style": "curiosity hook — 'curious what your score would be'",
    },
    "C": {
        "tone": "value-first, no pitch",
        "angle": "Lead with a genuinely useful insight or observation about their niche/space first. Mention what you do only in passing. Let the CTA be secondary.",
        "cta_style": "low pressure — 'no obligation, just sharing'",
    },
}

# ── Main function ──────────────────────────────────────────────────────────────

def compose_outreach(
    lead: dict,
    venture: str,
    variant: str = "A",
    campaign_goal: str = "",
    extra_context: str = "",
) -> dict:
    """
    Write a cold outreach email for a lead.

    Args:
        lead:           Lead dict (name, notes, website_url, company, source_channel)
        venture:        marketing_audit | content_studio | accessibility_audit
        variant:        A, B, or C — controls tone/angle
        campaign_goal:  What we want them to do (defaults to venture free offer)
        extra_context:  Any extra info to inject (e.g. personalised finding)

    Returns:
        {subject, body_html, body_text, tone_notes, cost_usd}
    """
    if venture not in _VENTURE_CONTEXT:
        raise ValueError(f"Unknown venture: {venture}")
    if variant not in _VARIANT_TONES:
        raise ValueError(f"Variant must be A, B, or C. Got: {variant}")

    vc = _VENTURE_CONTEXT[venture]
    tone = _VARIANT_TONES[variant]
    goal = campaign_goal or f"Get them to try the {vc['offer']}"

    lead_name = lead.get("name", "").split()[0] if lead.get("name") else ""
    lead_notes = lead.get("notes", "No specific context available.")
    lead_website = lead.get("website_url", "")
    lead_company = lead.get("company", "")
    lead_channel = lead.get("source_channel", "")

    prompt = f"""You are writing a cold outreach email for {vc['sender_name']} ({vc['sender_role']}).

SERVICE: {vc['service']}
VALUE PROP: {vc['value_prop']}
FREE OFFER: {vc['offer']}
CTA URL: {vc['cta_url']}

LEAD CONTEXT:
- Name/handle: {lead_name or 'not known'}
- Company/site: {lead_company or lead_website or 'not known'}
- Where found: {lead_channel}
- What we know about them: {lead_notes}
{f'- Extra context: {extra_context}' if extra_context else ''}

CAMPAIGN GOAL: {goal}

TONE: {tone['tone']}
ANGLE: {tone['angle']}
CTA STYLE: {tone['cta_style']}

RULES (follow all of these):
1. Subject line: max 8 words, no emoji, no ALL CAPS, never start with "I"
2. Body: under 140 words. Short paragraphs (1-2 sentences max).
3. Never use: "I hope this email finds you well", "I wanted to reach out", "synergy", "leverage", "game-changer", "cutting-edge", "revolutionize", "excited to share"
4. Sound like a real person wrote this — informal punctuation is fine, contractions are encouraged
5. If you mention something specific about them, be accurate based on the notes above — don't invent details
6. One CTA only. Make it low-friction.
7. Sign off with: {vc['sender_name']} (no title, no company — keep it human)

Write the email now. Output JSON only:
{{
  "subject": "...",
  "body_text": "plain text version",
  "tone_notes": "one sentence explaining the angle you chose"
}}"""

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

        input_tokens  = msg.usage.input_tokens
        output_tokens = msg.usage.output_tokens
        cost_usd = (input_tokens * 3 + output_tokens * 15) / 1_000_000

        subject   = data.get("subject", "")
        body_text = data.get("body_text", "")
        tone_notes = data.get("tone_notes", "")

        body_html = _text_to_html(body_text)

        return {
            "subject":    subject,
            "body_html":  body_html,
            "body_text":  body_text,
            "tone_notes": tone_notes,
            "variant":    variant,
            "cost_usd":   round(cost_usd, 6),
        }

    except Exception as e:
        log.error("compose_outreach failed: %s", e)
        raise


def compose_all_variants(
    lead: dict,
    venture: str,
    campaign_goal: str = "",
    extra_context: str = "",
) -> list[dict]:
    """
    Compose A, B, and C variants for a lead. Returns list of 3 email dicts.
    Each dict includes the 'variant' key.
    """
    results = []
    total_cost = 0.0
    for variant in ("A", "B", "C"):
        email = compose_outreach(lead, venture, variant, campaign_goal, extra_context)
        total_cost += email.get("cost_usd", 0)
        results.append(email)

    log.info("compose_all_variants: 3 variants composed, total cost $%.4f", total_cost)
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _text_to_html(text: str) -> str:
    """Convert plain text email body to minimal HTML."""
    lines = text.strip().split("\n")
    html_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_lines.append("<br>")
        else:
            import html
            html_lines.append(f"<p style='margin:0 0 8px 0;'>{html.escape(stripped)}</p>")
    return "\n".join(html_lines)
