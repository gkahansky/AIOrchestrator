"""
Outreach router — cold outreach campaign management.

Endpoints:
  GET/POST   /api/outreach/campaigns
  GET/PATCH  /api/outreach/campaigns/{id}
  GET/POST   /api/outreach/campaigns/{id}/templates
  PATCH      /api/outreach/templates/{id}        (approve/edit)
  GET/POST   /api/outreach/leads
  GET/PATCH  /api/outreach/leads/{id}
  POST       /api/outreach/campaigns/{id}/find-leads   (triggers Celery)
  POST       /api/outreach/campaigns/{id}/compose      (triggers Claude → templates)
  POST       /api/outreach/campaigns/{id}/send         (triggers Celery send)
  GET        /api/outreach/campaigns/{id}/stats        (A/B analysis)
  POST       /api/outreach/track/open/{send_id}        (pixel tracking — no auth)
  POST       /api/outreach/track/reply/{send_id}       (webhook — no auth)
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from aiplatform.database.models import (
    Lead, OutreachCampaign, OutreachTemplate, OutreachSend,
)
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth

router = APIRouter()

VALID_VENTURES = {"marketing_audit", "content_studio", "accessibility_audit"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    venture: str
    name: str
    goal: str | None = None

class CampaignPatch(BaseModel):
    name: str | None = None
    status: str | None = None
    goal: str | None = None

class TemplatePatch(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    approved: str | None = None  # pending | approved | rejected

class LeadCreate(BaseModel):
    venture: str
    source_channel: str
    source_url: str | None = None
    name: str | None = None
    email: str | None = None
    website_url: str | None = None
    company: str | None = None
    notes: str | None = None
    campaign_id: str | None = None

class LeadPatch(BaseModel):
    status: str | None = None
    email: str | None = None
    notes: str | None = None
    campaign_id: str | None = None

class FindLeadsRequest(BaseModel):
    channels: list[str] | None = None   # None = all configured channels
    max_leads: int = 20

class ComposeRequest(BaseModel):
    extra_context: str = ""
    regenerate_variants: list[str] | None = None  # ["A"] to regen only A

class SendRequest(BaseModel):
    lead_ids: list[str] | None = None       # None = all approved leads
    template_variant: str | None = None     # None = distribute across variants


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
        "id":             str(l.id),
        "venture":        l.venture,
        "source_channel": l.source_channel,
        "source_url":     l.source_url,
        "name":           l.name,
        "email":          l.email,
        "website_url":    l.website_url,
        "company":        l.company,
        "notes":          l.notes,
        "status":         l.status,
        "campaign_id":    str(l.campaign_id) if l.campaign_id else None,
        "created_at":     l.created_at.isoformat(),
        "updated_at":     l.updated_at.isoformat(),
    }

def _campaign_to_dict(c: OutreachCampaign, db: Any) -> dict:
    templates = db.query(OutreachTemplate).filter(OutreachTemplate.campaign_id == c.id).all()
    leads_count = db.query(Lead).filter(Lead.campaign_id == c.id).count()
    total_sends = sum(t.sends_count or 0 for t in templates)
    total_opens = sum(t.opens_count or 0 for t in templates)
    total_replies = sum(t.replies_count or 0 for t in templates)
    return {
        "id":           str(c.id),
        "venture":      c.venture,
        "name":         c.name,
        "status":       c.status,
        "goal":         c.goal,
        "leads_count":  leads_count,
        "templates_count": len(templates),
        "total_sends":  total_sends,
        "open_rate":    round(total_opens / total_sends * 100, 1) if total_sends > 0 else 0,
        "reply_rate":   round(total_replies / total_sends * 100, 1) if total_sends > 0 else 0,
        "created_at":   c.created_at.isoformat(),
        "updated_at":   c.updated_at.isoformat(),
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
    c = OutreachCampaign(
        venture=req.venture,
        name=req.name,
        goal=req.goal,
        status="draft",
    )
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
    if req.name is not None:    c.name = req.name
    if req.status is not None:  c.status = req.status
    if req.goal is not None:    c.goal = req.goal
    db.commit()
    db.refresh(c)
    return _campaign_to_dict(c, db)


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
    if req.subject is not None:   t.subject = req.subject
    if req.body_html is not None: t.body_html = req.body_html
    if req.body_text is not None: t.body_text = req.body_text
    if req.approved is not None:  t.approved = req.approved
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
    if venture:     q = q.filter(Lead.venture == venture)
    if status_filter: q = q.filter(Lead.status == status_filter)
    if campaign_id:
        q = q.filter(Lead.campaign_id == _uuid.UUID(campaign_id))
    total = q.count()
    items = q.order_by(Lead.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"items": [_lead_to_dict(l) for l in items], "total": total, "page": page, "page_size": page_size}


@router.post("/leads", status_code=status.HTTP_201_CREATED)
def create_lead(
    req: LeadCreate,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    campaign_uuid = _uuid.UUID(req.campaign_id) if req.campaign_id else None
    l = Lead(
        venture=req.venture, source_channel=req.source_channel,
        source_url=req.source_url, name=req.name, email=req.email,
        website_url=req.website_url, company=req.company,
        notes=req.notes, campaign_id=campaign_uuid, status="new",
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return _lead_to_dict(l)


@router.patch("/leads/{lead_id}")
def patch_lead(
    lead_id: str,
    req: LeadPatch,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    l = db.get(Lead, _uuid.UUID(lead_id))
    if not l:
        raise HTTPException(status_code=404, detail="Lead not found")
    if req.status is not None:      l.status = req.status
    if req.email is not None:       l.email = req.email
    if req.notes is not None:       l.notes = req.notes
    if req.campaign_id is not None: l.campaign_id = _uuid.UUID(req.campaign_id)
    db.commit()
    db.refresh(l)
    return _lead_to_dict(l)


# ── Action endpoints (trigger Celery) ────────────────────────────────────────

@router.post("/campaigns/{campaign_id}/find-leads", status_code=status.HTTP_202_ACCEPTED)
def trigger_find_leads(
    campaign_id: str,
    req: FindLeadsRequest,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    """Dispatch a Celery task to find leads for this campaign's venture."""
    c = _campaign_or_404(campaign_id, db)
    from aiplatform.worker import run_find_leads as celery_task
    task = celery_task.delay(campaign_id, c.venture, req.max_leads, req.channels)
    return {"campaign_id": campaign_id, "celery_task_id": task.id, "status": "queued"}


@router.post("/campaigns/{campaign_id}/compose", status_code=status.HTTP_202_ACCEPTED)
def trigger_compose(
    campaign_id: str,
    req: ComposeRequest,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    """
    Compose A/B/C email templates for this campaign using Claude.
    Uses the first qualifying lead in the campaign as the persona target.
    Existing templates are replaced unless regenerate_variants is specified.
    """
    c = _campaign_or_404(campaign_id, db)

    # Find a representative lead to write for
    sample_lead = db.query(Lead).filter(
        Lead.campaign_id == c.id
    ).first()

    lead_dict = _lead_to_dict(sample_lead) if sample_lead else {
        "name": "", "notes": "", "website_url": "", "company": "", "source_channel": "web",
    }

    from aiplatform.skills.comms.compose_outreach import compose_all_variants
    variants = compose_all_variants(lead_dict, c.venture, c.goal or "", req.extra_context)

    regenerate = set(req.regenerate_variants) if req.regenerate_variants else {"A", "B", "C"}

    for email in variants:
        v = email["variant"]
        if v not in regenerate:
            continue
        # Delete existing template for this variant if any
        existing = db.query(OutreachTemplate).filter(
            OutreachTemplate.campaign_id == c.id,
            OutreachTemplate.variant == v,
        ).first()
        if existing:
            db.delete(existing)

        t = OutreachTemplate(
            campaign_id=c.id,
            variant=v,
            subject=email["subject"],
            body_html=email["body_html"],
            body_text=email["body_text"],
            tone_notes=email["tone_notes"],
            approved="pending",
        )
        db.add(t)

    db.commit()
    return {"campaign_id": campaign_id, "variants_composed": list(regenerate)}


@router.post("/campaigns/{campaign_id}/send", status_code=status.HTTP_202_ACCEPTED)
def trigger_send(
    campaign_id: str,
    req: SendRequest,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    """
    Send approved templates to leads. Only approved templates are sent.
    Leads are distributed round-robin across variants unless variant is specified.
    """
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
    campaign_id: str,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    """Run A/B analysis via Claude and return results."""
    _campaign_or_404(campaign_id, db)
    from aiplatform.skills.comms.analyze_outreach import analyze_campaign
    return analyze_campaign(campaign_id, db)


# ── Tracking endpoints (no auth — called by email pixels/webhooks) ────────────

@router.get("/track/open/{send_id}", include_in_schema=False)
@router.post("/track/open/{send_id}", include_in_schema=False)
def track_open(send_id: str, db=Depends(get_db)):
    """1x1 pixel tracking endpoint — records an open event."""
    from aiplatform.skills.comms.analyze_outreach import record_open
    try:
        record_open(send_id, db)
    except Exception:
        pass
    # Return 1x1 transparent GIF
    from fastapi.responses import Response
    gif = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    return Response(content=gif, media_type="image/gif")


@router.post("/track/reply/{send_id}", include_in_schema=False)
def track_reply(send_id: str, db=Depends(get_db)):
    """Webhook endpoint — called when a reply is detected."""
    from aiplatform.skills.comms.analyze_outreach import record_reply
    try:
        record_reply(send_id, db)
    except Exception:
        pass
    return {"ok": True}
