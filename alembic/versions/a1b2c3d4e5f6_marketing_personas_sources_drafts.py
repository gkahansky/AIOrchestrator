"""Marketing redesign: personas/sources/drafts on campaigns; context on leads

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-05-04 00:00:00

Changes:
  outreach_campaigns  — add personas, target_prompt, user_search_instructions,
                        auto_search_enabled, search_interval_hours,
                        next_search_at, last_search_at
  leads               — add context, matched_persona
  campaign_sources    — new table (one-to-many with outreach_campaigns)
  lead_drafts         — new table (one-to-many with leads)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── outreach_campaigns: new fields ────────────────────────────────────────
    op.add_column('outreach_campaigns', sa.Column('personas', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('outreach_campaigns', sa.Column('target_prompt', sa.Text(), nullable=True))
    op.add_column('outreach_campaigns', sa.Column('user_search_instructions', sa.Text(), nullable=True))
    op.add_column('outreach_campaigns', sa.Column('auto_search_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('outreach_campaigns', sa.Column('search_interval_hours', sa.Integer(), nullable=True))
    op.add_column('outreach_campaigns', sa.Column('next_search_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('outreach_campaigns', sa.Column('last_search_at', sa.DateTime(timezone=True), nullable=True))

    # ── leads: context + persona match ───────────────────────────────────────
    op.add_column('leads', sa.Column('context', sa.Text(), nullable=True))
    op.add_column('leads', sa.Column('matched_persona', sa.String(100), nullable=True))

    # ── campaign_sources ─────────────────────────────────────────────────────
    op.create_table(
        'campaign_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('outreach_campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index('ix_campaign_sources_campaign_id', 'campaign_sources', ['campaign_id'])

    # ── lead_drafts ───────────────────────────────────────────────────────────
    op.create_table(
        'lead_drafts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('outreach_campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('message_body', sa.Text(), nullable=False),
        sa.Column('context_used', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending_review'),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('send_record_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('outreach_sends.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_lead_drafts_lead_id', 'lead_drafts', ['lead_id'])
    op.create_index('ix_lead_drafts_campaign_id', 'lead_drafts', ['campaign_id'])
    op.create_index('ix_lead_drafts_status', 'lead_drafts', ['status'])


def downgrade() -> None:
    op.drop_table('lead_drafts')
    op.drop_table('campaign_sources')
    op.drop_column('leads', 'matched_persona')
    op.drop_column('leads', 'context')
    op.drop_column('outreach_campaigns', 'last_search_at')
    op.drop_column('outreach_campaigns', 'next_search_at')
    op.drop_column('outreach_campaigns', 'search_interval_hours')
    op.drop_column('outreach_campaigns', 'auto_search_enabled')
    op.drop_column('outreach_campaigns', 'user_search_instructions')
    op.drop_column('outreach_campaigns', 'target_prompt')
    op.drop_column('outreach_campaigns', 'personas')
