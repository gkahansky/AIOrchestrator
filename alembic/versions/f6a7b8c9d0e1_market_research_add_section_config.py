"""market_research add section_config column

Revision ID: f6a7b8c9d0e1
Revises: e3f4a5b6c7d8
Create Date: 2026-04-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'f6a7b8c9d0e1'
down_revision = 'f5a6b7c8d9e0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('market_research', sa.Column('section_config', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('market_research', 'section_config')
