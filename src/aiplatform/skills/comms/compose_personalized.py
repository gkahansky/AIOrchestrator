"""
Skill: compose_personalized
Write a personalized outreach message for a single lead.

Unlike A/B template composition, this writes a unique message grounded in
the lead's specific post/query context. The message reads as a natural reply
to what they wrote, not a generic cold pitch.

Entry point:
    compose_for_lead(lead, campaign) -> dict
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

# Platform-specific tone and format rules injected into the prompt
_PLATFORM_RULES: dict[str, str] = {
    "email": (
        "Format: professional email with a subject line. "
        "Tone: friendly but business-appropriate. "
        "Length: 150-200 words. "
        "Include a clear, low-friction call to action (e.g. 'want a free quick look?')."
    ),
    "reddit": (
        "Format: Reddit comment reply — NO subject line. "
        "Tone: conversational, community-first, not salesy. "
        "Start by directly addressing the question or pain they described. "
        "Mention the service naturally, not as a pitch. "
        "Length: 80-150 words. Max 10k chars."
    ),
    "linkedin": (
        "Format: LinkedIn connection message or post comment — NO subject line. "
        "Tone: professional, warm, peer-to-peer. "
        "Connection request: max 300 chars. "
        "Comment: max 1250 chars, add genuine value before mentioning the service."
    ),
    "facebook": (
        "Format: Facebook group comment reply — NO subject line. "
        "Tone: friendly, community-oriented. "
        "Start by being helpful, then offer the service briefly. "
        "Length: 80-150 words."
    ),
    "instagram": (
        "Format: Instagram comment or DM — NO subject line. "
        "Tone: casual, visual-friendly, brief. "
        "Length: 50-100 words. Max 2200 chars."
    ),
    "fiverr": (
        "Format: Fiverr buyer request response — NO subject line. "
        "Tone: professional and direct. "
        "Directly address their stated requirements. "
        "Length: 100-150 words. Max 2k chars."
    ),
}

# Maps a lead's discovery channel (source_channel) to the outreach platform we
# would naturally reply on. Channels that aren't messaging surfaces (search /
# directory listings) map to email, since the lead is reached by email.
SOURCE_TO_OUTREACH: dict[str, str] = {
    "reddit": "reddit",
    "linkedin": "linkedin",
    "facebook": "facebook",
    "instagram": "instagram",
    "fiverr": "fiverr",
    "google": "email",
    "hackernews": "email",
    "indiehackers": "email",
    "listennotes": "email",
    "youtube": "email",
}

# Platforms with a delivery path. Email delivers via Resend; linkedin/instagram/
# facebook deliver via assisted send (deep link + operator confirm) through the
# send-handler registry (aiplatform.skills.comms.senders). Adding a platform here
# switches both message style and delivery to it automatically.
DELIVERABLE_PLATFORMS: set[str] = {"email", "linkedin", "instagram", "facebook"}


def outreach_platform_for_source(source_platform: str | None) -> str:
    """Map a source/discovery platform to the outreach platform to reply on."""
    return SOURCE_TO_OUTREACH.get((source_platform or "").lower(), "email")


def resolve_effective_platform(
    source_channel: str | None, campaign_platform: str = "email"
) -> str:
    """
    Resolve the platform used for BOTH message style and delivery for one lead.

    Prefers the platform the lead was found on; falls back to the campaign
    default for unmapped channels; then collapses to email when the preferred
    platform has no delivery path yet (see DELIVERABLE_PLATFORMS).
    """
    desired = SOURCE_TO_OUTREACH.get(
        (source_channel or "").lower(), campaign_platform or "email"
    )
    return desired if desired in DELIVERABLE_PLATFORMS else "email"


def compose_for_lead(lead: dict, campaign: dict, platform: str | None = None,
                     revision_feedback: str | None = None,
                     previous_message: str | None = None) -> dict:
    """
    Write a personalized outreach message for a single lead.

    Args:
        lead:     Lead dict with fields: name, context, notes, source_channel,
                  website_url, company, matched_persona, platform_username
        campaign: Campaign dict with fields: target_prompt, personas, platform,
                  venture, goal, name
        revision_feedback: When set, rewrite a prior draft to address operator
                  feedback instead of composing from scratch.
        previous_message: The prior draft body the feedback refers to.

    Returns:
        {subject, message_body, context_used}
        subject is None for non-email platforms.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    platform = platform or campaign.get("platform", "email")
    platform_rules = _PLATFORM_RULES.get(platform, _PLATFORM_RULES["email"])

    # Find the matched persona details
    personas = campaign.get("personas") or []
    matched_persona_name = lead.get("matched_persona", "")
    persona_detail = ""
    if matched_persona_name and personas:
        for p in personas:
            if p.get("name") == matched_persona_name:
                persona_detail = (
                    f"\nMATCHED PERSONA: {p['name']}\n{p.get('description', '')}"
                )
                break

    context = lead.get("context") or lead.get("notes") or ""
    lead_name = lead.get("name") or lead.get("platform_username") or "them"
    company_line = f"Company/Project: {lead.get('company')}" if lead.get("company") else ""
    website_line = f"Website: {lead.get('website_url')}" if lead.get("website_url") else ""

    system = (
        "You are an expert outreach writer. You write personalized, context-aware messages "
        "that feel like a natural response to what the recipient said — not a mass-blast template. "
        "Every message must reference something specific from their post or query."
    )

    user_prompt = f"""Write a personalized outreach message for this lead.

SERVICE WE OFFER:
{campaign.get('target_prompt') or campaign.get('goal') or 'Digital service for businesses'}

PLATFORM: {platform.upper()}
{platform_rules}
{persona_detail}

LEAD DETAILS:
Name / Handle: {lead_name}
Channel found on: {lead.get('source_channel', '')}
{company_line}
{website_line}

THEIR POST / QUERY (this is what they wrote — your message must feel like a direct reply to this):
\"\"\"
{context[:1500]}
\"\"\"

AI-extracted notes about their pain point: {lead.get('notes', '')}

INSTRUCTIONS:
1. Open by acknowledging something specific they said (use their words, not generic paraphrasing).
2. Briefly introduce how the service addresses their exact pain point.
3. End with a low-friction CTA.
4. Do NOT use a generic opener like "I came across your post" — be specific.
5. Do NOT over-promise or use hype language.
{"6. Output format: JSON with keys 'subject' (string, email only — write null for other platforms) and 'message_body' (string)." if platform == "email" else "6. Output format: JSON with keys 'subject' (null) and 'message_body' (string)."}

Output JSON only, no explanation outside the JSON."""

    if revision_feedback:
        user_prompt += f"""

REVISION REQUEST — this overrides a fresh compose:
The operator reviewed the draft below and asked for changes. Rewrite the message
to address their feedback while keeping it grounded in the lead's post above.

PREVIOUS DRAFT:
\"\"\"
{(previous_message or '')[:1500]}
\"\"\"

OPERATOR FEEDBACK (apply this):
{revision_feedback[:1000]}"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        import json, re
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        return {
            "subject":      data.get("subject"),
            "message_body": data.get("message_body", ""),
            "context_used": context[:500],
        }
    except Exception as e:
        log.error("compose_for_lead failed for lead %s: %s", lead.get("id", "?"), e)
        raise
