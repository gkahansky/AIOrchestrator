"""
Pydantic schemas for request/response validation across all API routers.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Shared ─────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    db: bool
    redis: bool
    version: str = "1.0.0"


# ── Jobs ───────────────────────────────────────────────────────────────────────

class JobSummary(BaseModel):
    id: uuid.UUID
    venture: str
    status: str
    phase_current: int | None
    phase_total: int | None
    environment: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobDetail(JobSummary):
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    error_message: str | None
    celery_task_id: str | None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: list[JobSummary]
    total: int
    page: int
    page_size: int


class JobActionResponse(BaseModel):
    job_id: uuid.UUID
    action: str
    status: str


# ── Dashboard ──────────────────────────────────────────────────────────────────

class VentureStats(BaseModel):
    venture: str
    total_jobs: int
    pending: int
    in_progress: int
    completed: int
    failed: int
    pending_review: int


class DashboardResponse(BaseModel):
    ventures: list[VentureStats]
    total_cost_usd_month: float
    total_revenue_usd_month: float
    db_ok: bool
    redis_ok: bool


# ── Finance ────────────────────────────────────────────────────────────────────

class CostSummary(BaseModel):
    tool_id: str
    capability: str
    total_cost_usd: float
    call_count: int


class RevenueSummary(BaseModel):
    venture: str
    source: str
    total_amount_usd: float
    total_fee_usd: float
    total_net_usd: float
    order_count: int


class FinanceResponse(BaseModel):
    costs: list[CostSummary]
    revenues: list[RevenueSummary]
    net_usd: float
    period: str  # e.g. "2026-03"


# ── Venture — Etsy ─────────────────────────────────────────────────────────────

class EtsyRunPhaseRequest(BaseModel):
    phase: int = Field(..., ge=1, le=7)
    params: dict[str, Any] = Field(default_factory=dict)


class EtsyPhaseResponse(BaseModel):
    celery_task_id: str
    phase: int
    status: str = "queued"


# ── Venture — Marketing Audit ──────────────────────────────────────────────────

class AuditOrderRequest(BaseModel):
    url: str
    tier: str = Field("full", pattern="^(snapshot|full|premium)$")
    report_type: str = Field("both", pattern="^(both|full|sample)$")
    client_email: str | None = None
    order_id: str | None = None


class AuditOrderResponse(BaseModel):
    order_id: str
    celery_task_id: str
    status: str = "queued"


class AuditApproveRequest(BaseModel):
    order_id: str
    action: str = Field(..., pattern="^(approve|reject|revision)$")
    notes: str | None = None


# ── Venture — Content Studio ───────────────────────────────────────────────────

class PodcastOrderRequest(BaseModel):
    audio_url: str
    tier: str = Field("standard", pattern="^(starter|standard|premium)$")
    show_name: str | None = None
    client_email: str | None = None
    order_id: str | None = None


class PodcastOrderResponse(BaseModel):
    order_id: str
    celery_task_id: str
    status: str = "queued"


class PodcastApproveRequest(BaseModel):
    order_id: str
    action: str = Field(..., pattern="^(approve|reject|revision)$")
    notes: str | None = None


# ── Jobs — approve / reject ─────────────────────────────────────────────────────

class JobApproveRequest(BaseModel):
    notes: str | None = None


class JobRejectRequest(BaseModel):
    reason: str | None = None


# ── Venture — Etsy listings ─────────────────────────────────────────────────────

class EtsyListing(BaseModel):
    listing_id: str | None
    title: str | None
    status: str
    drive_folder: str | None
    tags: list[str] = Field(default_factory=list)
    price_usd: float | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class EtsyListingsResponse(BaseModel):
    items: list[EtsyListing]
    total: int


# ── Platform settings ─────────────────────────────────────────────────────────

class SettingsKeyResponse(BaseModel):
    service: str
    masked_key: str          # last 6 chars only, e.g. "...abc123"
    is_set: bool
    last_tested: datetime | None = None
    test_ok: bool | None = None


class SettingsKeysListResponse(BaseModel):
    keys: list[SettingsKeyResponse]


class SettingsKeyUpdate(BaseModel):
    key: str = Field(..., min_length=1)


class SettingsKeyTestResponse(BaseModel):
    service: str
    ok: bool
    detail: str


class ToolSettingUpdate(BaseModel):
    active: bool


class ToolSettingResponse(BaseModel):
    capability: str
    tool_id: str
    tier: str
    cost_per_call: float
    active: bool
    note: str | None = None
