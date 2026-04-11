"""
Outreach router — cold outreach campaign management + unified contact CRM.

Endpoints:
  GET/POST        /api/outreach/campaigns
  GET/PATCH/DELETE /api/outreach/campaigns/{id}
  POST            /api/outreach/campaigns/{id}/generate-prompt  (AI search criteria)
  POST            /api/outreach/campaigns/{id}/find-leads       (triggers Celery)
  POST            /api/outreach/campaigns/{id}/compose          (triggers Claude)
  POST            /api/outreach/campaigns/{id}/send             (triggers Celery)
  GET             /api/outreach/campaigns/{id}/stats            (A/B analysis)
  GET/POST        /api/outreach/campaigns/{id}/templates
  PATCH           /api/outreach/templates/{id}
  GET/POST        /api/outreach/leads
  GET/PATCH       /api/outreach/leads/{id}
  GET/PATCH       /api/outreach/contacts
  PATCH           /api/outreach/contacts/{id}
  GET             /api/outreach/unsubscribe/{send_id}  (no auth — email link)
  GET/POST        /api/outreach/track/open/{send_id}   (no auth — pixel)
  POST            /api/outreach/track/reply/{send_id}  (no auth — webhook)
"""

from __future__ import annotations

import os
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from aiplatform.database.models import (
    Contact, Lead, OutreachCampaign, OutreachTemplate, OutreachSend,
)
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth

router = APIRouter()

VALID_VENTURES = {"marketing_audit", "content_studio", "accessibility_audit"}
VALID_PLATFORMS = {"email", "fiverr", "reddit", "linkedin", "facebook", "instagram"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    venture: str
    name: str
    goal: str | None = None
    platform: str = "email"

class CampaignPatch(BaseModel):
    name: str | None = None
    status: str | None = None
    goal: str | None = None
    platform: str | None = None

class TemplatePatch(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    approved: str | None = None  # pending | approved | rejected
    tone_notes: str | None = None

class LeadCreate(BaseModel):
    venture: str
    source_channel: str
    source_url: str | None = None
    name: str | None = None
    email: str | None = None
    platform_username: str | None = None
    website_url: str | None = None
    company: str | None = None
    notes: str | None = None
    campaign_id: str | None = None

class LeadPatch(BaseModel):
    status: str | None = None
    email: str | None = None
    platform_username: str | None = None
    notes: str | None = None
    campaign_id: str | None = None

class FindLeadsRequest(BaseModel):
    channels: list[str] | None = None
    max_leads: int = 20
    search_prompt: str | None = None   # user-reviewed AI-generated criteria prompt

class ComposeRequest(BaseModel):
    extra_context: str = ""
    regenerate_variants: list[str] | None = None

class SendRequest(BaseModel):
    lead_ids: list[str] | None = None
    template_variant: str | None = None

class ContactPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    company: str | None = None
    website_url: str | None = None
    status: str | None = None
    is_test_user: bool | None = None
    features_of_interest: dict | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _campaign_or_404(campaign_id: str, db: Any) -> OutreachCampaign:
    try:
        uid = _uuid.UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid campaign_id format")
    obj = db.get(OutreachCampaign, uid)
    if not obj:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return obj

def _template_to_dict(t: OutreachTemplate) -> dict:
    sends = t.sends_count or 0
    return {
        "id":           str(t.id),
        "campaign_id":  str(t.campaign_id),
        "variant":      t.variant,
        "subject":      t.subject,
        "body_html":    t.body_html,
        "body_text":    t.body_text,
        "tone_notes":   t.tone_notes,
        "approved":     t.approved,
        "sends":        sends,
        "opens":        t.opens_count or 0,
        "replies":      t.replies_count or 0,
        "open_rate":    round((t.opens_count or 0) / sends * 100, 1) if sends > 0 else 0,
        "reply_rate":   round((t.replies_count or 0) / sends * 100, 1) if sends > 0 else 0,
        "created_at":   t.created_at.isoformat(),
        "updated_at":   t.updated_at.isoformat(),
    }

def _lead_to_dict(l: Lead) -> dict:
    return {
        "id":               str(l.id),
        "venture":          l.venture,
        "source_channel":   l.source_channel,
        "source_url":       l.source_url,
        "name":             l.name,
        "email":            l.email,
        "platform_username": l.platform_username,
        "website_url":      l.website_url,
        "company":          l.company,
        "notes":            l.notes,
        "status":           l.status,
        "campaign_id":      str(l.campaign_id) if l.campaign_id else None,
        "created_at":       l.created_at.isoformat(),
        "updated_at":       l.updated_at.isoformat(),
    }

def _contact_to_dict(c: Contact) -> dict:
    return {
        "id":                   str(c.id),
        "email":                c.email,
        "usernames":            c.usernames or {},
        "name":                 c.name,
        "phone":                c.phone,
        "address":              c.address,
        "company":              c.company,
        "website_url":          c.website_url,
        "status":               c.status,
        "is_test_user":         c.is_test_user,
        "ventures_approached":  c.ventures_approached or [],
        "features_of_interest": c.features_of_interest or {},
        "last_activity_at":     c.last_activity_at.isoformat() if c.last_activity_at else None,
        "purchased_at":         c.purchased_at.isoformat() if c.purchased_at else None,
        "unsubscribed_at":      c.unsubscribed_at.isoformat() if c.unsubscribed_at else None,
        "created_at":           c.created_at.isoformat(),
        "updated_at":           c.updated_at.isoformat(),
    }

def _campaign_to_dict(c: OutreachCampaign, db: Any) -> dict:
    templates = db.query(OutreachTemplate).filter(OutreachTemplate.campaign_id == c.id).all()
    leads_count = db.query(Lead).filter(Lead.campaign_id == c.id).count()
    total_sends = sum(t.sends_count or 0 for t in templates)
    total_opens = sum(t.opens_count or 0 for t in templates)
    total_replies = sum(t.replies_count or 0 for t in templates)
    return {
        "id":              str(c.id),
        "venture":         c.venture,
        "name":            c.name,
        "status":          c.status,
        "goal":            c.goal,
        "platform":        c.platform or "email",
        "leads_count":     leads_count,
        "templates_count": len(templates),
        "total_sends":     total_sends,
        "open_rate":       round(total_opens / total_sends * 100, 1) if total_sends > 0 else 0,
        "reply_rate":      round(total_replies / total_sends * 100, 1) if total_sends > 0 else 0,
        "created_at":      c.created_at.isoformat(),
        "updated_at":      c.updated_at.isoformat(),
    }


# ── Campaign endpoints ────────────────────────────────────────────────────────

@router.get("/campaigns")
def list_campaigns(
    venture: str | None = Query(None),
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    q = db.query(OutreachCampaign)
    if venture:
        q = q.filter(OutreachCampaign.venture == venture)
    items = q.order_by(OutreachCampaign.created_at.desc()).all()
    return {"items": [_campaign_to_dict(c, db) for c in items], "total": len(items)}


@router.post("/campaigns", status_code=status.HTTP_201_CREATED)
def create_campaign(
    req: CampaignCreate,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    if req.venture not in VALID_VENTURES:
        raise HTTPException(status_code=400, detail=f"venture must be one of {VALID_VENTURES}")
    if req.platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"platform must be one of {VALID_PLATFORMS}")
    c = OutreachCampaign(venture=req.venture, name=req.name, goal=req.goal, status="draft", platform=req.platform)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _campaign_to_dict(c, db)


@router.get("/campaigns/{campaign_id}")
def get_campaign(
    campaign_id: str,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    result = _campaign_to_dict(c, db)
    result["templates"] = [_template_to_dict(t) for t in db.query(OutreachTemplate).filter(
        OutreachTemplate.campaign_id == c.id).all()]
    return result


@router.patch("/campaigns/{campaign_id}")
def patch_campaign(
    campaign_id: str,
    req: CampaignPatch,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    if req.name is not None:     c.name = req.name
    if req.status is not None:   c.status = req.status
    if req.goal is not None:     c.goal = req.goal
    if req.platform is not None:
        if req.platform not in VALID_PLATFORMS:
            raise HTTPException(status_code=400, detail=f"platform must be one of {VALID_PLATFORMS}")
        c.platform = req.platform
    db.commit()
    db.refresh(c)
    return _campaign_to_dict(c, db)


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: str,
    _: str = Depends(require_auth),
    db=Depends(get_db),
):
    """Delete a campaign and all related templates, leads, and sends (cascade)."""
    c = _campaign_or_404(campaign_id, db)
    db.delete(c)
    db.commit()


# ── AI search criteria prompt generation ─────────────────────────────────────

@router.post("/campaigns/{campaign_id}/generate-prompt")
def generate_search_prompt(
    campaign_id: str,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    """
    Use Claude to generate a structured lead search criteria prompt for this campaign.
    The user reviews / edits this before triggering find-leads.
    """
    import anthropic as _anthropic

    c = _campaign_or_404(campaign_id, db)

    venture_descriptions = {
        "marketing_audit": (
            "website marketing audit service — we score sites on SEO, messaging, conversion, "
            "and competitive positioning. Target: small business owners, SaaS founders, and "
            "e-commerce operators who are struggling with traffic, conversions, or unclear messaging."
        ),
        "content_studio": (
            "podcast show notes service — we turn audio into show notes, timestamps, transcripts, "
            "and social posts. Target: podcasters (solo or with guests) who are growing their show "
            "and need to save time on content production."
        ),
        "accessibility_audit": (
            "WCAG accessibility audit service — we scan websites for accessibility violations and "
            "provide a prioritised fix list with code examples. Target: web developers, digital agencies, "
            "startups, and SMBs with public-facing websites who may be exposed to compliance risk."
        ),
    }

    venture_desc = venture_descriptions.get(c.venture, c.venture)
    campaign_platform = c.platform or "email"

    platform_search_guidance = {
        "email": (
            "Search strategy: web, LinkedIn, Reddit — capture business email and website URL. "
            "Search queries should target Google and Reddit for pain-signal posts."
        ),
        "fiverr": (
            "Search strategy: Fiverr buyer requests only. "
            "Search queries should be Fiverr 'buyer requests' search terms that surface people actively posting requests "
            "for the service. Capture the buyer's Fiverr username (not email). "
            "Queries should be short Fiverr search terms, not Google queries."
        ),
        "reddit": (
            "Search strategy: Reddit posts and threads only. "
            "Search queries should be Reddit-specific (subreddit names + keyword combos). "
            "Capture the poster's Reddit username (u/username). "
            "Target posts where the person is asking for help with the exact problem this service solves."
        ),
        "linkedin": (
            "Search strategy: LinkedIn profiles and posts. "
            "Search queries should target LinkedIn search and Google site:linkedin.com. "
            "Capture the person's LinkedIn profile URL or username. "
            "Target roles or companies that are a strong fit for the service."
        ),
        "facebook": (
            "Search strategy: Facebook groups and public posts. "
            "Search queries should identify relevant Facebook groups and surface posts asking for help. "
            "Capture the person's Facebook profile name or group post URL."
        ),
        "instagram": (
            "Search strategy: Instagram posts and profiles. "
            "Search queries should identify relevant hashtags and accounts. "
            "Capture the Instagram @username. Target accounts that post content related to the pain points."
        ),
    }

    platform_note = platform_search_guidance.get(campaign_platform, "")

    prompt = f"""You are helping build a lead generation search criteria prompt for a cold outreach campaign.

VENTURE: {c.venture}
SERVICE: {venture_desc}
CAMPAIGN NAME: {c.name}
CAMPAIGN GOAL: {c.goal or "Not specified — use the venture's default goal (get leads to try the free offer)"}
PLATFORM: {campaign_platform.upper()} — {platform_note}

Generate a structured lead search criteria prompt that will be used to:
1. Search for potential customers on {campaign_platform}
2. Guide an AI model in qualifying whether each result is a good lead

The prompt must be structured with these sections:
- TARGET PROFILE: who we're looking for (role, business type, size, stage)
- PAIN SIGNALS: what phrases, questions, or behaviors indicate they need this service
- DISQUALIFIERS: what signals mean this is NOT a good lead
- IDENTIFIER TO CAPTURE: exactly what contact identifier to save (e.g. email, Fiverr username, Reddit u/handle)
- CONTEXT NOTES: any nuances the searcher or qualifier should know
- SEARCH QUERIES: 4-6 specific search queries for {campaign_platform} (each on its own line)

Write the prompt now. Make it specific, practical, and directly usable as instructions to an AI model.
Do NOT include any preamble — output the structured prompt directly, starting with "TARGET PROFILE:".
Keep the total under 450 words."""

    client = _anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "campaign_id": campaign_id,
        "prompt": msg.content[0].text.strip(),
        "cost_usd": round((msg.usage.input_tokens * 0.8 + msg.usage.output_tokens * 4) / 1_000_000, 6),
    }


# ── Template endpoints ────────────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/templates")
def list_templates(
    campaign_id: str,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    _campaign_or_404(campaign_id, db)
    templates = db.query(OutreachTemplate).filter(
        OutreachTemplate.campaign_id == _uuid.UUID(campaign_id)
    ).all()
    return {"items": [_template_to_dict(t) for t in templates]}


@router.patch("/templates/{template_id}")
def patch_template(
    template_id: str,
    req: TemplatePatch,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    try:
        uid = _uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template_id")
    t = db.get(OutreachTemplate, uid)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    if req.subject is not None:    t.subject = req.subject
    if req.body_html is not None:  t.body_html = req.body_html
    if req.body_text is not None:  t.body_text = req.body_text
    if req.approved is not None:   t.approved = req.approved
    if req.tone_notes is not None: t.tone_notes = req.tone_notes
    db.commit()
    db.refresh(t)
    return _template_to_dict(t)


# ── Leads endpoints ───────────────────────────────────────────────────────────

@router.get("/leads")
def list_leads(
    venture: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    campaign_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    q = db.query(Lead)
    if venture:      q = q.filter(Lead.venture == venture)
    if status_filter: q = q.filter(Lead.status == status_filter)
    if campaign_id:  q = q.filter(Lead.campaign_id == _uuid.UUID(campaign_id))
    total = q.count()
    items = q.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_lead_to_dict(l) for l in items], "total": total, "page": page, "page_size": page_size}


@router.post("/leads", status_code=status.HTTP_201_CREATED)
def create_lead(req: LeadCreate, _: str = Depends(require_auth), db=Depends(get_db)) -> dict:
    if not req.email and not req.platform_username:
        raise HTTPException(
            status_code=400,
            detail="Lead must have at least one reachable identifier: email or platform_username.",
        )
    campaign_uuid = _uuid.UUID(req.campaign_id) if req.campaign_id else None
    l = Lead(
        venture=req.venture, source_channel=req.source_channel,
        source_url=req.source_url, name=req.name, email=req.email,
        platform_username=req.platform_username,
        website_url=req.website_url, company=req.company,
        notes=req.notes, campaign_id=campaign_uuid, status="new",
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return _lead_to_dict(l)


@router.patch("/leads/{lead_id}")
def patch_lead(lead_id: str, req: LeadPatch, _: str = Depends(require_auth), db=Depends(get_db)) -> dict:
    l = db.get(Lead, _uuid.UUID(lead_id))
    if not l:
        raise HTTPException(status_code=404, detail="Lead not found")
    if req.status is not None:           l.status = req.status
    if req.email is not None:            l.email = req.email
    if req.platform_username is not None: l.platform_username = req.platform_username
    if req.notes is not None:            l.notes = req.notes
    if req.campaign_id is not None:      l.campaign_id = _uuid.UUID(req.campaign_id)
    db.commit()
    db.refresh(l)
    return _lead_to_dict(l)


# ── Contacts endpoints ────────────────────────────────────────────────────────

@router.get("/contacts")
def list_contacts(
    status_filter: str | None = Query(None, alias="status"),
    venture: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    q = db.query(Contact)
    if status_filter: q = q.filter(Contact.status == status_filter)
    if venture:       q = q.filter(Contact.ventures_approached.contains([venture]))
    if search:
        like = f"%{search}%"
        q = q.filter(
            Contact.email.ilike(like) | Contact.name.ilike(like) | Contact.company.ilike(like)
        )
    total = q.count()
    items = q.order_by(Contact.last_activity_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_contact_to_dict(c) for c in items], "total": total, "page": page, "page_size": page_size}


@router.patch("/contacts/{contact_id}")
def patch_contact(
    contact_id: str, req: ContactPatch,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = db.get(Contact, _uuid.UUID(contact_id))
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    if req.name is not None:                 c.name = req.name
    if req.phone is not None:                c.phone = req.phone
    if req.address is not None:              c.address = req.address
    if req.company is not None:              c.company = req.company
    if req.website_url is not None:          c.website_url = req.website_url
    if req.status is not None:               c.status = req.status
    if req.is_test_user is not None:         c.is_test_user = req.is_test_user
    if req.features_of_interest is not None: c.features_of_interest = req.features_of_interest
    db.commit()
    db.refresh(c)
    return _contact_to_dict(c)


# ── Action endpoints (trigger Celery / Claude inline) ────────────────────────

@router.post("/campaigns/{campaign_id}/find-leads", status_code=status.HTTP_202_ACCEPTED)
def trigger_find_leads(
    campaign_id: str, req: FindLeadsRequest,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    from aiplatform.worker import run_find_leads as celery_task
    task = celery_task.delay(campaign_id, c.venture, req.max_leads, req.channels, req.search_prompt)
    return {"campaign_id": campaign_id, "celery_task_id": task.id, "status": "queued"}


@router.post("/campaigns/{campaign_id}/compose", status_code=status.HTTP_202_ACCEPTED)
def trigger_compose(
    campaign_id: str, req: ComposeRequest,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    """
    Compose A/B/C email templates for this campaign using Claude.
    Uses the first qualifying lead in the campaign as the persona target.
    """
    c = _campaign_or_404(campaign_id, db)

    sample_lead = db.query(Lead).filter(Lead.campaign_id == c.id).first()
    lead_dict = _lead_to_dict(sample_lead) if sample_lead else {
        "name": "", "notes": "", "website_url": "", "company": "",
        "source_channel": "web", "platform_username": None,
    }

    from aiplatform.skills.comms.compose_outreach import compose_all_variants
    variants = compose_all_variants(
        lead_dict, c.venture, c.goal or "", req.extra_context,
        platform=c.platform or "email",
    )

    regenerate = set(req.regenerate_variants) if req.regenerate_variants else {"A", "B", "C"}

    for email in variants:
        v = email["variant"]
        if v not in regenerate:
            continue
        existing = db.query(OutreachTemplate).filter(
            OutreachTemplate.campaign_id == c.id, OutreachTemplate.variant == v,
        ).first()
        if existing:
            db.delete(existing)
        t = OutreachTemplate(
            campaign_id=c.id, variant=v,
            subject=email["subject"], body_html=email["body_html"],
            body_text=email["body_text"], tone_notes=email["tone_notes"],
            approved="pending",
        )
        db.add(t)

    db.commit()
    return {"campaign_id": campaign_id, "variants_composed": list(regenerate)}


@router.post("/campaigns/{campaign_id}/send", status_code=status.HTTP_202_ACCEPTED)
def trigger_send(
    campaign_id: str, req: SendRequest,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    approved_templates = db.query(OutreachTemplate).filter(
        OutreachTemplate.campaign_id == c.id,
        OutreachTemplate.approved == "approved",
    ).all()
    if not approved_templates:
        raise HTTPException(status_code=409, detail="No approved templates. Review and approve templates first.")
    from aiplatform.worker import run_send_outreach as celery_task
    task = celery_task.delay(campaign_id, req.lead_ids, req.template_variant)
    return {"campaign_id": campaign_id, "celery_task_id": task.id, "status": "queued"}


# ── Stats endpoint ────────────────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/stats")
def get_campaign_stats(
    campaign_id: str, _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    _campaign_or_404(campaign_id, db)
    from aiplatform.skills.comms.analyze_outreach import analyze_campaign
    return analyze_campaign(campaign_id, db)


# ── Tracking endpoints (no auth — called by email pixels/webhooks) ────────────

@router.get("/track/open/{send_id}", include_in_schema=False)
@router.post("/track/open/{send_id}", include_in_schema=False)
def track_open(send_id: str, db=Depends(get_db)):
    from aiplatform.skills.comms.analyze_outreach import record_open
    try:
        record_open(send_id, db)
    except Exception:
        pass
    from fastapi.responses import Response
    gif = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    return Response(content=gif, media_type="image/gif")


@router.post("/track/reply/{send_id}", include_in_schema=False)
def track_reply(send_id: str, db=Depends(get_db)):
    from aiplatform.skills.comms.analyze_outreach import record_reply
    try:
        record_reply(send_id, db)
    except Exception:
        pass
    return {"ok": True}


# ── Unsubscribe endpoint (no auth — linked from every outreach email) ─────────

@router.get("/unsubscribe/{send_id}", include_in_schema=False)
def unsubscribe(send_id: str, db=Depends(get_db)):
    """
    Marks the contact as unsubscribed. Linked from every outreach email.
    Returns a confirmation HTML page.
    Never send to this address again unless they re-subscribe.
    """
    try:
        uid = _uuid.UUID(send_id)
        send = db.get(OutreachSend, uid)
        if send:
            # Mark the send
            send.status = "unsubscribed"
            # Look up the lead
            lead = db.get(Lead, send.lead_id)
            if lead:
                lead.status = "unsubscribed"
                # Only upsert a Contact record if we have an email identifier
                if lead.email:
                    contact = db.query(Contact).filter(Contact.email == lead.email).first()
                    now = datetime.now(timezone.utc)
                    if contact:
                        contact.status = "unsubscribed"
                        contact.unsubscribed_at = now
                        contact.last_activity_at = now
                    else:
                        contact = Contact(
                            email=lead.email,
                            name=lead.name,
                            company=lead.company,
                            website_url=lead.website_url,
                            status="unsubscribed",
                            ventures_approached=[lead.venture] if lead.venture else [],
                            last_activity_at=now,
                            unsubscribed_at=now,
                        )
                        db.add(contact)
            db.commit()
    except Exception:
        pass

    html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Unsubscribed</title>
<style>body{font-family:sans-serif;max-width:480px;margin:80px auto;text-align:center;color:#444;}
h1{color:#222;}p{line-height:1.6;}</style></head>
<body>
<h1>You've been unsubscribed</h1>
<p>You will not receive any further emails from us regarding this or any other campaign.</p>
<p>If this was a mistake, please reply to the email you received and we'll reinstate you.</p>
</body></html>"""
    return HTMLResponse(content=html)
