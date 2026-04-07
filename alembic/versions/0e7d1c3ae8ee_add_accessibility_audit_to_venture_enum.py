"""Add accessibility_audit to venture_enum

Revision ID: 0e7d1c3ae8ee
Revises: a7eb62fd41b3
Create Date: 2026-04-07 10:41:38.307644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0e7d1c3ae8ee'
down_revision: Union[str, Sequence[str], None] = 'a7eb62fd41b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE venture_enum ADD VALUE IF NOT EXISTS 'accessibility_audit'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
