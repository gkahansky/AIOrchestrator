"""
SQLAlchemy ORM models for AI-Infra platform.

Replaces per-order JSON files (output/*/order.json) with a queryable,
durable database that works across processes and survives cloud restarts.

Tables:
  jobs          — top-level record per pipeline run (one per order)
  phase_events  — append-only audit log of every state transition
  cost_events   — every API call cost (replaces log_cost() stub)
  revenue_events — every sale/delivery (replaces log_revenue() stub)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Enums ──────────────────────────────────────────────────────────────────────

VENTURE_ENUM = Enum(
    "etsy", "marketing_audit", "content_studio", "accessibility_audit",
    name="venture_enum",
)

ENVIRONMENT_ENUM = Enum(
    "production", "staging",
    name="environment_enum",
)

PHASE_EVENT_TYPE_ENUM = Enum(
    "started", "completed", "failed", "paused", "resumed",
    name="phase_event_type_enum",
)


# ── Jobs ───────────────────────────────────────────────────────────────────────

class Job(Base):
    """
    Top-level record for every pipeline run.

    Replaces every output/{venture}/{order_id}/order.json file.
    The status field mirrors each venture pipeline's state machine exactly.

    Venture status machines:
      etsy:            pending -> generating -> generated -> packaged ->
                       review_pending -> approved -> rejected -> draft_live -> published
      marketing_audit: pending -> scraping -> scraped -> auditing -> audited ->
                       generating_report -> report_ready -> review_pending ->
                       approved -> delivering -> delivered -> failed
      content_studio:  pending -> transcribing -> transcribed -> generating ->
                       generated -> packaging -> addons_pending -> packaged ->
                       review_pending -> approved -> delivering -> delivered -> failed
    """

    __tablename__ = "jobs"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venture        = Column(VENTURE_ENUM, nullable=False, index=True)
    status         = Column(String(50), nullable=False, default="pending", index=True)
    phase_current  = Column(Integer, nullable=True)
    phase_total    = Column(Integer, nullable=True)

    # Venture-specific order fields at creation time.
    # etsy:           {slug, theme, quality_tier, ...}
    # marketing_audit:{url, tier, brand_name, competitor_urls, client_email, ...}
    # content_studio: {audio_path, show_name, episode_title, tier, add_ons, ...}
    input_data  = Column(JSONB, nullable=False, default=dict)

    # Accumulated outputs written by each phase.
    # Drive links, pdf_path, listing_id, gdoc_url, etc.
    output_data = Column(JSONB, nullable=False, default=dict)

    error_message  = Column(Text, nullable=True)
    celery_task_id = Column(String(100), nullable=True)
    environment    = Column(ENVIRONMENT_ENUM, nullable=False, default="production")

    created_at   = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))
    updated_at   = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
    started_at   = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    phase_events   = relationship("PhaseEvent",   back_populates="job",
                                  cascade="all, delete-orphan", order_by="PhaseEvent.created_at")
    cost_events    = relationship("CostEvent",    back_populates="job",
                                  cascade="all, delete-orphan")
    revenue_events = relationship("RevenueEvent", back_populates="job",
                                  cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job {self.id} venture={self.venture} status={self.status}>"

    def to_dict(self):
        return {
            "id":            str(self.id),
            "venture":       self.venture,
            "status":        self.status,
            "phase_current": self.phase_current,
            "phase_total":   self.phase_total,
            "input_data":    self.input_data,
            "output_data":   self.output_data,
            "error_message": self.error_message,
            "environment":   self.environment,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
            "updated_at":    self.updated_at.isoformat() if self.updated_at else None,
            "started_at":    self.started_at.isoformat() if self.started_at else None,
            "completed_at":  self.completed_at.isoformat() if self.completed_at else None,
        }


# ── Phase Events ───────────────────────────────────────────────────────────────

class PhaseEvent(Base):
    """
    Append-only audit log of every state transition within a job.

    Never updated — only inserted. Provides a full timeline of any job
    and lets you calculate per-phase duration and cost after the fact.
    """

    __tablename__ = "phase_events"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id     = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    phase      = Column(Integer, nullable=True)
    event_type = Column(PHASE_EVENT_TYPE_ENUM, nullable=False)

    # Phase-specific payload: cost_usd, drive_link, file_count, listing_id, etc.
    details    = Column(JSONB, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    job = relationship("Job", back_populates="phase_events")

    def __repr__(self):
        return f"<PhaseEvent job={self.job_id} phase={self.phase} type={self.event_type}>"


# ── Cost Events ────────────────────────────────────────────────────────────────

class CostEvent(Base):
    """
    Every external API call with a cost.

    Replaces the stub log_cost() function in skills/finance/log_cost.py.
    job_id is nullable for platform-level costs not tied to a specific job
    (e.g. SerpAPI trend research, ClickUp sync calls).
    """

    __tablename__ = "cost_events"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id     = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"),
                        nullable=True, index=True)
    venture    = Column(String(50), nullable=True, index=True)
    capability = Column(String(100), nullable=False)  # e.g. "image-generation"
    tool_id    = Column(String(100), nullable=False)  # e.g. "gemini-imagen"
    cost_usd   = Column(Numeric(10, 6), nullable=False)
    tokens_in  = Column(Integer, nullable=True)   # for LLM calls
    tokens_out = Column(Integer, nullable=True)   # for LLM calls

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    job = relationship("Job", back_populates="cost_events")

    def __repr__(self):
        return (f"<CostEvent job={self.job_id} tool={self.tool_id} "
                f"cost=${self.cost_usd}>")


# ── Revenue Events ─────────────────────────────────────────────────────────────

class RevenueEvent(Base):
    """
    Every sale or delivery.

    Replaces the stub log_revenue() function in skills/finance/log_revenue.py.
    """

    __tablename__ = "revenue_events"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id      = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"),
                         nullable=True, index=True)
    venture     = Column(String(50), nullable=False, index=True)
    source      = Column(String(100), nullable=False)  # "fiverr", "etsy", "direct"
    amount_usd  = Column(Numeric(10, 2), nullable=False)
    fee_usd     = Column(Numeric(10, 2), nullable=False, default=0)
    net_usd     = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=True)

    created_at  = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))

    job = relationship("Job", back_populates="revenue_events")

    def __repr__(self):
        return (f"<RevenueEvent job={self.job_id} venture={self.venture} "
                f"net=${self.net_usd}>")

# -- Advisory & Roadmap --------------------------------------------------------

from sqlalchemy import SmallInteger

ADVISOR_ID_ENUM = Enum(
    "architect", "marketing", "product", "executive",
    name="advisor_id_enum",
)

PROPOSAL_STATUS_ENUM = Enum(
    "pending_review", "approved", "rejected", "archived",
    name="proposal_status_enum",
)

ROADMAP_STATUS_ENUM = Enum(
    "backlog", "in_progress", "completed",
    name="roadmap_status_enum",
)

class AdvisoryProposal(Base):
    """
    AI-generated proposals for venture strategy, optimization, or platform codebase.
    """
    __tablename__ = "advisory_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advisor_id = Column(ADVISOR_ID_ENUM, nullable=False, index=True)
    category = Column(String(255), nullable=False)
    content = Column(JSONB, nullable=False)
    status = Column(PROPOSAL_STATUS_ENUM, nullable=False, default="pending_review", index=True)
    priority = Column(SmallInteger, nullable=False, default=3)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    job = relationship("Job")

class Roadmap(Base):
    """
    Actionable tasks approved from Advisory Proposals or created manually.
    """
    __tablename__ = "roadmap"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    effort_score = Column(SmallInteger, nullable=True) # 1-10
    margin_potential = Column(SmallInteger, nullable=True) # 1-10
    status = Column(ROADMAP_STATUS_ENUM, nullable=False, default="backlog", index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class AccessibilityAudit(Base):
    """
    Accessibility Audit Module (AAM) table storing raw Axe results and structured roadmap data.
    """
    __tablename__ = "accessibility_audits"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    target_url = Column(String(2048), nullable=False)
    raw_axe_results = Column(JSONB, nullable=True)
    roadmap_data = Column(JSONB, nullable=True)
    compliance_score = Column(Integer, nullable=True)
    manual_override_notes = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="Queued") # Queued | Scanning | Analyzing | Completed

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    job = relationship("Job")
