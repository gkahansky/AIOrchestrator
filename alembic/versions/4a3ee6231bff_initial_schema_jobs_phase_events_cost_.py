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


def upgrade() -> None:
    # ── Enum types via DO block (safe to re-run — ignores if already exists) ───
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE venture_enum AS ENUM ('etsy', 'marketing_audit', 'content_studio');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE environment_enum AS ENUM ('production', 'staging');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE phase_event_type_enum AS ENUM ('started', 'completed', 'failed', 'paused', 'resumed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # ── jobs ───────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("venture",
                  postgresql.ENUM(name="venture_enum", create_type=False),
                  nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("phase_current", sa.Integer, nullable=True),
        sa.Column("phase_total", sa.Integer, nullable=True),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default="{}"),
        sa.Column("output_data", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column("environment",
                  postgresql.ENUM(name="environment_enum", create_type=False),
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
        sa.Column("event_type",
                  postgresql.ENUM(name="phase_event_type_enum", create_type=False),
                  nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default="{}"),
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

    # ── platform_settings ──────────────────────────────────────────────────────
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
    op.drop_table("revenue_events")
    op.drop_table("cost_events")
    op.drop_table("phase_events")
    op.drop_table("jobs")
    op.execute("DROP TYPE IF EXISTS phase_event_type_enum")
    op.execute("DROP TYPE IF EXISTS environment_enum")
    op.execute("DROP TYPE IF EXISTS venture_enum")
