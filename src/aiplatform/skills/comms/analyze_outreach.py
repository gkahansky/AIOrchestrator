"""
Skill: analyze_outreach
Analyze A/B test results across outreach template variants and generate
recommendations for improving future campaigns.

Input:
    campaign_id (str): UUID of the campaign to analyze
    db_session:        SQLAlchemy session (injected by caller)

Output:
    {
        "variants": [{variant, sends, opens, replies, open_rate, reply_rate}],
        "winner":   variant letter or None,
        "analysis": str,          # human-readable summary
        "recommendations": [str], # actionable next steps
        "cost_usd": float,
    }
"""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic

log = logging.getLogger(__name__)


def analyze_campaign(campaign_id: str, db: Any) -> dict:
    """
    Pull sends/opens/replies from DB for each template variant and
    use Claude to interpret the results and suggest improvements.

    Args:
        campaign_id: UUID string of the OutreachCampaign
        db:          SQLAlchemy session

    Returns:
        Analysis dict with variant stats, winner, analysis text, and recommendations.
    """
    from aiplatform.database.models import OutreachCampaign, OutreachTemplate, OutreachSend
    import uuid

    # ── Pull campaign data ──────────────────────────────────────────────────────
    campaign = db.get(OutreachCampaign, uuid.UUID(campaign_id))
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    templates = db.query(OutreachTemplate).filter(
        OutreachTemplate.campaign_id == uuid.UUID(campaign_id)
    ).all()

    if not templates:
        return {
            "variants": [],
            "winner": None,
            "analysis": "No templates found for this campaign.",
            "recommendations": ["Create email templates and start sending before running analysis."],
            "cost_usd": 0.0,
        }

    # ── Build stats per variant ─────────────────────────────────────────────────
    variant_stats = []
    for t in templates:
        sends   = t.sends_count or 0
        opens   = t.opens_count or 0
        replies = t.replies_count or 0

        open_rate   = round(opens   / sends * 100, 1) if sends > 0 else 0
        reply_rate  = round(replies / sends * 100, 1) if sends > 0 else 0

        variant_stats.append({
            "variant":     t.variant,
            "subject":     t.subject,
            "tone_notes":  t.tone_notes or "",
            "sends":       sends,
            "opens":       opens,
            "replies":     replies,
            "open_rate":   open_rate,
            "reply_rate":  reply_rate,
        })

    # Sort by reply_rate desc (primary metric)
    variant_stats.sort(key=lambda x: (x["reply_rate"], x["open_rate"]), reverse=True)
    winner = variant_stats[0]["variant"] if variant_stats and variant_stats[0]["sends"] >= 5 else None

    # ── Minimum data check ──────────────────────────────────────────────────────
    total_sends = sum(v["sends"] for v in variant_stats)
    if total_sends < 10:
        return {
            "variants": variant_stats,
            "winner": None,
            "analysis": f"Only {total_sends} emails sent so far — need at least 10 per variant for statistically meaningful results.",
            "recommendations": [
                "Keep sending until you have at least 10 sends per variant.",
                "Check that tracking pixels are loading correctly to capture open rates.",
            ],
            "cost_usd": 0.0,
        }

    # ── Claude analysis ─────────────────────────────────────────────────────────
    stats_text = "\n".join([
        f"Variant {v['variant']}: {v['sends']} sent, {v['open_rate']}% open rate, {v['reply_rate']}% reply rate\n"
        f"  Subject: {v['subject']}\n"
        f"  Tone: {v['tone_notes']}"
        for v in variant_stats
    ])

    prompt = f"""You're analyzing A/B test results for a cold outreach email campaign.

Campaign: {campaign.name}
Venture: {campaign.venture}
Goal: {campaign.goal or 'Not specified'}

Results:
{stats_text}

Industry benchmarks for cold outreach:
- Open rate: 20-30% is good, 30%+ is excellent
- Reply rate: 2-5% is good, 5%+ is excellent

Provide a concise analysis and actionable recommendations. Output JSON only:
{{
  "analysis": "2-3 sentence plain-English interpretation of the results, noting what's working and what isn't",
  "recommendations": [
    "specific, actionable recommendation 1",
    "specific, actionable recommendation 2",
    "specific, actionable recommendation 3"
  ]
}}

Focus recommendations on: subject line changes, tone adjustments, timing, follow-up strategy, or audience targeting. Be specific."""

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        import json, re
        text = msg.content[0].text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)

        cost_usd = (msg.usage.input_tokens * 0.8 + msg.usage.output_tokens * 4) / 1_000_000

        return {
            "variants":        variant_stats,
            "winner":          winner,
            "analysis":        data.get("analysis", ""),
            "recommendations": data.get("recommendations", []),
            "cost_usd":        round(cost_usd, 6),
        }

    except Exception as e:
        log.error("analyze_campaign Claude call failed: %s", e)
        return {
            "variants":        variant_stats,
            "winner":          winner,
            "analysis":        "Analysis unavailable — Claude call failed.",
            "recommendations": ["Check API key and retry."],
            "cost_usd":        0.0,
        }


def record_open(send_id: str, db: Any) -> None:
    """Mark a send as opened and update template open counter."""
    from aiplatform.database.models import OutreachSend, OutreachTemplate
    from datetime import datetime, timezone
    import uuid

    send = db.get(OutreachSend, uuid.UUID(send_id))
    if not send or send.opened_at:
        return

    send.opened_at = datetime.now(timezone.utc)
    send.status = "opened"

    template = db.get(OutreachTemplate, send.template_id)
    if template:
        template.opens_count = (template.opens_count or 0) + 1

    db.commit()


def record_reply(send_id: str, db: Any) -> None:
    """Mark a send as replied and update template reply counter."""
    from aiplatform.database.models import OutreachSend, OutreachTemplate
    from datetime import datetime, timezone
    import uuid

    send = db.get(OutreachSend, uuid.UUID(send_id))
    if not send:
        return

    send.replied_at = datetime.now(timezone.utc)
    send.status = "replied"

    template = db.get(OutreachTemplate, send.template_id)
    if template:
        template.replies_count = (template.replies_count or 0) + 1

    # Update the lead status too
    from aiplatform.database.models import Lead
    lead = db.get(Lead, send.lead_id)
    if lead:
        lead.status = "replied"

    db.commit()
