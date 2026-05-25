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
    Float,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
    Boolean,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Enums ──────────────────────────────────────────────────────

VENTURE_ENUM = Enum(
    "etsy", "marketing_audit", "content_studio", "accessibility_audit", "security_audit",
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


# ── Jobs ──────────────────────────────────────────────────────

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


# ── Phase Events ────────────────────────────────────────────────────

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


# ── Cost Events ──────────────────────────────────────────────────────

class CostEvent(Base):
    """
    Every external API call with a cost.

    Replaces the stub log_cost() function in skills/finance/log_cost.py.
    job_id is nullable for platform-level costs not tied to a specific job
    (e.g. SerpAPI trend research, Jira sync calls).
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


# ── Revenue Events ─────────────────────────────────────────────────────

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


class RoadmapFeature(Base):
    """
    Available product features used to tag roadmap items.
    """
    __tablename__ = "roadmap_features"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    name       = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))


class Roadmap(Base):
    """
    Actionable tasks approved from Advisory Proposals or created manually.

    Status values:
      not_started         → Product Backlog
      in_progress         → Work in Progress
      in_testing          → Work in Progress
      ready_for_deployment → Work in Progress
      done                → cleared (surfaced via Recently Done query)
    """
    __tablename__ = "roadmap"

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    title            = Column(String(500), nullable=False)
    description      = Column(Text, nullable=False, default="")
    effort_score     = Column(SmallInteger, nullable=True)
    margin_potential = Column(SmallInteger, nullable=True)

    # "New feature" | "Bug" | "Feature enhancement" | "Task"
    item_type  = Column(String(50), nullable=True, default="New feature")
    owner      = Column(String(255), nullable=True)  # email of the assigned owner
    feature_id = Column(BigInteger, ForeignKey("roadmap_features.id", ondelete="SET NULL"), nullable=True)

    # not_started | in_progress | in_testing | ready_for_deployment | done
    status     = Column(String(50), nullable=False, default="not_started", index=True)

    sort_order   = Column(Integer, nullable=False, default=0)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at   = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))

    feature = relationship("RoadmapFeature")

# ── Outreach ──────────────────────────────────────────────────────────

LEAD_STATUS_ENUM = Enum(
    "new", "email_sent", "opened", "replied", "converted", "not_interested",
    name="lead_status_enum",
)

CAMPAIGN_STATUS_ENUM = Enum(
    "draft", "active", "paused", "completed",
    name="campaign_status_enum",
)

OUTREACH_VENTURE_ENUM = Enum(
    "marketing_audit", "content_studio", "accessibility_audit",
    name="outreach_venture_enum",
)


class Lead(Base):
    """
    A potential customer found via automated or manual research.
    Tracks contact info, discovery source, and outreach status.

    At least one of `email` or `platform_username` must be non-null —
    enforced in the router before insert. A lead with no reachable identifier
    is silently discarded during find-leads.
    """
    __tablename__ = "leads"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venture           = Column(String(50), nullable=False, index=True)
    source_channel    = Column(String(100), nullable=False)   # reddit, fiverr, linkedin, web_search …
    source_url        = Column(String(2048), nullable=True)   # URL of the post / profile where found
    name              = Column(String(255), nullable=True)
    email             = Column(String(255), nullable=True, index=True)
    platform_username = Column(String(255), nullable=True)    # e.g. "u/johndoe", "fiverr:john_doe"
    website_url       = Column(String(2048), nullable=True)   # their website (audit leads)
    company           = Column(String(255), nullable=True)
    notes             = Column(Text, nullable=True)           # AI-extracted context about them
    status            = Column(String(50), nullable=False, default="new", index=True)
    campaign_id       = Column(UUID(as_uuid=True), ForeignKey("outreach_campaigns.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    context        = Column(Text, nullable=True)          # raw post/query text that surfaced this lead
    matched_persona = Column(String(100), nullable=True)  # which persona name this lead matches
    intent_score   = Column(Integer, nullable=True)       # 0–100 intent signal strength from Claude Haiku

    campaign = relationship("OutreachCampaign", back_populates="leads")
    sends    = relationship("OutreachSend", back_populates="lead", cascade="all, delete-orphan")
    drafts   = relationship("LeadDraft", back_populates="lead", cascade="all, delete-orphan")


class OutreachCampaign(Base):
    """
    A named outreach campaign targeting a specific venture's audience.
    Contains multiple A/B message variants.

    `platform` controls how leads are found and how messages are composed:
      email    — cold email via Resend (default, existing behaviour)
      fiverr   — respond to buyer requests / approach sellers on Fiverr
      reddit   — comment replies on relevant subreddit posts
      linkedin — connection messages or post comments
      facebook — group post comments or DMs
      instagram — post/reel comments or DMs
    Additional platforms can be added without schema changes.
    """
    __tablename__ = "outreach_campaigns"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venture  = Column(String(50), nullable=False, index=True)
    name     = Column(String(255), nullable=False)
    status   = Column(String(50), nullable=False, default="draft", index=True)
    goal     = Column(Text, nullable=True)
    # Platform this campaign targets — drives compose style and send mechanism
    platform = Column(String(50), nullable=False, default="email")

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Persona-driven search fields
    personas                 = Column(JSONB, nullable=True)            # [{name, description}] up to 5
    target_prompt            = Column(Text, nullable=True)             # product/audience context for AI
    user_search_instructions = Column(Text, nullable=True)             # optional user-supplied search guidance
    auto_search_enabled      = Column(Boolean, nullable=False, default=False, server_default="false")
    search_interval_hours    = Column(Integer, nullable=True)          # 6 | 24 | 168 | …
    next_search_at           = Column(DateTime(timezone=True), nullable=True)
    last_search_at           = Column(DateTime(timezone=True), nullable=True)

    # Test mode flags — independent; both default False on production campaigns
    use_mock_leads = Column(Boolean, nullable=False, default=False, server_default="false")
    dry_run        = Column(Boolean, nullable=False, default=False, server_default="false")

    leads     = relationship("Lead", back_populates="campaign")
    templates = relationship("OutreachTemplate", back_populates="campaign", cascade="all, delete-orphan")
    sends     = relationship("OutreachSend", back_populates="campaign", cascade="all, delete-orphan")
    sources   = relationship("CampaignSource", back_populates="campaign", cascade="all, delete-orphan",
                             order_by="CampaignSource.created_at")
    drafts    = relationship("LeadDraft", back_populates="campaign", cascade="all, delete-orphan")
    # Many-to-many links to the reusable persona library. The legacy `personas`
    # JSONB column above is kept as a fallback during the cut-over and is read
    # via _campaign_personas() only when no links exist.
    persona_links = relationship("CampaignPersona", back_populates="campaign",
                                 cascade="all, delete-orphan")


class OutreachTemplate(Base):
    """
    A message variant within a campaign (A/B/C testing).
    Platform-agnostic: email uses subject + body_html + body_text;
    all other platforms (Reddit, Fiverr, LinkedIn, Instagram, Facebook …)
    use only `message_body` (plain text / markdown).

    Column semantics by platform:
      email     — subject (required), body_html (rendered), body_text (plain fallback)
      reddit    — message_body only (markdown OK, ~10k char limit)
      fiverr    — message_body only (plain text, ~2k chars)
      linkedin  — message_body only (plain text, 300 chars for connection, 1250 InMail)
      facebook  — message_body only (plain text / markdown)
      instagram — message_body only (plain text, 2200 chars)
    """
    __tablename__ = "outreach_templates"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id   = Column(UUID(as_uuid=True), ForeignKey("outreach_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    variant       = Column(String(10), nullable=False)    # "A", "B", "C"
    # Email-specific fields (null for non-email platforms)
    subject       = Column(String(500), nullable=True)
    body_html     = Column(Text, nullable=True)
    # Universal content field — plain text body for all platforms
    body_text     = Column(Text, nullable=True)
    tone_notes    = Column(Text, nullable=True)
    sends_count   = Column(Integer, nullable=False, default=0)
    opens_count   = Column(Integer, nullable=False, default=0)
    replies_count = Column(Integer, nullable=False, default=0)
    approved      = Column(String(10), nullable=False, default="pending")  # pending, approved, rejected

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    campaign = relationship("OutreachCampaign", back_populates="templates")
    sends    = relationship("OutreachSend", back_populates="template", cascade="all, delete-orphan")


class OutreachSend(Base):
    """
    A record of one email sent to one lead using one template variant.
    Tracks open and reply events for A/B analysis.
    """
    __tablename__ = "outreach_sends"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id     = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    # Nullable: draft-based (persona) sends have no template; only legacy A/B sends set this.
    template_id = Column(UUID(as_uuid=True), ForeignKey("outreach_templates.id", ondelete="CASCADE"), nullable=True, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("outreach_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id  = Column(String(255), nullable=True)   # Resend message ID for tracking
    status      = Column(String(50), nullable=False, default="sent")  # sent, opened, replied, bounced

    sent_at     = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    opened_at   = Column(DateTime(timezone=True), nullable=True)
    replied_at  = Column(DateTime(timezone=True), nullable=True)

    lead     = relationship("Lead", back_populates="sends")
    template = relationship("OutreachTemplate", back_populates="sends")
    campaign = relationship("OutreachCampaign", back_populates="sends")


class Contact(Base):
    """
    Unified CRM contact list across all ventures.

    Retention rules:
      - status in (approached, inquired): auto-expire 12 months from last_activity_at
      - status = purchased: keep forever
      - status = unsubscribed: keep forever (to prevent re-contacting)

    Cross-venture spam guard: before sending any email, look up email here.
    If unsubscribed — never send. If recently approached — respect cooldown.
    """
    __tablename__ = "contacts"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # email is nullable — contacts found via social platforms may not have one.
    # At least one of email or usernames must be non-null (enforced in router).
    email       = Column(String(255), nullable=True, unique=True, index=True)
    # usernames: platform → handle mapping, e.g. {"reddit": "u/johndoe", "fiverr": "john_doe"}
    usernames   = Column(JSONB, nullable=True)
    name        = Column(String(255), nullable=True)
    phone       = Column(String(50), nullable=True)
    address     = Column(Text, nullable=True)
    company     = Column(String(255), nullable=True)
    website_url = Column(String(2048), nullable=True)

    # approached | inquired | purchased | unsubscribed
    status      = Column(String(50), nullable=False, default="approached", index=True)
    is_test_user = Column(Boolean, nullable=False, default=False, server_default="false")

    # List of venture slugs this contact was approached from, e.g. ["marketing_audit"]
    ventures_approached  = Column(JSONB, nullable=False, default=list)
    # {venture_slug: "what they were shown / interested in"}
    features_of_interest = Column(JSONB, nullable=True)

    last_activity_at  = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    purchased_at      = Column(DateTime(timezone=True), nullable=True)
    unsubscribed_at   = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


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

class ContactMessage(Base):
    """
    Email logs sent to a unified CRM contact.
    """
    __tablename__ = "contact_messages"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id  = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    venture     = Column(String(50), nullable=False, index=True) # marketing_audit, podcast_notes, accessibility
    message_type = Column(String(50), nullable=False, index=True) # sample, nurture, outreach, delivery
    subject     = Column(String(500), nullable=False)
    body_snippet = Column(Text, nullable=True)
    message_id  = Column(String(255), nullable=True) # Resend ID

    sent_at     = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    contact     = relationship("Contact", backref="messages")


# ── Campaign Sources ─────────────────────────────────────────────────────

class CampaignSource(Base):
    """
    A single search source attached to an outreach campaign.

    One campaign has many sources — each represents one platform/venue to watch.
    platform controls which handler runs; keywords drives what to search;
    config holds platform-specific extras (e.g. subreddits list, group_urls).

    Examples:
      reddit:       config={subreddits:["smallbusiness","entrepreneur"]}, keywords=[...]
      facebook:     config={group_urls:["facebook.com/groups/abc"]},      keywords=[...]
      google:       config={},                                            keywords=[...]
      hackernews:   config={post_type:"ask"},                             keywords=[...]
      linkedin:     config={use_apify:true},                              keywords=[...]
    """
    __tablename__ = "campaign_sources"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("outreach_campaigns.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    platform    = Column(String(50), nullable=False)    # reddit | google | linkedin | facebook | …
    name        = Column(String(255), nullable=False)   # user label, e.g. "r/smallbusiness"
    keywords    = Column(JSONB, nullable=False, default=list)   # list of search terms / queries
    config      = Column(JSONB, nullable=True)          # platform-specific extras
    enabled     = Column(Boolean, nullable=False, default=True, server_default="true")

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    campaign = relationship("OutreachCampaign", back_populates="sources")


# ── Lead Drafts ───────────────────────────────────────────────────────

class LeadDraft(Base):
    """
    A personalized outreach message drafted by Claude for one specific lead.

    Replaces the A/B template model for persona-driven campaigns: instead of
    one template sent to everyone, each lead gets one draft written specifically
    for them based on their post context and matched persona.

    Status flow: pending_review → approved | rejected → sent
    """
    __tablename__ = "lead_drafts"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id      = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    campaign_id  = Column(UUID(as_uuid=True), ForeignKey("outreach_campaigns.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    subject      = Column(String(500), nullable=True)   # email platform only
    message_body = Column(Text, nullable=False)
    context_used = Column(Text, nullable=True)          # snapshot of lead context at compose time
    status       = Column(String(20), nullable=False, default="pending_review", index=True)
    # pending_review | approved | rejected | awaiting_send | sent | test_sent
    # awaiting_send: dispatched to an assisted (non-email) platform; the operator
    # must send manually in the native app and then confirm, which finalises it.

    generated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at  = Column(DateTime(timezone=True), nullable=True)
    sent_at      = Column(DateTime(timezone=True), nullable=True)
    send_record_id = Column(UUID(as_uuid=True), ForeignKey("outreach_sends.id", ondelete="SET NULL"),
                            nullable=True)
    # Assisted-send: the deep link the operator opens to send in the native app,
    # and the platform it targets. Populated when status = awaiting_send.
    send_deep_link = Column(String(2048), nullable=True)
    send_platform  = Column(String(50), nullable=True)

    lead     = relationship("Lead", back_populates="drafts")
    campaign = relationship("OutreachCampaign", back_populates="drafts")


# ── Reusable persona library ──────────────────────────────────────────

class Persona(Base):
    """
    A reusable audience persona. Personas live in a per-venture library and are
    linked to campaigns many-to-many via CampaignPersona. Editing a persona is a
    live reference: every campaign linked to it sees the change.
    """
    __tablename__ = "personas"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venture     = Column(String(50), nullable=True, index=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    campaign_links = relationship("CampaignPersona", back_populates="persona",
                                  cascade="all, delete-orphan")


class CampaignPersona(Base):
    """Join row linking one campaign to one reusable persona (many-to-many)."""
    __tablename__ = "campaign_personas"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("outreach_campaigns.id", ondelete="CASCADE"),
                         primary_key=True)
    persona_id  = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"),
                         primary_key=True, index=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    campaign = relationship("OutreachCampaign", back_populates="persona_links")
    persona  = relationship("Persona", back_populates="campaign_links")


# ── Security Audit ─────────────────────────────────────────────────────

class SecurityAudit(Base):
    """
    Security Audit venture — tracks scan state, findings, and scope verification.

    State machine:
      pending → scope_pending → scope_verified → scanning → scan_complete →
      correlating → report_ready → review_pending → approved → delivering →
      delivered → failed
    """
    __tablename__ = "security_audits"

    audit_id   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id     = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"),
                        nullable=True, index=True)
    target_url   = Column(String(2048), nullable=False)
    target_domain = Column(String(255), nullable=False, index=True)

    # Service tier: starter | professional | agency
    tier       = Column(String(50), nullable=False, default="starter")

    # Scope verification
    scope_token         = Column(String(100), nullable=True)   # DNS TXT token to place
    scope_verified      = Column(Boolean, nullable=False, default=False)
    scope_verified_at   = Column(DateTime(timezone=True), nullable=True)
    scope_method        = Column(String(50), nullable=True)    # "dns_txt" | "file" | "manual"

    # Authenticated testing (Professional + Agency)
    auth_username  = Column(String(255), nullable=True)
    auth_password  = Column(String(255), nullable=True)  # encrypted at rest in pipeline
    auth_login_url = Column(String(2048), nullable=True)

    # Phase outputs — raw findings per phase stored as JSONB
    phase1_recon_data    = Column(JSONB, nullable=True)   # passive OSINT results
    phase2_surface_data  = Column(JSONB, nullable=True)   # surface mapping results
    phase3_vuln_data     = Column(JSONB, nullable=True)   # vulnerability scan results
    phase4_exploit_data  = Column(JSONB, nullable=True)   # confirmed PoC results (future)
    phase5_auth_data     = Column(JSONB, nullable=True)   # authenticated scan results (future)

    # Aggregated findings after Claude correlation
    findings_json  = Column(JSONB, nullable=True)   # [{severity, category, title, desc, cvss, fix}]
    attack_chains  = Column(JSONB, nullable=True)   # [{chain_title, steps, risk}]
    risk_score     = Column(Integer, nullable=True) # 0-100 overall risk

    # Reviewer notes
    reviewer_notes = Column(Text, nullable=True)

    # Retest fields — populated when this record is a retest of a previous audit
    retest_of_audit_id  = Column(UUID(as_uuid=True), nullable=True)  # original audit UUID
    retest_finding_ids  = Column(JSONB, nullable=True)               # ["F-001", "F-003"]
    retest_requested_at = Column(DateTime(timezone=True), nullable=True)

    # Pipeline status
    status = Column(String(50), nullable=False, default="pending", index=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    job = relationship("Job")


# ── Market Research ──────────────────────────────────────────────────────

class MarketResearch(Base):
    """
    Market Research venture — parallel multi-LLM research with RAG and critic review.

    State machine:
      pending → optimizing → researching → merging → reflecting → generating_pdf →
      pdf_ready → delivering → delivered → failed
    """
    __tablename__ = "market_research"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic         = Column(Text, nullable=False)
    title         = Column(String(500), nullable=True)   # AI-generated short title
    status        = Column(String(50), nullable=False, default="pending", index=True)

    selected_llms = Column(JSONB, nullable=False, default=list)
    critic_llm    = Column(String(50), nullable=False, default="grok")
    rag_doc_ids   = Column(JSONB, nullable=True)

    section_config    = Column(JSONB, nullable=True)   # v3: {version:3, system_prompt, sections:[{id,name,enabled,prompt,locked}]}
    optimized_prompts = Column(JSONB, nullable=True)   # v2: {version:2, packages:[...]} / v1: {llm_id: prompt}
    research_results  = Column(JSONB, nullable=True)   # v3: {version:3, sections:{id:{status,draft,...}}} / v2/v1: legacy

    # Productization fields (Phase 1+)
    report_config = Column(JSONB, nullable=True)       # {output_depth, writing_style, framework, citation_format}
    sector        = Column(String(100), nullable=True, default="business_intelligence")  # sector key from registry
    merged_report     = Column(Text, nullable=True)
    critic_feedback   = Column(Text, nullable=True)
    final_report      = Column(Text, nullable=True)

    pdf_path       = Column(String(2048), nullable=True)
    drive_link     = Column(String(2048), nullable=True)
    client_email   = Column(String(255), nullable=True)
    error          = Column(Text, nullable=True)
    celery_task_id = Column(String(100), nullable=True)

    # History / audit fields
    started_at         = Column(DateTime(timezone=True), nullable=True)   # when pipeline actually began
    completed_at       = Column(DateTime(timezone=True), nullable=True)   # when pipeline finished (success or failure)
    uploaded_filenames = Column(JSONB, nullable=True)                     # list of original filenames from RAG uploads

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ── Campaign Manager ─────────────────────────────────────────────────────

class Campaign(Base):
    """
    Paid ad campaign managed across Google Ads and Meta Ads.

    Status machine:
      draft → active | paused | stopped
    """
    __tablename__ = "campaigns"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name            = Column(String(255), nullable=False)
    vendor          = Column(String(50),  nullable=False)          # google | meta
    external_id     = Column(String(255), nullable=True)           # vendor campaign ID
    status          = Column(String(50),  nullable=False, default="draft", index=True)
    daily_budget_limit  = Column(Numeric(10, 2), nullable=True)
    total_budget_limit  = Column(Numeric(10, 2), nullable=True)
    drive_folder_id = Column(String(255), nullable=True)

    # Creative Lab
    creative_prompt    = Column(Text,  nullable=True)
    creative_assets    = Column(JSONB, nullable=True)              # [{url, file_id, format}]
    creative_approved  = Column(Boolean, nullable=False, default=False)

    # AI Insight Engine
    ai_insights        = Column(JSONB, nullable=True)              # latest insight payload
    insights_at        = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    metrics = relationship("MetricsHistory", back_populates="campaign",
                           order_by="MetricsHistory.timestamp.desc()")


class MetricsHistory(Base):
    """Hourly metrics snapshot per campaign (populated by the budget-monitor beat task)."""
    __tablename__ = "metrics_history"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    spend       = Column(Numeric(10, 2), nullable=False, default=0)
    clicks      = Column(Integer, nullable=False, default=0)
    impressions = Column(Integer, nullable=False, default=0)
    cpa         = Column(Numeric(10, 2), nullable=True)
    timestamp   = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc), index=True)

    campaign = relationship("Campaign", back_populates="metrics")


# ── Content Repurposing ─────────────────────────────────────────────────────

class CRJob(Base):
    """
    Content Repurposing job — one per submitted video.

    State machine:
      pending → downloading → transcribing → scoring → processing →
      generating_text → packaging → review_pending → approved →
      delivering → delivered → failed
    """
    __tablename__ = "cr_jobs"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status         = Column(String(50), nullable=False, default="pending", index=True)
    plan           = Column(String(50), nullable=False, default="starter")

    # Order fields (flat copy for quick reads without deserialising input_data)
    show_name      = Column(String(255), nullable=True)
    episode_title  = Column(String(255), nullable=True)
    client_email   = Column(String(255), nullable=True)

    # Full original order payload
    input_data     = Column(JSONB, nullable=False, default=dict)

    # Transcription outputs
    transcript      = Column(Text, nullable=True)
    segments_json   = Column(JSONB, nullable=True)   # Whisper word-level segments
    video_duration_s = Column(Float, nullable=True)

    # Chapter review gate (Feature 4)
    chapters_json        = Column(JSONB, nullable=True)   # [{index, title, start_s, end_s, summary}]
    selected_chapter_ids = Column(JSONB, nullable=True)   # [0, 2, 4] — null means all chapters

    # Delivery
    drive_folder_id = Column(String(255), nullable=True)
    clip_count      = Column(Integer, nullable=True)

    error_message  = Column(Text, nullable=True)
    celery_task_id = Column(String(100), nullable=True)

    created_at   = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))
    updated_at   = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    clips = relationship("CRClipAsset", back_populates="job",
                         cascade="all, delete-orphan", order_by="CRClipAsset.clip_index")

    def __repr__(self):
        return f"<CRJob {self.id} plan={self.plan} status={self.status}>"


class CRClipAsset(Base):
    """
    One extracted, transcoded, and titled clip within a CRJob.
    Created per clip during Phase 4-6.
    """
    __tablename__ = "cr_clip_assets"

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    cr_job_id        = Column(UUID(as_uuid=True), ForeignKey("cr_jobs.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    clip_index       = Column(Integer, nullable=False)   # 0-based within job
    start_s          = Column(Float, nullable=False)
    end_s            = Column(Float, nullable=False)
    virality_score   = Column(Float, nullable=True)
    hook             = Column(Text, nullable=True)       # one-line hook from virality scorer

    # Drive references (file IDs)
    drive_clip_id      = Column(String(255), nullable=True)
    drive_thumbnail_id = Column(String(255), nullable=True)

    # Metadata
    title         = Column(String(500), nullable=True)
    description   = Column(Text, nullable=True)
    platform      = Column(String(50), nullable=True)   # primary platform for this clip
    caption_text  = Column(Text, nullable=True)         # SRT content

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    job = relationship("CRJob", back_populates="clips")

    def __repr__(self):
        return (f"<CRClipAsset job={self.cr_job_id} idx={self.clip_index} "
                f"score={self.virality_score}>")
