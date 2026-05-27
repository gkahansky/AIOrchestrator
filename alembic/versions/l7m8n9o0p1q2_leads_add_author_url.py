"""Leads: add author_url (reachable social profile/channel URL)

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-05-27 12:00:00

Captured by linkedin/facebook/youtube/instagram source handlers so assisted send
can deep-link the operator to the lead's actual profile.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'l7m8n9o0p1q2'
down_revision: Union[str, Sequence[str], None] = 'k6l7m8n9o0p1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('author_url', sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'author_url')
