"""
Outreach router — persona-driven campaign management + unified contact CRM.

Endpoints:
  GET/POST        /api/outreach/campaigns
  GET/PATCH/DELETE /api/outreach/campaigns/{id}
  PATCH           /api/outreach/campaigns/{id}/schedule
  POST            /api/outreach/campaigns/{id}/generate-prompt
  POST            /api/outreach/campaigns/{id}/find-leads
  POST            /api/outreach/campaigns/{id}/compose-pending   (draft all new leads)
  POST            /api/outreach/campaigns/{id}/compose-lead/{lead_id}
  POST            /api/outreach/campaigns/{id}/send-approved     (send approved drafts)
  POST            /api/outreach/campaigns/{id}/compose           (legacy A/B)
  POST            /api/outreach/campaigns/{id}/send              (legacy A/B send)
  GET             /api/outreach/campaigns/{id}/stats             (legacy A/B stats)
  GET/POST        /api/outreach/campaigns/{id}/templates         (legacy)
  PATCH           /api/outreach/templates/{id}                   (legacy)
  GET/POST        /api/outreach/campaigns/{id}/sources
  PATCH/DELETE    /api/outreach/sources/{id}
  GET             /api/outreach/campaigns/{id}/drafts
  PATCH           /api/outreach/drafts/{id}
  GET/POST        /api/outreach/leads
  GET/PATCH       /api/outreach/leads/{id}
  GET/PATCH       /api/outreach/contacts
  PATCH           /api/outreach/contacts/{id}
  GET             /api/outreach/unsubscribe/{send_id}
  GET/POST        /api/outreach/track/open/{send_id}
  POST            /api/outreach/track/reply/{send_id}
"""

from __future__ import annotations

import json
import os
import uuid as _uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from aiplatform.database.models import (
    CampaignSource, Contact, Lead, LeadDraft,
    OutreachCampaign, OutreachTemplate, OutreachSend,
)
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth

router = APIRouter()

# ── Outreach config — loaded from JSON file, path overrideable via env var ─────
# Edit config/outreach_sources.json to add ventures/platforms without a deploy.
# Set OUTREACH_CONFIG_PATH on Railway to point to a custom file.

def _load_outreach_config() -> dict:
    config_path = Path(
        os.environ.get("OUTREACH_CONFIG_PATH", "config/outreach_sources.json")
    )
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}

_cfg = _load_outreach_config()

VALID_VENTURES: set[str] = set(_cfg.get("valid_ventures", [
    "marketing_audit", "content_studio", "accessibility_audit",
    "security_audit", "market_research",
]))
VALID_PLATFORMS: set[str] = set(_cfg.get("valid_platforms", [
    "email", "fiverr", "reddit", "linkedin", "facebook", "instagram",
]))
VALID_SOURCE_PLATFORMS: set[str] = set(_cfg.get("valid_source_platforms", [
    "reddit", "google", "linkedin", "facebook",
    "hackernews", "indiehackers", "fiverr", "listennotes",
]))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PersonaSchema(BaseModel):
    name: str
    description: str

class CampaignCreate(BaseModel):
    venture: str
    name: str
    goal: str | None = None
    platform: str = "email"
    personas: list[PersonaSchema] | None = None
    target_prompt: str | None = None
    user_search_instructions: str | None = None
    auto_search_enabled: bool = False
    search_interval_hours: int | None = None

class CampaignPatch(BaseModel):
    name: str | None = None
    status: str | None = None
    goal: str | None = None
    platform: str | None = None
    personas: list[PersonaSchema] | None = None
    target_prompt: str | None = None
    user_search_instructions: str | None = None

class SchedulePatch(BaseModel):
    auto_search_enabled: bool
    search_interval_hours: int | None = None  # 6 | 24 | 168 | None (manual)

class SourceCreate(BaseModel):
    platform: str
    name: str
    keywords: list[str] = []
    config: dict = {}
    enabled: bool = True

class SourcePatch(BaseModel):
    name: str | None = None
    keywords: list[str] | None = None
    config: dict | None = None
    enabled: bool | None = None

class DraftPatch(BaseModel):
    subject: str | None = None
    message_body: str | None = None
    status: str | None = None   # pending_review | approved | rejected

class TemplatePatch(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    approved: str | None = None
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
    max_leads: int = 20
    search_prompt: str | None = None

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


# ── Serialisers ───────────────────────────────────────────────────────────────

def _campaign_or_404(campaign_id: str, db: Any) -> OutreachCampaign:
    try:
        uid = _uuid.UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid campaign_id format")
    obj = db.get(OutreachCampaign, uid)
    if not obj:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return obj

def _source_to_dict(s: CampaignSource) -> dict:
    return {
        "id":          str(s.id),
        "campaign_id": str(s.campaign_id),
        "platform":    s.platform,
        "name":        s.name,
        "keywords":    s.keywords or [],
        "config":      s.config or {},
        "enabled":     s.enabled,
        "created_at":  s.created_at.isoformat(),
        "updated_at":  s.updated_at.isoformat(),
    }

def _draft_to_dict(d: LeadDraft, lead: Lead | None = None) -> dict:
    result = {
        "id":           str(d.id),
        "lead_id":      str(d.lead_id),
        "campaign_id":  str(d.campaign_id),
        "subject":      d.subject,
        "message_body": d.message_body,
        "context_used": d.context_used,
        "status":       d.status,
        "generated_at": d.generated_at.isoformat(),
        "reviewed_at":  d.reviewed_at.isoformat() if d.reviewed_at else None,
        "sent_at":      d.sent_at.isoformat() if d.sent_at else None,
    }
    if lead:
        result["lead"] = {
            "name":             lead.name,
            "platform_username": lead.platform_username,
            "source_channel":   lead.source_channel,
            "source_url":       lead.source_url,
            "company":          lead.company,
            "context":          lead.context,
            "matched_persona":  lead.matched_persona,
            "status":           lead.status,
        }
    return result

def _template_to_dict(t: OutreachTemplate) -> dict:
    sends = t.sends_count or 0
    return {
        "id": str(t.id), "campaign_id": str(t.campaign_id), "variant": t.variant,
        "subject": t.subject, "body_html": t.body_html, "body_text": t.body_text,
        "tone_notes": t.tone_notes, "approved": t.approved,
        "sends": sends, "opens": t.opens_count or 0, "replies": t.replies_count or 0,
        "open_rate":  round((t.opens_count or 0) / sends * 100, 1) if sends > 0 else 0,
        "reply_rate": round((t.replies_count or 0) / sends * 100, 1) if sends > 0 else 0,
        "created_at": t.created_at.isoformat(), "updated_at": t.updated_at.isoformat(),
    }

def _lead_to_dict(l: Lead) -> dict:
    return {
        "id": str(l.id), "venture": l.venture,
        "source_channel": l.source_channel, "source_url": l.source_url,
        "name": l.name, "email": l.email,
        "platform_username": l.platform_username,
        "website_url": l.website_url, "company": l.company,
        "notes": l.notes,
        "context": l.context,
        "matched_persona": l.matched_persona,
        "status": l.status,
        "campaign_id": str(l.campaign_id) if l.campaign_id else None,
        "created_at": l.created_at.isoformat(), "updated_at": l.updated_at.isoformat(),
    }

def _contact_to_dict(c: Contact) -> dict:
    return {
        "id": str(c.id), "email": c.email, "usernames": c.usernames or {},
        "name": c.name, "phone": c.phone, "address": c.address,
        "company": c.company, "website_url": c.website_url,
        "status": c.status, "is_test_user": c.is_test_user,
        "ventures_approached": c.ventures_approached or [],
        "features_of_interest": c.features_of_interest or {},
        "last_activity_at": c.last_activity_at.isoformat() if c.last_activity_at else None,
        "purchased_at": c.purchased_at.isoformat() if c.purchased_at else None,
        "unsubscribed_at": c.unsubscribed_at.isoformat() if c.unsubscribed_at else None,
        "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat(),
    }

def _campaign_to_dict(c: OutreachCampaign, db: Any) -> dict:
    from sqlalchemy import func
    templates = db.query(OutreachTemplate).filter(OutreachTemplate.campaign_id == c.id).all()
    leads_count = db.query(Lead).filter(Lead.campaign_id == c.id).count()
    drafts_pending = db.query(LeadDraft).filter(
        LeadDraft.campaign_id == c.id, LeadDraft.status == "pending_review"
    ).count()
    total_sends = sum(t.sends_count or 0 for t in templates)
    total_opens = sum(t.opens_count or 0 for t in templates)
    total_replies = sum(t.replies_count or 0 for t in templates)
    return {
        "id": str(c.id), "venture": c.venture, "name": c.name,
        "status": c.status, "goal": c.goal, "platform": c.platform or "email",
        "personas": c.personas or [],
        "target_prompt": c.target_prompt,
        "user_search_instructions": c.user_search_instructions,
        "auto_search_enabled": c.auto_search_enabled,
        "search_interval_hours": c.search_interval_hours,
        "next_search_at": c.next_search_at.isoformat() if c.next_search_at else None,
        "last_search_at": c.last_search_at.isoformat() if c.last_search_at else None,
        "leads_count": leads_count,
        "drafts_pending": drafts_pending,
        "templates_count": len(templates),
        "total_sends": total_sends,
        "open_rate": round(total_opens / total_sends * 100, 1) if total_sends > 0 else 0,
        "reply_rate": round(total_replies / total_sends * 100, 1) if total_sends > 0 else 0,
        "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat(),
    }


# ── Campaign endpoints ────────────────────────────────────────────────────────

@router.get("/campaigns")
def list_campaigns(
    venture: str | None = Query(None),
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    q = db.query(OutreachCampaign)
    if venture:
        q = q.filter(OutreachCampaign.venture == venture)
    items = q.order_by(OutreachCampaign.created_at.desc()).all()
    return {"items": [_campaign_to_dict(c, db) for c in items], "total": len(items)}


@router.post("/campaigns", status_code=status.HTTP_201_CREATED)
def create_campaign(
    req: CampaignCreate, _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    if req.venture not in VALID_VENTURES:
        raise HTTPException(status_code=400, detail=f"venture must be one of {VALID_VENTURES}")
    if req.platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"platform must be one of {VALID_PLATFORMS}")

    c = OutreachCampaign(
        venture=req.venture, name=req.name, goal=req.goal,
        status="draft", platform=req.platform,
        personas=[p.model_dump() for p in req.personas] if req.personas else [],
        target_prompt=req.target_prompt,
        user_search_instructions=req.user_search_instructions,
        auto_search_enabled=req.auto_search_enabled,
        search_interval_hours=req.search_interval_hours,
    )
    if req.auto_search_enabled and req.search_interval_hours:
        c.next_search_at = datetime.now(timezone.utc) + timedelta(hours=req.search_interval_hours)

    db.add(c)
    db.flush()  # get c.id before seeding sources

    # Seed default sources for this venture
    from aiplatform.skills.research.find_leads import VENTURE_DEFAULT_SOURCES
    for src_def in VENTURE_DEFAULT_SOURCES.get(req.venture, []):
        db.add(CampaignSource(
            campaign_id=c.id,
            platform=src_def["platform"],
            name=src_def["name"],
            keywords=src_def["keywords"],
            config=src_def.get("config") or {},
            enabled=True,
        ))

    db.commit()
    db.refresh(c)
    result = _campaign_to_dict(c, db)
    result["sources"] = [_source_to_dict(s) for s in c.sources]
    return result


@router.get("/campaigns/{campaign_id}")
def get_campaign(
    campaign_id: str, _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    result = _campaign_to_dict(c, db)
    result["templates"] = [_template_to_dict(t) for t in db.query(OutreachTemplate).filter(
        OutreachTemplate.campaign_id == c.id).all()]
    result["sources"] = [_source_to_dict(s) for s in c.sources]
    return result


@router.patch("/campaigns/{campaign_id}")
def patch_campaign(
    campaign_id: str, req: CampaignPatch,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    if req.name is not None:       c.name = req.name
    if req.status is not None:     c.status = req.status
    if req.goal is not None:       c.goal = req.goal
    if req.platform is not None:
        if req.platform not in VALID_PLATFORMS:
            raise HTTPException(status_code=400, detail=f"platform must be one of {VALID_PLATFORMS}")
        c.platform = req.platform
    if req.personas is not None:           c.personas = [p.model_dump() for p in req.personas]
    if req.target_prompt is not None:      c.target_prompt = req.target_prompt
    if req.user_search_instructions is not None:
        c.user_search_instructions = req.user_search_instructions
    db.commit()
    db.refresh(c)
    result = _campaign_to_dict(c, db)
    result["sources"] = [_source_to_dict(s) for s in c.sources]
    return result


@router.patch("/campaigns/{campaign_id}/schedule")
def patch_schedule(
    campaign_id: str, req: SchedulePatch,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    c.auto_search_enabled = req.auto_search_enabled
    c.search_interval_hours = req.search_interval_hours
    if req.auto_search_enabled and req.search_interval_hours:
        c.next_search_at = datetime.now(timezone.utc) + timedelta(hours=req.search_interval_hours)
    else:
        c.next_search_at = None
    db.commit()
    db.refresh(c)
    return _campaign_to_dict(c, db)


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: str, _: str = Depends(require_auth), db=Depends(get_db),
):
    c = _campaign_or_404(campaign_id, db)
    db.delete(c)
    db.commit()


# ── Sources endpoints ─────────────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/sources")
def list_sources(
    campaign_id: str, _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    return {"items": [_source_to_dict(s) for s in c.sources]}


@router.post("/campaigns/{campaign_id}/sources", status_code=status.HTTP_201_CREATED)
def create_source(
    campaign_id: str, req: SourceCreate,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    if req.platform not in VALID_SOURCE_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"platform must be one of {VALID_SOURCE_PLATFORMS}")
    s = CampaignSource(
        campaign_id=c.id, platform=req.platform, name=req.name,
        keywords=req.keywords, config=req.config, enabled=req.enabled,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _source_to_dict(s)


@router.patch("/sources/{source_id}")
def patch_source(
    source_id: str, req: SourcePatch,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    s = db.get(CampaignSource, _uuid.UUID(source_id))
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")
    if req.name is not None:     s.name = req.name
    if req.keywords is not None: s.keywords = req.keywords
    if req.config is not None:   s.config = req.config
    if req.enabled is not None:  s.enabled = req.enabled
    db.commit()
    db.refresh(s)
    return _source_to_dict(s)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: str, _: str = Depends(require_auth), db=Depends(get_db),
):
    s = db.get(CampaignSource, _uuid.UUID(source_id))
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")
    db.delete(s)
    db.commit()


# ── Draft endpoints ───────────────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/drafts")
def list_drafts(
    campaign_id: str,
    draft_status: str | None = Query(None, alias="status"),
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    _campaign_or_404(campaign_id, db)
    q = db.query(LeadDraft).filter(LeadDraft.campaign_id == _uuid.UUID(campaign_id))
    if draft_status:
        q = q.filter(LeadDraft.status == draft_status)
    drafts = q.order_by(LeadDraft.generated_at.desc()).all()
    lead_ids = {d.lead_id for d in drafts}
    leads_map = {l.id: l for l in db.query(Lead).filter(Lead.id.in_(lead_ids)).all()}
    return {
        "items": [_draft_to_dict(d, leads_map.get(d.lead_id)) for d in drafts],
        "total": len(drafts),
    }


@router.patch("/drafts/{draft_id}")
def patch_draft(
    draft_id: str, req: DraftPatch,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    d = db.get(LeadDraft, _uuid.UUID(draft_id))
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")
    if req.subject is not None:       d.subject = req.subject
    if req.message_body is not None:  d.message_body = req.message_body
    if req.status is not None:
        valid = {"pending_review", "approved", "rejected"}
        if req.status not in valid:
            raise HTTPException(status_code=400, detail=f"status must be one of {valid}")
        d.status = req.status
        if req.status in ("approved", "rejected"):
            d.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(d)
    lead = db.get(Lead, d.lead_id)
    return _draft_to_dict(d, lead)


# ── Action endpoints ─────────────────────────────────────────────────────────

@router.post("/campaigns/{campaign_id}/generate-prompt")
def generate_search_prompt(
    campaign_id: str, _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    import anthropic as _anthropic
    c = _campaign_or_404(campaign_id, db)

    venture_descriptions = {
        "marketing_audit": (
            "website marketing audit — SEO, messaging, conversion, competitive positioning. "
            "Target: small business owners, SaaS founders, e-commerce operators."
        ),
        "content_studio": (
            "podcast show notes service — audio → show notes, timestamps, transcripts, social posts. "
            "Target: podcasters who need to save time on content production."
        ),
        "accessibility_audit": (
            "WCAG accessibility audit — scan for violations, prioritised fix list with code examples. "
            "Target: web developers, agencies, startups with public-facing websites."
        ),
    }
    venture_desc = venture_descriptions.get(c.venture, c.venture)
    platform = c.platform or "email"

    persona_block = ""
    if c.personas:
        lines = "\n".join(f"  - {p['name']}: {p.get('description','')}" for p in c.personas)
        persona_block = f"\nCUSTOMER PERSONAS:\n{lines}\n"

    target_block = f"\nPRODUCT/AUDIENCE CONTEXT:\n{c.target_prompt}\n" if c.target_prompt else ""

    prompt = f"""Generate a lead search criteria prompt for a cold outreach campaign.

VENTURE: {c.venture}
SERVICE: {venture_desc}
PLATFORM: {platform.upper()}
{persona_block}{target_block}
The prompt will guide an AI when searching and qualifying leads on {platform}.

Include sections: TARGET PROFILE, PAIN SIGNALS, DISQUALIFIERS, IDENTIFIER TO CAPTURE,
CONTEXT NOTES, SEARCH QUERIES (4-6 platform-specific queries).

Output the structured prompt directly, starting with "TARGET PROFILE:". Under 450 words."""

    client = _anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "campaign_id": campaign_id,
        "prompt": msg.content[0].text.strip(),
        "cost_usd": round((msg.usage.input_tokens * 0.8 + msg.usage.output_tokens * 4) / 1_000_000, 6),
    }


@router.post("/campaigns/{campaign_id}/find-leads", status_code=status.HTTP_202_ACCEPTED)
def trigger_find_leads(
    campaign_id: str, req: FindLeadsRequest,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    sources = [_source_to_dict(s) for s in c.sources if s.enabled]
    personas = c.personas or []
    from aiplatform.worker import run_find_leads as celery_task
    task = celery_task.delay(campaign_id, c.venture, req.max_leads, sources,
                             req.search_prompt, personas)
    return {"campaign_id": campaign_id, "celery_task_id": task.id, "status": "queued"}


@router.post("/campaigns/{campaign_id}/compose-pending", status_code=status.HTTP_202_ACCEPTED)
def trigger_compose_pending(
    campaign_id: str, _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    """Queue drafts for all leads in 'new' status that don't have a draft yet."""
    c = _campaign_or_404(campaign_id, db)
    from aiplatform.worker import run_compose_pending as celery_task
    task = celery_task.delay(campaign_id)
    return {"campaign_id": campaign_id, "celery_task_id": task.id, "status": "queued"}


@router.post("/campaigns/{campaign_id}/compose-lead/{lead_id}")
def compose_for_lead(
    campaign_id: str, lead_id: str,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    """Generate a personalized draft for a single lead (inline, not Celery)."""
    c = _campaign_or_404(campaign_id, db)
    lead = db.get(Lead, _uuid.UUID(lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Remove existing draft if present
    existing = db.query(LeadDraft).filter(
        LeadDraft.lead_id == lead.id, LeadDraft.campaign_id == c.id,
        LeadDraft.status == "pending_review",
    ).first()
    if existing:
        db.delete(existing)

    from aiplatform.skills.comms.compose_personalized import compose_for_lead as _compose
    campaign_dict = _campaign_to_dict(c, db)
    composed = _compose(_lead_to_dict(lead), campaign_dict)

    draft = LeadDraft(
        lead_id=lead.id, campaign_id=c.id,
        subject=composed.get("subject"),
        message_body=composed["message_body"],
        context_used=composed.get("context_used"),
        status="pending_review",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_to_dict(draft, lead)


@router.post("/campaigns/{campaign_id}/send-approved", status_code=status.HTTP_202_ACCEPTED)
def trigger_send_approved(
    campaign_id: str, _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    """Send all approved drafts."""
    c = _campaign_or_404(campaign_id, db)
    approved_count = db.query(LeadDraft).filter(
        LeadDraft.campaign_id == c.id, LeadDraft.status == "approved",
    ).count()
    if not approved_count:
        raise HTTPException(status_code=409, detail="No approved drafts to send.")
    from aiplatform.worker import run_send_approved_drafts as celery_task
    task = celery_task.delay(campaign_id)
    return {"campaign_id": campaign_id, "celery_task_id": task.id,
            "approved_drafts": approved_count, "status": "queued"}


# ── Legacy A/B endpoints (kept for existing campaigns) ────────────────────────

@router.get("/campaigns/{campaign_id}/templates")
def list_templates(
    campaign_id: str, _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    _campaign_or_404(campaign_id, db)
    templates = db.query(OutreachTemplate).filter(
        OutreachTemplate.campaign_id == _uuid.UUID(campaign_id)
    ).all()
    return {"items": [_template_to_dict(t) for t in templates]}


@router.patch("/templates/{template_id}")
def patch_template(
    template_id: str, req: TemplatePatch,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    t = db.get(OutreachTemplate, _uuid.UUID(template_id))
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


@router.post("/campaigns/{campaign_id}/compose", status_code=status.HTTP_202_ACCEPTED)
def trigger_compose(
    campaign_id: str, req: ComposeRequest,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    sample_lead = db.query(Lead).filter(Lead.campaign_id == c.id).first()
    lead_dict = _lead_to_dict(sample_lead) if sample_lead else {
        "name": "", "notes": "", "website_url": "", "company": "",
        "source_channel": "web", "platform_username": None,
    }
    from aiplatform.skills.comms.compose_outreach import compose_all_variants
    variants = compose_all_variants(lead_dict, c.venture, c.goal or "", req.extra_context,
                                    platform=c.platform or "email")
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
        db.add(OutreachTemplate(
            campaign_id=c.id, variant=v, subject=email["subject"],
            body_html=email["body_html"], body_text=email["body_text"],
            tone_notes=email["tone_notes"], approved="pending",
        ))
    db.commit()
    return {"campaign_id": campaign_id, "variants_composed": list(regenerate)}


@router.post("/campaigns/{campaign_id}/send", status_code=status.HTTP_202_ACCEPTED)
def trigger_send(
    campaign_id: str, req: SendRequest,
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    c = _campaign_or_404(campaign_id, db)
    approved_templates = db.query(OutreachTemplate).filter(
        OutreachTemplate.campaign_id == c.id, OutreachTemplate.approved == "approved",
    ).all()
    if not approved_templates:
        raise HTTPException(status_code=409, detail="No approved templates.")
    from aiplatform.worker import run_send_outreach as celery_task
    task = celery_task.delay(campaign_id, req.lead_ids, req.template_variant)
    return {"campaign_id": campaign_id, "celery_task_id": task.id, "status": "queued"}


@router.get("/campaigns/{campaign_id}/stats")
def get_campaign_stats(
    campaign_id: str, _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    _campaign_or_404(campaign_id, db)
    from aiplatform.skills.comms.analyze_outreach import analyze_campaign
    return analyze_campaign(campaign_id, db)


# ── Leads endpoints ───────────────────────────────────────────────────────────

@router.get("/leads")
def list_leads(
    venture: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    campaign_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    q = db.query(Lead)
    if venture:      q = q.filter(Lead.venture == venture)
    if status_filter: q = q.filter(Lead.status == status_filter)
    if campaign_id:  q = q.filter(Lead.campaign_id == _uuid.UUID(campaign_id))
    total = q.count()
    items = q.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_lead_to_dict(l) for l in items], "total": total,
            "page": page, "page_size": page_size}


@router.post("/leads", status_code=status.HTTP_201_CREATED)
def create_lead(req: LeadCreate, _: str = Depends(require_auth), db=Depends(get_db)) -> dict:
    if not req.email and not req.platform_username:
        raise HTTPException(status_code=400,
                            detail="Lead must have email or platform_username.")
    l = Lead(
        venture=req.venture, source_channel=req.source_channel,
        source_url=req.source_url, name=req.name, email=req.email,
        platform_username=req.platform_username, website_url=req.website_url,
        company=req.company, notes=req.notes,
        campaign_id=_uuid.UUID(req.campaign_id) if req.campaign_id else None,
        status="new",
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
    if req.status is not None:            l.status = req.status
    if req.email is not None:             l.email = req.email
    if req.platform_username is not None: l.platform_username = req.platform_username
    if req.notes is not None:             l.notes = req.notes
    if req.campaign_id is not None:       l.campaign_id = _uuid.UUID(req.campaign_id)
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
    _: str = Depends(require_auth), db=Depends(get_db),
) -> dict:
    q = db.query(Contact)
    if status_filter: q = q.filter(Contact.status == status_filter)
    if venture:       q = q.filter(Contact.ventures_approached.contains([venture]))
    if search:
        like = f"%{search}%"
        q = q.filter(Contact.email.ilike(like) | Contact.name.ilike(like) | Contact.company.ilike(like))
    total = q.count()
    items = q.order_by(Contact.last_activity_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_contact_to_dict(c) for c in items], "total": total,
            "page": page, "page_size": page_size}


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


# ── Tracking endpoints (no auth) ──────────────────────────────────────────────

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


@router.get("/unsubscribe/{send_id}", include_in_schema=False)
def unsubscribe(send_id: str, db=Depends(get_db)):
    try:
        uid = _uuid.UUID(send_id)
        send = db.get(OutreachSend, uid)
        if send:
            send.status = "unsubscribed"
            lead = db.get(Lead, send.lead_id)
            if lead:
                lead.status = "unsubscribed"
                if lead.email:
                    now = datetime.now(timezone.utc)
                    contact = db.query(Contact).filter(Contact.email == lead.email).first()
                    if contact:
                        contact.status = "unsubscribed"
                        contact.unsubscribed_at = now
                        contact.last_activity_at = now
                    else:
                        db.add(Contact(
                            email=lead.email, name=lead.name, company=lead.company,
                            website_url=lead.website_url, status="unsubscribed",
                            ventures_approached=[lead.venture] if lead.venture else [],
                            last_activity_at=now, unsubscribed_at=now,
                        ))
            db.commit()
    except Exception:
        pass
    html = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Unsubscribed</title>
<style>body{font-family:sans-serif;max-width:480px;margin:80px auto;text-align:center;color:#444;}
h1{color:#222;}p{line-height:1.6;}</style></head>
<body><h1>You've been unsubscribed</h1>
<p>You will not receive any further emails from us regarding this or any other campaign.</p>
<p>If this was a mistake, please reply to the email you received.</p></body></html>"""
    return HTMLResponse(content=html)
