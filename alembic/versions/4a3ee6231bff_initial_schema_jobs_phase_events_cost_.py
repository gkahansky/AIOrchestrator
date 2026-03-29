"""initial schema: jobs, phase_events, cost_events, revenue_events

Revision ID: 4a3ee6231bff
Revises:
Create Date: 2026-03-29 16:55:38.320094

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4a3ee6231bff'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum type helpers — create/drop outside of table context so they're shared
venture_enum = postgresql.ENUM(
    "etsy", "marketing_audit", "content_studio",
    name="venture_enum",
)
environment_enum = postgresql.ENUM(
    "production", "staging",
    name="environment_enum",
)
phase_event_type_enum = postgresql.ENUM(
    "started", "completed", "failed", "paused", "resumed",
    name="phase_event_type_enum",
)


def upgrade() -> None:
    """Create all four tables and their supporting enum types."""

    # ── Enum types ─────────────────────────────────────────────────────────────
    venture_enum.create(op.get_bind(), checkfirst=True)
    environment_enum.create(op.get_bind(), checkfirst=True)
    phase_event_type_enum.create(op.get_bind(), checkfirst=True)

    # ── jobs ───────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("venture", sa.Enum("etsy", "marketing_audit", "content_studio",
                                     name="venture_enum"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("phase_current", sa.Integer, nullable=True),
        sa.Column("phase_total", sa.Integer, nullable=True),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default="{}"),
        sa.Column("output_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column("environment", sa.Enum("production", "staging",
                                          name="environment_enum"),
                  nullable=False, server_default="production"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_venture", "jobs", ["venture"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    # ── phase_events ───────────────────────────────────────────────────────────
    op.create_table(
        "phase_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase", sa.Integer, nullable=True),
        sa.Column("event_type", sa.Enum("started", "completed", "failed", "paused", "resumed",
                                         name="phase_event_type_enum"), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_phase_events_job_id", "phase_events", ["job_id"])

    # ── cost_events ────────────────────────────────────────────────────────────
    op.create_table(
        "cost_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("venture", sa.String(50), nullable=True),
        sa.Column("capability", sa.String(100), nullable=False),
        sa.Column("tool_id", sa.String(100), nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=True),
        sa.Column("tokens_out", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_cost_events_job_id", "cost_events", ["job_id"])
    op.create_index("ix_cost_events_venture", "cost_events", ["venture"])

    # ── revenue_events ─────────────────────────────────────────────────────────
    op.create_table(
        "revenue_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("venture", sa.String(50), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("amount_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("fee_usd", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("net_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_revenue_events_job_id", "revenue_events", ["job_id"])
    op.create_index("ix_revenue_events_venture", "revenue_events", ["venture"])


def downgrade() -> None:
    """Drop all four tables and enum types."""
    op.drop_table("revenue_events")
    op.drop_table("cost_events")
    op.drop_table("phase_events")
    op.drop_table("jobs")

    phase_event_type_enum.drop(op.get_bind(), checkfirst=True)
    environment_enum.drop(op.get_bind(), checkfirst=True)
    venture_enum.drop(op.get_bind(), checkfirst=True)
