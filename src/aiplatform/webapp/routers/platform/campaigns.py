"""
Campaign Manager router.

  GET    /api/platform/campaigns                     — list campaigns
  POST   /api/platform/campaigns                     — create campaign record
  GET    /api/platform/campaigns/{id}                — campaign detail + metrics
  PATCH  /api/platform/campaigns/{id}/status         — pause / resume / stop
  POST   /api/platform/campaigns/{id}/creatives/generate  — generate assets (AI)
  POST   /api/platform/campaigns/{id}/creatives/approve   — approve + publish to vendor
  POST   /api/platform/campaigns/{id}/insights       — trigger AI insight engine
  GET    /api/platform/campaigns/formats/{vendor}    — supported creative formats
  GET    /api/platform/campaigns/vendors             — which vendors are configured
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aiplatform.database.models import Campaign, MetricsHistory
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth

log = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateCampaignRequest(BaseModel):
    name: str
    vendor: str                             # google | meta
    daily_budget_limit: float
    total_budget_limit: Optional[float] = None
    creative_prompt: Optional[str] = None


class StatusRequest(BaseModel):
    status: str                             # active | paused | stopped


class InsightRequest(BaseModel):
    market_research_context: Optional[str] = None


class CampaignSummary(BaseModel):
    id: str
    name: str
    vendor: str
    external_id: Optional[str]
    status: str
    daily_budget_limit: Optional[float]
    total_budget_limit: Optional[float]
    drive_folder_id: Optional[str]
    creative_approved: bool
    latest_spend: Optional[float]
    latest_clicks: Optional[int]
    latest_impressions: Optional[int]
    created_at: str


class CampaignDetail(CampaignSummary):
    creative_prompt: Optional[str]
    creative_assets: Optional[list]
    ai_insights: Optional[dict]
    insights_at: Optional[str]
    metrics: list


def _to_summary(c: Campaign) -> CampaignSummary:
    latest = c.metrics[0] if c.metrics else None
    return CampaignSummary(
        id=str(c.id),
        name=c.name,
        vendor=c.vendor,
        external_id=c.external_id,
        status=c.status,
        daily_budget_limit=float(c.daily_budget_limit) if c.daily_budget_limit else None,
        total_budget_limit=float(c.total_budget_limit) if c.total_budget_limit else None,
        drive_folder_id=c.drive_folder_id,
        creative_approved=c.creative_approved,
        latest_spend=float(latest.spend) if latest else None,
        latest_clicks=latest.clicks if latest else None,
        latest_impressions=latest.impressions if latest else None,
        created_at=c.created_at.isoformat(),
    )


def _to_detail(c: Campaign) -> CampaignDetail:
    summary = _to_summary(c)
    metrics_list = [
        {
            "spend": float(m.spend),
            "clicks": m.clicks,
            "impressions": m.impressions,
            "cpa": float(m.cpa) if m.cpa else None,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in c.metrics[:48]  # last 48 hourly snapshots
    ]
    return CampaignDetail(
        **summary.model_dump(),
        creative_prompt=c.creative_prompt,
        creative_assets=c.creative_assets,
        ai_insights=c.ai_insights,
        insights_at=c.insights_at.isoformat() if c.insights_at else None,
        metrics=metrics_list,
    )


def _get_or_404(db: Session, campaign_id: str) -> Campaign:
    try:
        cid = uuid.UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid campaign ID")
    record = db.get(Campaign, cid)
    if not record:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return record


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/vendors")
def get_vendors(_: str = Depends(require_auth)) -> dict:
    """Return which ad vendors have credentials configured."""
    from aiplatform.skills.ads.meta_ads_adapter import available_vendors
    return {"available": available_vendors()}


@router.get("/formats/{vendor}")
def get_formats(
    vendor: str,
    _: str = Depends(require_auth),
) -> dict:
    """Return supported creative formats for a vendor."""
    from aiplatform.skills.ads.meta_ads_adapter import get_adapter
    try:
        adapter = get_adapter(vendor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    formats = [
        {
            "name": f.name,
            "width": f.width,
            "height": f.height,
            "aspect_ratio": f.aspect_ratio,
            "format_type": f.format_type,
        }
        for f in adapter.get_supported_formats()
    ]
    return {"vendor": vendor, "formats": formats}


@router.get("")
def list_campaigns(
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> list[CampaignSummary]:
    records = (
        db.query(Campaign)
        .order_by(Campaign.created_at.desc())
        .limit(100)
        .all()
    )
    return [_to_summary(c) for c in records]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_campaign(
    req: CreateCampaignRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> CampaignSummary:
    """Create a campaign record. Drive folder is created immediately; vendor campaign is created only after creative approval."""
    from aiplatform.skills.ads.meta_ads_adapter import get_adapter
    try:
        get_adapter(req.vendor)  # validate vendor slug
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create Drive folder for campaign assets
    drive_folder_id = None
    try:
        from aiplatform.skills.storage.drive_write import drive_write
        import tempfile, pathlib
        placeholder = pathlib.Path(tempfile.mktemp(suffix=".txt"))
        placeholder.write_text("Campaign assets folder")
        root_folder = os.environ.get("GOOGLE_DRIVE_PLATFORM_ASSETS_ID", "")
        if root_folder:
            result = drive_write(
                local_path=str(placeholder),
                folder_id=root_folder,
                filename=f"[Campaign] {req.name}",
                mime_type="application/vnd.google-apps.folder",
            )
            drive_folder_id = result.get("id") or result.get("file_id")
        placeholder.unlink(missing_ok=True)
    except Exception as e:
        log.warning("Drive folder creation failed (non-fatal): %s", e)

    record = Campaign(
        name=req.name,
        vendor=req.vendor,
        status="draft",
        daily_budget_limit=Decimal(str(req.daily_budget_limit)),
        total_budget_limit=Decimal(str(req.total_budget_limit)) if req.total_budget_limit else None,
        drive_folder_id=drive_folder_id,
        creative_prompt=req.creative_prompt,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_summary(record)


@router.get("/{campaign_id}")
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> CampaignDetail:
    return _to_detail(_get_or_404(db, campaign_id))


@router.patch("/{campaign_id}/status")
def update_status(
    campaign_id: str,
    req: StatusRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> CampaignSummary:
    """Pause, resume, or stop a campaign — syncs status to vendor API if external_id exists."""
    record = _get_or_404(db, campaign_id)
    allowed = {"active", "paused", "stopped"}
    if req.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of {allowed}")

    if record.external_id:
        try:
            from aiplatform.skills.ads.meta_ads_adapter import get_adapter
            adapter = get_adapter(record.vendor)
            if req.status == "active":
                adapter.toggle_status(record.external_id, active=True)
            else:
                adapter.toggle_status(record.external_id, active=False)
        except Exception as e:
            log.warning("Vendor status sync failed (updating DB only): %s", e)

    record.status = req.status
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return _to_summary(record)


@router.post("/{campaign_id}/creatives/generate")
def generate_creatives(
    campaign_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """
    Generate creative assets from the campaign's prompt using the image generation skill.
    Assets are stored in Drive and URLs saved to the campaign record.
    Human approval required before the campaign goes live.
    """
    record = _get_or_404(db, campaign_id)
    if not record.creative_prompt:
        raise HTTPException(status_code=400, detail="Set a creative_prompt on the campaign first.")

    from aiplatform.skills.ads.meta_ads_adapter import get_adapter
    adapter = get_adapter(record.vendor)
    formats = adapter.get_supported_formats()

    from aiplatform.skills.media.generate_image import generate_image
    from aiplatform.skills.storage.drive_write import drive_write
    import pathlib, tempfile

    assets = []
    folder_id = record.drive_folder_id or os.environ.get("GOOGLE_DRIVE_PLATFORM_ASSETS_ID", "root")

    for fmt in formats[:3]:  # generate top-3 formats (limit cost)
        sized_prompt = (
            f"{record.creative_prompt} — {fmt.aspect_ratio} aspect ratio, "
            f"professional ad creative, no text, clean composition"
        )
        try:
            tmp_dir = pathlib.Path(tempfile.mkdtemp())
            img = generate_image(
                prompt=sized_prompt,
                aspect_ratio=fmt.aspect_ratio,
                quality_tier="standard",
                output_dir=tmp_dir,
                filename=f"creative-{fmt.name.lower().replace(' ', '-')}",
            )
            drive_resp = drive_write(
                local_path=img["image_path"],
                folder_id=folder_id,
                share_anyone_with_link=True,
            )
            assets.append({
                "format": fmt.name,
                "aspect_ratio": fmt.aspect_ratio,
                "width": fmt.width,
                "height": fmt.height,
                "url": drive_resp.get("web_view_link", ""),
                "file_id": drive_resp.get("id", ""),
            })
        except Exception as e:
            log.warning("Creative generation failed for format %s: %s", fmt.name, e)
            assets.append({"format": fmt.name, "error": str(e)})

    record.creative_assets = assets
    record.creative_approved = False
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"assets": assets, "pending_approval": True}


@router.post("/{campaign_id}/creatives/approve")
def approve_creatives(
    campaign_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> CampaignSummary:
    """
    Human approves the generated creatives.
    Creates the campaign on the vendor platform and activates it.
    """
    record = _get_or_404(db, campaign_id)
    if not record.creative_assets:
        raise HTTPException(status_code=400, detail="No creatives generated yet.")

    # Create campaign in vendor API
    try:
        from aiplatform.skills.ads.meta_ads_adapter import get_adapter
        adapter = get_adapter(record.vendor)
        if adapter.is_configured():
            external_id = adapter.create_campaign(
                name=record.name,
                daily_budget_usd=float(record.daily_budget_limit or 10),
                total_budget_usd=float(record.total_budget_limit) if record.total_budget_limit else None,
            )
            record.external_id = external_id
            record.status = "active"
            adapter.toggle_status(external_id, active=True)
        else:
            log.warning(
                "Vendor %s not configured — marking approved but not publishing", record.vendor
            )
            record.status = "active"
    except Exception as e:
        log.error("Failed to publish campaign to vendor: %s", e)
        raise HTTPException(status_code=502, detail=f"Vendor API error: {e}")

    record.creative_approved = True
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return _to_summary(record)


@router.post("/{campaign_id}/insights")
def generate_insights(
    campaign_id: str,
    req: InsightRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """
    Run the AI Insight Engine for this campaign.
    Pulls latest metrics + optional market research context → Claude/Gemini → structured suggestions.
    """
    record = _get_or_404(db, campaign_id)

    # Build metrics summary
    metrics_summary = ""
    if record.metrics:
        latest = record.metrics[0]
        metrics_summary = (
            f"Latest spend: ${latest.spend}, Clicks: {latest.clicks}, "
            f"Impressions: {latest.impressions}, CPA: {latest.cpa or 'N/A'}"
        )

    context = req.market_research_context or ""
    prompt = f"""You are a performance marketing analyst. Provide concise, actionable optimization suggestions for this ad campaign.

Campaign: {record.name}
Vendor: {record.vendor}
Status: {record.status}
Daily budget: ${record.daily_budget_limit}

Current metrics:
{metrics_summary or 'No metrics captured yet.'}

{f'Market Research Context:{chr(10)}{context}' if context else ''}

Return a JSON object with this structure:
{{
  "summary": "<one sentence overall assessment>",
  "suggestions": [
    {{"action": "<action to take>", "reason": "<why>", "priority": "high|medium|low"}},
    ...
  ],
  "budget_recommendation": "<keep|increase|decrease — with brief reason>"
}}

Return ONLY the JSON, no commentary."""

    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()

    import json
    start, end = raw.find("{"), raw.rfind("}") + 1
    insights = json.loads(raw[start:end]) if start != -1 else {"raw": raw}

    record.ai_insights = insights
    record.insights_at = datetime.now(timezone.utc)
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"insights": insights}
