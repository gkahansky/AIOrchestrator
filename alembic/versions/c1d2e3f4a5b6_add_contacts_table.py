"""add contacts table (unified CRM cross-venture)

Revision ID: c1d2e3f4a5b6
Revises: b3f2a1d9e047
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b3f2a1d9e047'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'contacts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('website_url', sa.String(length=2048), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='approached'),
        sa.Column('ventures_approached', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('features_of_interest', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unsubscribed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_contacts_email', 'contacts', ['email'], unique=True)
    op.create_index('ix_contacts_status', 'contacts', ['status'])


def downgrade() -> None:
    op.drop_index('ix_contacts_status', table_name='contacts')
    op.drop_index('ix_contacts_email', table_name='contacts')
    op.drop_table('contacts')
