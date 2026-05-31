"""Content Engine venture router.

Multi-channel content creation + publishing for EchoForge Accessibility
(and future brands).

  /api/ventures/content-engine/brands
  /api/ventures/content-engine/strategies
  /api/ventures/content-engine/items
  /api/ventures/content-engine/items/{id}/{generate,approve,revise,schedule,publish-now,unschedule}
  /api/ventures/content-engine/publish-jobs
  /api/ventures/content-engine/social-accounts
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aiplatform.database.models import (
    ContentAsset,
    ContentBrand,
    ContentItem,
    ContentStrategy,
    PublishJob,
    SocialAccount,
)
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class BrandIn(BaseModel):
    slug: str
    name: str
    venture_tag: str | None = None
    description: str | None = None
    voice_profile_json: dict[str, Any] | None = None
    theme_weights: dict[str, float] | None = None
    banned_phrases: list[str] | None = None
    channel_cadence: dict[str, int] | None = None
    target_personas: list[dict[str, Any]] | None = None
    auto_strategy_enabled: bool = False


class BrandOut(BaseModel):
    id: str
    slug: str
    name: str
    venture_tag: str | None
    description: str | None
    voice_profile_json: dict[str, Any]
    theme_weights: dict[str, Any]
    banned_phrases: list[str]
    channel_cadence: dict[str, Any]
    target_personas: list[dict[str, Any]]
    auto_strategy_enabled: bool
    created_at: str
    updated_at: str


class StrategyIn(BaseModel):
    brand_id: str
    title: str | None = None
    period_days: int = 30
    channel_cadence: dict[str, int] | None = None


class StrategyOut(BaseModel):
    id: str
    brand_id: str
    title: str
    period_days: int
    status: str
    pillars: list[Any]
    channel_cadence: dict[str, Any]
    calendar: list[dict[str, Any]]
    notes: str | None
    created_at: str
    updated_at: str
    approved_at: str | None


class ItemIn(BaseModel):
    brand_id: str
    strategy_id: str | None = None
    title: str | None = None
    format: str = "post"
    channels: list[str] = Field(default_factory=list)
    pillar: str | None = None
    topic: str | None = None
    scheduled_for: str | None = None  # ISO8601
    brief_json: dict[str, Any] | None = None


class ItemPatch(BaseModel):
    title: str | None = None
    format: str | None = None
    channels: list[str] | None = None
    pillar: str | None = None
    topic: str | None = None
    scheduled_for: str | None = None
    variants_json: dict[str, Any] | None = None
    review_notes: str | None = None
    status: str | None = None


class ItemOut(BaseModel):
    id: str
    brand_id: str
    strategy_id: str | None
    title: str | None
    format: str
    channels: list[str]
    pillar: str | None
    topic: str | None
    status: str
    scheduled_for: str | None
    brief_json: dict[str, Any]
    variants_json: dict[str, Any]
    quality_report_json: dict[str, Any]
    review_notes: str | None
    error_message: str | None
    created_at: str
    updated_at: str
    approved_at: str | None
    published_at: str | None
    asset_count: int
    publish_job_count: int


class SocialAccountIn(BaseModel):
    brand_id: str
    platform: str
    account_id: str | None = None
    account_name: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: str | None = None
    scopes: list[str] | None = None
    enabled: bool = True


class SocialAccountOut(BaseModel):
    id: str
    brand_id: str
    platform: str
    account_id: str | None
    account_name: str | None
    has_token: bool
    expires_at: str | None
    scopes: list[str]
    enabled: bool
    created_at: str


class PublishJobOut(BaseModel):
    id: str
    item_id: str
    channel: str
    status: str
    external_post_id: str | None
    external_url: str | None
    deep_link: str | None
    error_message: str | None
    created_at: str
    published_at: str | None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _brand_to_out(b: ContentBrand) -> BrandOut:
    return BrandOut(
        id=str(b.id),
        slug=b.slug,
        name=b.name,
        venture_tag=b.venture_tag,
        description=b.description,
        voice_profile_json=b.voice_profile_json or {},
        theme_weights=b.theme_weights or {},
        banned_phrases=b.banned_phrases or [],
        channel_cadence=b.channel_cadence or {},
        target_personas=b.target_personas or [],
        auto_strategy_enabled=b.auto_strategy_enabled,
        created_at=_iso(b.created_at) or "",
        updated_at=_iso(b.updated_at) or "",
    )


def _strategy_to_out(s: ContentStrategy) -> StrategyOut:
    return StrategyOut(
        id=str(s.id),
        brand_id=str(s.brand_id),
        title=s.title,
        period_days=s.period_days,
        status=s.status,
        pillars=s.pillars_json or [],
        channel_cadence=s.channel_cadence_json or {},
        calendar=s.calendar_json or [],
        notes=s.notes,
        created_at=_iso(s.created_at) or "",
        updated_at=_iso(s.updated_at) or "",
        approved_at=_iso(s.approved_at),
    )


def _item_to_out(i: ContentItem) -> ItemOut:
    return ItemOut(
        id=str(i.id),
        brand_id=str(i.brand_id),
        strategy_id=str(i.strategy_id) if i.strategy_id else None,
        title=i.title,
        format=i.format,
        channels=i.channels or [],
        pillar=i.pillar,
        topic=i.topic,
        status=i.status,
        scheduled_for=_iso(i.scheduled_for),
        brief_json=i.brief_json or {},
        variants_json=i.variants_json or {},
        quality_report_json=i.quality_report_json or {},
        review_notes=i.review_notes,
        error_message=i.error_message,
        created_at=_iso(i.created_at) or "",
        updated_at=_iso(i.updated_at) or "",
        approved_at=_iso(i.approved_at),
        published_at=_iso(i.published_at),
        asset_count=len(i.assets or []),
        publish_job_count=len(i.publish_jobs or []),
    )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid ISO datetime: {value}",
        ) from exc


# ── Brands ─────────────────────────────────────────────────────────────────────

@router.get("/brands", response_model=list[BrandOut])
def list_brands(_: str = Depends(require_auth), db: Session = Depends(get_db)) -> list[BrandOut]:
    brands = db.query(ContentBrand).order_by(ContentBrand.created_at.desc()).all()
    return [_brand_to_out(b) for b in brands]


@router.post("/brands", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
def create_brand(
    req: BrandIn,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> BrandOut:
    existing = db.query(ContentBrand).filter(ContentBrand.slug == req.slug).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"brand slug '{req.slug}' already exists")

    brand = ContentBrand(
        slug=req.slug,
        name=req.name,
        venture_tag=req.venture_tag,
        description=req.description,
        voice_profile_json=req.voice_profile_json or {},
        theme_weights=req.theme_weights or {"accessibility": 0.7, "adjacent": 0.3},
        banned_phrases=req.banned_phrases or [],
        channel_cadence=req.channel_cadence or {},
        target_personas=req.target_personas or [],
        auto_strategy_enabled=req.auto_strategy_enabled,
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return _brand_to_out(brand)


@router.patch("/brands/{brand_id}", response_model=BrandOut)
def update_brand(
    brand_id: str,
    req: BrandIn,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> BrandOut:
    brand = db.get(ContentBrand, uuid.UUID(brand_id))
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="brand not found")

    for field_name in (
        "name", "venture_tag", "description", "voice_profile_json", "theme_weights",
        "banned_phrases", "channel_cadence", "target_personas", "auto_strategy_enabled",
    ):
        value = getattr(req, field_name, None)
        if value is not None:
            setattr(brand, field_name, value)
    db.commit()
    db.refresh(brand)
    return _brand_to_out(brand)


@router.delete("/brands/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(
    brand_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    brand = db.get(ContentBrand, uuid.UUID(brand_id))
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="brand not found")
    db.delete(brand)
    db.commit()


@router.post("/brands/seed-echoforge", response_model=BrandOut)
def seed_echoforge_brand(
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> BrandOut:
    """One-shot helper to create the EchoForge Accessibility brand from config seed."""
    from ventures.content_engine.config import ECHOFORGE_ACCESSIBILITY_SEED

    seed = ECHOFORGE_ACCESSIBILITY_SEED
    existing = db.query(ContentBrand).filter(ContentBrand.slug == seed["slug"]).first()
    if existing:
        return _brand_to_out(existing)

    brand = ContentBrand(
        slug=seed["slug"],
        name=seed["name"],
        venture_tag=seed.get("venture_tag"),
        description=seed.get("description"),
        voice_profile_json=seed.get("voice_profile_json") or {},
        theme_weights=seed.get("theme_weights") or {},
        banned_phrases=seed.get("banned_phrases") or [],
        channel_cadence=seed.get("channel_cadence") or {},
        target_personas=seed.get("target_personas") or [],
        auto_strategy_enabled=seed.get("auto_strategy_enabled", False),
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return _brand_to_out(brand)


# ── Strategies ─────────────────────────────────────────────────────────────────

@router.get("/strategies", response_model=list[StrategyOut])
def list_strategies(
    brand_id: str | None = None,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[StrategyOut]:
    q = db.query(ContentStrategy)
    if brand_id:
        q = q.filter(ContentStrategy.brand_id == uuid.UUID(brand_id))
    rows = q.order_by(ContentStrategy.created_at.desc()).all()
    return [_strategy_to_out(s) for s in rows]


@router.post("/strategies", response_model=StrategyOut, status_code=status.HTTP_201_CREATED)
def create_strategy(
    req: StrategyIn,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> StrategyOut:
    """Generate a fresh draft calendar for a brand."""
    from ventures.content_engine.strategy import generate_calendar

    brand = db.get(ContentBrand, uuid.UUID(req.brand_id))
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="brand not found")

    brand_seed = {
        "name":            brand.name,
        "description":     brand.description,
        "target_personas": brand.target_personas or [],
        "theme_weights":   brand.theme_weights or {},
        "channel_cadence": brand.channel_cadence or {},
    }
    cal = generate_calendar(
        brand_seed=brand_seed,
        channel_cadence=req.channel_cadence,
        period_days=req.period_days,
    )

    strategy = ContentStrategy(
        brand_id=brand.id,
        title=req.title or cal["title"],
        period_days=cal["period_days"],
        status="draft",
        pillars_json=cal["pillars"],
        channel_cadence_json=cal["channel_cadence"],
        calendar_json=cal["calendar"],
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return _strategy_to_out(strategy)


@router.patch("/strategies/{strategy_id}", response_model=StrategyOut)
def update_strategy(
    strategy_id: str,
    body: dict[str, Any],
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> StrategyOut:
    strategy = db.get(ContentStrategy, uuid.UUID(strategy_id))
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="strategy not found")

    for key in ("title", "notes"):
        if key in body and body[key] is not None:
            setattr(strategy, key, body[key])
    if "calendar" in body and body["calendar"] is not None:
        strategy.calendar_json = body["calendar"]
    if "pillars" in body and body["pillars"] is not None:
        strategy.pillars_json = body["pillars"]
    if "channel_cadence" in body and body["channel_cadence"] is not None:
        strategy.channel_cadence_json = body["channel_cadence"]
    if "status" in body and body["status"]:
        strategy.status = body["status"]
        if body["status"] == "approved" and not strategy.approved_at:
            strategy.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(strategy)
    return _strategy_to_out(strategy)


@router.post("/strategies/{strategy_id}/approve", response_model=StrategyOut)
def approve_strategy(
    strategy_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> StrategyOut:
    strategy = db.get(ContentStrategy, uuid.UUID(strategy_id))
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="strategy not found")
    strategy.status = "approved"
    strategy.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(strategy)
    return _strategy_to_out(strategy)


# ── Items ──────────────────────────────────────────────────────────────────────

@router.get("/items", response_model=list[ItemOut])
def list_items(
    brand_id: str | None = None,
    status_filter: str | None = None,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    q = db.query(ContentItem)
    if brand_id:
        q = q.filter(ContentItem.brand_id == uuid.UUID(brand_id))
    if status_filter:
        q = q.filter(ContentItem.status == status_filter)
    rows = q.order_by(ContentItem.created_at.desc()).limit(200).all()
    return [_item_to_out(i) for i in rows]


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    req: ItemIn,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ItemOut:
    brand = db.get(ContentBrand, uuid.UUID(req.brand_id))
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="brand not found")

    item = ContentItem(
        brand_id=brand.id,
        strategy_id=uuid.UUID(req.strategy_id) if req.strategy_id else None,
        title=req.title,
        format=req.format,
        channels=req.channels or [],
        pillar=req.pillar,
        topic=req.topic,
        status="brief",
        scheduled_for=_parse_iso(req.scheduled_for),
        brief_json=req.brief_json or {},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_to_out(item)


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(
    item_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ItemOut:
    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    return _item_to_out(item)


@router.patch("/items/{item_id}", response_model=ItemOut)
def patch_item(
    item_id: str,
    req: ItemPatch,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ItemOut:
    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")

    for field_name in ("title", "format", "channels", "pillar", "topic",
                       "variants_json", "review_notes"):
        value = getattr(req, field_name)
        if value is not None:
            setattr(item, field_name, value)
    if req.scheduled_for is not None:
        item.scheduled_for = _parse_iso(req.scheduled_for)
    if req.status:
        item.status = req.status
        if req.status == "approved" and not item.approved_at:
            item.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _item_to_out(item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    db.delete(item)
    db.commit()


@router.post("/items/{item_id}/generate", response_model=ItemOut)
def generate_item(
    item_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ItemOut:
    """Kick off async generation. Returns immediately — UI polls /items/{id}."""
    from aiplatform.webapp.worker import celery_app

    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")

    task = celery_app.send_task("content.run_item_gen", args=[item_id])
    item.status = "generating"
    item.error_message = None
    db.commit()
    db.refresh(item)
    return _item_to_out(item)


class ReviewActionRequest(BaseModel):
    action: str  # approve | revise | reject
    notes: str | None = None


@router.post("/items/{item_id}/review", response_model=ItemOut)
def review_item(
    item_id: str,
    req: ReviewActionRequest,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ItemOut:
    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    if item.status not in {"review_pending", "revising"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"item status is '{item.status}', expected 'review_pending' or 'revising'",
        )

    if req.action == "approve":
        item.status = "approved"
        item.approved_at = datetime.now(timezone.utc)
    elif req.action == "revise":
        item.status = "revising"
        # Re-kick generation so the worker re-runs with new context.
        from aiplatform.webapp.worker import celery_app
        celery_app.send_task("content.run_item_gen", args=[item_id])
    elif req.action == "reject":
        item.status = "cancelled"
    else:
        raise HTTPException(status_code=400, detail=f"unknown action '{req.action}'")

    if req.notes:
        item.review_notes = req.notes
    db.commit()
    db.refresh(item)
    return _item_to_out(item)


class ScheduleRequest(BaseModel):
    scheduled_for: str  # ISO8601
    channels: list[str] | None = None


@router.post("/items/{item_id}/schedule", response_model=ItemOut)
def schedule_item(
    item_id: str,
    req: ScheduleRequest,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ItemOut:
    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    if item.status not in {"approved", "scheduled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"item must be 'approved' before scheduling (got '{item.status}')",
        )
    when = _parse_iso(req.scheduled_for)
    if when is None:
        raise HTTPException(status_code=400, detail="scheduled_for is required")
    item.scheduled_for = when
    if req.channels:
        item.channels = req.channels
    item.status = "scheduled"
    db.commit()
    db.refresh(item)
    return _item_to_out(item)


@router.post("/items/{item_id}/unschedule", response_model=ItemOut)
def unschedule_item(
    item_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ItemOut:
    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    if item.status != "scheduled":
        raise HTTPException(status_code=409, detail=f"item is not scheduled (status '{item.status}')")
    item.scheduled_for = None
    item.status = "approved"
    db.commit()
    db.refresh(item)
    return _item_to_out(item)


@router.post("/items/{item_id}/publish-now", response_model=ItemOut)
def publish_now(
    item_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ItemOut:
    """Force-publish an approved item immediately (skip scheduler)."""
    from aiplatform.webapp.worker import celery_app

    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    if item.status not in {"approved", "scheduled"}:
        raise HTTPException(status_code=409, detail=f"item must be approved (got '{item.status}')")
    celery_app.send_task("content.run_publish_item", args=[item_id])
    return _item_to_out(item)


# ── Publish jobs ───────────────────────────────────────────────────────────────

@router.get("/publish-jobs", response_model=list[PublishJobOut])
def list_publish_jobs(
    item_id: str | None = None,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[PublishJobOut]:
    q = db.query(PublishJob)
    if item_id:
        q = q.filter(PublishJob.item_id == uuid.UUID(item_id))
    rows = q.order_by(PublishJob.created_at.desc()).limit(200).all()
    return [
        PublishJobOut(
            id=str(r.id),
            item_id=str(r.item_id),
            channel=r.channel,
            status=r.status,
            external_post_id=r.external_post_id,
            external_url=r.external_url,
            deep_link=r.deep_link,
            error_message=r.error_message,
            created_at=_iso(r.created_at) or "",
            published_at=_iso(r.published_at),
        )
        for r in rows
    ]


class ConfirmSentRequest(BaseModel):
    external_url: str | None = None
    external_post_id: str | None = None


@router.post("/publish-jobs/{job_id}/confirm-sent", response_model=PublishJobOut)
def confirm_publish_sent(
    job_id: str,
    req: ConfirmSentRequest,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> PublishJobOut:
    """Operator confirms an assisted-send manual publish."""
    pj = db.get(PublishJob, uuid.UUID(job_id))
    if not pj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="publish job not found")
    if pj.status != "awaiting_manual":
        raise HTTPException(status_code=409, detail=f"job is not awaiting manual confirm ('{pj.status}')")
    pj.status = "success"
    pj.published_at = datetime.now(timezone.utc)
    if req.external_url:
        pj.external_url = req.external_url
    if req.external_post_id:
        pj.external_post_id = req.external_post_id

    # If at least one channel for this item is now successful, mark item published.
    item = db.get(ContentItem, pj.item_id)
    if item and item.status in {"publishing", "scheduled", "approved"}:
        item.status = "published"
        item.published_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(pj)
    return PublishJobOut(
        id=str(pj.id),
        item_id=str(pj.item_id),
        channel=pj.channel,
        status=pj.status,
        external_post_id=pj.external_post_id,
        external_url=pj.external_url,
        deep_link=pj.deep_link,
        error_message=pj.error_message,
        created_at=_iso(pj.created_at) or "",
        published_at=_iso(pj.published_at),
    )


# ── Social accounts ────────────────────────────────────────────────────────────

@router.get("/social-accounts", response_model=list[SocialAccountOut])
def list_social_accounts(
    brand_id: str | None = None,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[SocialAccountOut]:
    q = db.query(SocialAccount)
    if brand_id:
        q = q.filter(SocialAccount.brand_id == uuid.UUID(brand_id))
    rows = q.order_by(SocialAccount.created_at.desc()).all()
    return [
        SocialAccountOut(
            id=str(a.id),
            brand_id=str(a.brand_id),
            platform=a.platform,
            account_id=a.account_id,
            account_name=a.account_name,
            has_token=bool(a.access_token),
            expires_at=_iso(a.expires_at),
            scopes=a.scopes or [],
            enabled=a.enabled,
            created_at=_iso(a.created_at) or "",
        )
        for a in rows
    ]


@router.post("/social-accounts", response_model=SocialAccountOut, status_code=status.HTTP_201_CREATED)
def create_social_account(
    req: SocialAccountIn,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> SocialAccountOut:
    brand = db.get(ContentBrand, uuid.UUID(req.brand_id))
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="brand not found")
    acct = SocialAccount(
        brand_id=brand.id,
        platform=req.platform,
        account_id=req.account_id,
        account_name=req.account_name,
        access_token=req.access_token,
        refresh_token=req.refresh_token,
        expires_at=_parse_iso(req.expires_at),
        scopes=req.scopes or [],
        enabled=req.enabled,
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    return SocialAccountOut(
        id=str(acct.id),
        brand_id=str(acct.brand_id),
        platform=acct.platform,
        account_id=acct.account_id,
        account_name=acct.account_name,
        has_token=bool(acct.access_token),
        expires_at=_iso(acct.expires_at),
        scopes=acct.scopes or [],
        enabled=acct.enabled,
        created_at=_iso(acct.created_at) or "",
    )


@router.delete("/social-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_social_account(
    account_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    acct = db.get(SocialAccount, uuid.UUID(account_id))
    if not acct:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    db.delete(acct)
    db.commit()
