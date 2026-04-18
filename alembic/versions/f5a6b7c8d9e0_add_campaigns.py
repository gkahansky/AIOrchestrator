"""add campaigns and metrics_history tables

Revision ID: f5a6b7c8d9e0
Revises: e3f4a5b6c7d8
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'f5a6b7c8d9e0'
down_revision = 'e3f4a5b6c7d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'campaigns',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('vendor', sa.String(50), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('daily_budget_limit', sa.Numeric(10, 2), nullable=True),
        sa.Column('total_budget_limit', sa.Numeric(10, 2), nullable=True),
        sa.Column('drive_folder_id', sa.String(255), nullable=True),
        sa.Column('creative_prompt', sa.Text, nullable=True),
        sa.Column('creative_assets', JSONB, nullable=True),
        sa.Column('creative_approved', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('ai_insights', JSONB, nullable=True),
        sa.Column('insights_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index('ix_campaigns_status', 'campaigns', ['status'])

    op.create_table(
        'metrics_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('campaign_id', UUID(as_uuid=True),
                  sa.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('spend', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('clicks', sa.Integer, nullable=False, server_default='0'),
        sa.Column('impressions', sa.Integer, nullable=False, server_default='0'),
        sa.Column('cpa', sa.Numeric(10, 2), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index('ix_metrics_history_campaign_id', 'metrics_history', ['campaign_id'])
    op.create_index('ix_metrics_history_timestamp', 'metrics_history', ['timestamp'])


def downgrade() -> None:
    op.drop_table('metrics_history')
    op.drop_table('campaigns')
