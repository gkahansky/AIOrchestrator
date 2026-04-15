"""Add security_audit venture — SecurityAudit table, extend VENTURE_ENUM

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-04-15

Changes:
  jobs.venture       — add "security_audit" to venture_enum
  security_audits    — new table for security audit job tracking
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend the venture_enum to include security_audit
    op.execute("ALTER TYPE venture_enum ADD VALUE IF NOT EXISTS 'security_audit'")

    # Create security_audits table
    op.create_table(
        'security_audits',
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_url', sa.String(2048), nullable=False),
        sa.Column('target_domain', sa.String(255), nullable=False),
        sa.Column('tier', sa.String(50), nullable=False, server_default='starter'),

        # Scope verification
        sa.Column('scope_token', sa.String(100), nullable=True),
        sa.Column('scope_verified', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('scope_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scope_method', sa.String(50), nullable=True),

        # Authenticated testing
        sa.Column('auth_username', sa.String(255), nullable=True),
        sa.Column('auth_password', sa.String(255), nullable=True),
        sa.Column('auth_login_url', sa.String(2048), nullable=True),

        # Phase outputs
        sa.Column('phase1_recon_data', postgresql.JSONB, nullable=True),
        sa.Column('phase2_surface_data', postgresql.JSONB, nullable=True),
        sa.Column('phase3_vuln_data', postgresql.JSONB, nullable=True),
        sa.Column('phase4_exploit_data', postgresql.JSONB, nullable=True),
        sa.Column('phase5_auth_data', postgresql.JSONB, nullable=True),

        # Aggregated AI findings
        sa.Column('findings_json', postgresql.JSONB, nullable=True),
        sa.Column('attack_chains', postgresql.JSONB, nullable=True),
        sa.Column('risk_score', sa.Integer, nullable=True),

        sa.Column('reviewer_notes', sa.Text, nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),

        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index('ix_security_audits_job_id', 'security_audits', ['job_id'])
    op.create_index('ix_security_audits_target_domain', 'security_audits', ['target_domain'])
    op.create_index('ix_security_audits_status', 'security_audits', ['status'])


def downgrade() -> None:
    op.drop_table('security_audits')
    # Note: PostgreSQL does not support removing enum values; venture_enum stays extended.
