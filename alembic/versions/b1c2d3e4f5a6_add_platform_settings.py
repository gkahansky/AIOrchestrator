"""add platform_settings table

Revision ID: b1c2d3e4f5a6
Revises: 4a3ee6231bff
Create Date: 2026-03-30

Stores API keys (masked in responses) and tool-router overrides so the
settings API can persist state without requiring a redeploy.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "4a3ee6231bff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TABLE IF NOT EXISTS platform_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        END $$;
    """)


def downgrade() -> None:
    op.drop_table("platform_settings")
