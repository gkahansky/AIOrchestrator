"""Content Engine M4 — brand fields for auto-approve and voice source URLs.

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-06-02

Adds two columns to `content_brands`:
  - `auto_approve_min_score` INT — items whose quality_report.ai_tell_score is
    at least this threshold (and have zero banned phrases + length OK) skip
    the review_pending gate and go straight to `approved`. Default 0
    (= always require human review).
  - `voice_source_urls` JSONB — list of URLs (e.g. echoforge.biz pages) the
    brand-voice regeneration endpoint scrapes when called.
"""
from alembic import op


revision = "n9o0p1q2r3s4"
down_revision = "m8n9o0p1q2r3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE content_brands "
        "ADD COLUMN IF NOT EXISTS auto_approve_min_score INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE content_brands "
        "ADD COLUMN IF NOT EXISTS voice_source_urls JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE content_brands DROP COLUMN IF EXISTS voice_source_urls")
    op.execute("ALTER TABLE content_brands DROP COLUMN IF EXISTS auto_approve_min_score")
