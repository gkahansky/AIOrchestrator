"""outreach_campaign add use_mock_leads and dry_run columns

Revision ID: g2h3i4j5k6l7
Revises: b4c5d6e7f8a9
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa

revision = 'g2h3i4j5k6l7'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('outreach_campaigns', sa.Column(
        'use_mock_leads', sa.Boolean(), nullable=False,
        server_default='false',
    ))
    op.add_column('outreach_campaigns', sa.Column(
        'dry_run', sa.Boolean(), nullable=False,
        server_default='false',
    ))


def downgrade() -> None:
    op.drop_column('outreach_campaigns', 'dry_run')
    op.drop_column('outreach_campaigns', 'use_mock_leads')
