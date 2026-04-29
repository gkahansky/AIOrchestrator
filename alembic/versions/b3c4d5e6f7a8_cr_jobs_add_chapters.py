"""Add chapters_json and selected_chapter_ids to cr_jobs

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-28

Adds two JSONB columns to support the chapter-review gate (Feature 4):
  chapters_json        — Claude-generated chapter list [{index, title, start_s, end_s, summary}]
  selected_chapter_ids — admin-selected chapter indexes [0, 2, 4]; null = all chapters
"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE cr_jobs ADD COLUMN IF NOT EXISTS chapters_json JSONB"
    )
    op.execute(
        "ALTER TABLE cr_jobs ADD COLUMN IF NOT EXISTS selected_chapter_ids JSONB"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE cr_jobs DROP COLUMN IF EXISTS chapters_json")
    op.execute("ALTER TABLE cr_jobs DROP COLUMN IF EXISTS selected_chapter_ids")
