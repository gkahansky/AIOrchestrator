"""market_research add internal flag

Revision ID: h1i2j3k4l5m6
Revises: c2d3e4f5a6b7, g2h3i4j5k6l7
Create Date: 2026-05-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'h1i2j3k4l5m6'
down_revision: Union[str, Sequence[str], None] = ('c2d3e4f5a6b7', 'g2h3i4j5k6l7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'market_research',
        sa.Column('internal', sa.Boolean(), nullable=False, server_default='false'),
    )
    # All previously existing sessions were platform-owned internal research.
    op.execute("UPDATE market_research SET internal = TRUE")


def downgrade() -> None:
    op.drop_column('market_research', 'internal')
