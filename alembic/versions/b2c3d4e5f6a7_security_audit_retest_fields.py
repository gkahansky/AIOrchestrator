"""Add retest fields to security_audits table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-16

Changes:
  security_audits — add retest_of_audit_id, retest_finding_ids, retest_requested_at
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'security_audits',
        sa.Column('retest_of_audit_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        'security_audits',
        sa.Column('retest_finding_ids', postgresql.JSONB, nullable=True),
    )
    op.add_column(
        'security_audits',
        sa.Column('retest_requested_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('security_audits', 'retest_requested_at')
    op.drop_column('security_audits', 'retest_finding_ids')
    op.drop_column('security_audits', 'retest_of_audit_id')
