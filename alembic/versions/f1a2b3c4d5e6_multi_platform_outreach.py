"""Multi-platform outreach — platform on campaigns, usernames on contacts, platform_username on leads

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-04-11 10:00:00

Changes:
  outreach_campaigns  — add `platform` column (default "email")
  outreach_templates  — make `subject` and `body_html` nullable (non-email platforms have neither)
  contacts            — make `email` nullable, add `usernames` JSONB
  leads               — add `platform_username` column
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── outreach_campaigns: add platform ─────────────────────────────────────
    op.add_column(
        'outreach_campaigns',
        sa.Column('platform', sa.String(50), nullable=False, server_default='email'),
    )

    # ── outreach_templates: make subject + body_html nullable ─────────────────
    op.alter_column('outreach_templates', 'subject',   nullable=True)
    op.alter_column('outreach_templates', 'body_html', nullable=True)

    # ── contacts: make email nullable, add usernames JSONB ────────────────────
    # Drop the unique index first, then alter the column
    op.drop_index('ix_contacts_email', table_name='contacts')
    op.alter_column('contacts', 'email', nullable=True)
    op.create_index('ix_contacts_email', 'contacts', ['email'], unique=True,
                    postgresql_where=sa.text('email IS NOT NULL'))
    op.add_column(
        'contacts',
        sa.Column('usernames', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # ── leads: add platform_username ─────────────────────────────────────────
    op.add_column(
        'leads',
        sa.Column('platform_username', sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('leads', 'platform_username')
    op.drop_column('contacts', 'usernames')
    op.drop_index('ix_contacts_email', table_name='contacts')
    op.alter_column('contacts', 'email', nullable=False)
    op.create_index('ix_contacts_email', 'contacts', ['email'], unique=True)
    op.alter_column('outreach_templates', 'body_html', nullable=False)
    op.alter_column('outreach_templates', 'subject',   nullable=False)
    op.drop_column('outreach_campaigns', 'platform')
