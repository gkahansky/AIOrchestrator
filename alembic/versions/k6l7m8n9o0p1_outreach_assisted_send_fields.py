"""Outreach: assisted-send fields on lead_drafts; make outreach_sends.template_id nullable

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-05-25 00:10:00

Changes:
  lead_drafts    — add send_deep_link, send_platform (assisted send state)
  outreach_sends — make template_id nullable (draft-based sends have no template)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'k6l7m8n9o0p1'
down_revision: Union[str, Sequence[str], None] = 'j5k6l7m8n9o0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('lead_drafts', sa.Column('send_deep_link', sa.String(2048), nullable=True))
    op.add_column('lead_drafts', sa.Column('send_platform', sa.String(50), nullable=True))
    op.alter_column('outreach_sends', 'template_id', nullable=True)


def downgrade() -> None:
    # Note: rows with NULL template_id (draft-based sends) would block re-adding
    # the NOT NULL constraint; clear them first if downgrading.
    op.alter_column('outreach_sends', 'template_id', nullable=False)
    op.drop_column('lead_drafts', 'send_platform')
    op.drop_column('lead_drafts', 'send_deep_link')
