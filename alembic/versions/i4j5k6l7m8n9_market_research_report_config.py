"""market_research: add report_config and sector columns for productization

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'i4j5k6l7m8n9'
down_revision = 'h3i4j5k6l7m8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('market_research',
        sa.Column('report_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('market_research',
        sa.Column('sector', sa.String(length=100), nullable=True, server_default='business_intelligence'))


def downgrade() -> None:
    op.drop_column('market_research', 'sector')
    op.drop_column('market_research', 'report_config')
