"""market_research add title column

Revision ID: e3f4a5b6c7d8
Revises: d1e2f3a4b5c6
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa

revision = 'e3f4a5b6c7d8'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('market_research', sa.Column('title', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('market_research', 'title')
