"""market_research: add started_at, completed_at, uploaded_filenames

Revision ID: c2d3e4f5a6b7
Revises: b3c4d5e6f7a8
Create Date: 2026-04-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'c2d3e4f5a6b7'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('market_research', sa.Column('started_at',         sa.DateTime(timezone=True), nullable=True))
    op.add_column('market_research', sa.Column('completed_at',       sa.DateTime(timezone=True), nullable=True))
    op.add_column('market_research', sa.Column('uploaded_filenames', JSONB,                      nullable=True))


def downgrade() -> None:
    op.drop_column('market_research', 'uploaded_filenames')
    op.drop_column('market_research', 'completed_at')
    op.drop_column('market_research', 'started_at')
