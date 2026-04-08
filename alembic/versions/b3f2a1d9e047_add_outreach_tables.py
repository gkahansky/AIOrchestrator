"""add outreach tables (leads, campaigns, templates, sends)

Revision ID: b3f2a1d9e047
Revises: a7eb62fd41b3
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b3f2a1d9e047'
down_revision: Union[str, Sequence[str], None] = 'a7eb62fd41b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'outreach_campaigns',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('venture', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_outreach_campaigns_venture', 'outreach_campaigns', ['venture'])
    op.create_index('ix_outreach_campaigns_status', 'outreach_campaigns', ['status'])

    op.create_table(
        'leads',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('venture', sa.String(length=50), nullable=False),
        sa.Column('source_channel', sa.String(length=100), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('website_url', sa.String(length=2048), nullable=True),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='new'),
        sa.Column('campaign_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['outreach_campaigns.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_leads_venture', 'leads', ['venture'])
    op.create_index('ix_leads_status', 'leads', ['status'])
    op.create_index('ix_leads_email', 'leads', ['email'])
    op.create_index('ix_leads_campaign_id', 'leads', ['campaign_id'])

    op.create_table(
        'outreach_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('campaign_id', sa.UUID(), nullable=False),
        sa.Column('variant', sa.String(length=10), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('tone_notes', sa.Text(), nullable=True),
        sa.Column('sends_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('opens_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('replies_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('approved', sa.String(length=10), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['outreach_campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_outreach_templates_campaign_id', 'outreach_templates', ['campaign_id'])

    op.create_table(
        'outreach_sends',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('lead_id', sa.UUID(), nullable=False),
        sa.Column('template_id', sa.UUID(), nullable=False),
        sa.Column('campaign_id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='sent'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replied_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['outreach_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['outreach_campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_outreach_sends_lead_id', 'outreach_sends', ['lead_id'])
    op.create_index('ix_outreach_sends_campaign_id', 'outreach_sends', ['campaign_id'])
    op.create_index('ix_outreach_sends_template_id', 'outreach_sends', ['template_id'])


def downgrade() -> None:
    op.drop_table('outreach_sends')
    op.drop_table('outreach_templates')
    op.drop_table('leads')
    op.drop_table('outreach_campaigns')
