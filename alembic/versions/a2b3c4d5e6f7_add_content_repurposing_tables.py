"""Add content repurposing tables — cr_jobs and cr_clip_assets

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-04-28

Changes:
  cr_jobs        — one per uploaded video; tracks pipeline status + transcript
  cr_clip_assets — one per extracted clip within a job
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = 'a2b3c4d5e6f7'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'cr_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending', index=True),
        sa.Column('plan', sa.String(50), nullable=False, server_default='starter'),
        sa.Column('show_name', sa.String(255), nullable=True),
        sa.Column('episode_title', sa.String(255), nullable=True),
        sa.Column('client_email', sa.String(255), nullable=True),
        sa.Column('input_data', JSONB, nullable=False, server_default='{}'),
        sa.Column('transcript', sa.Text, nullable=True),
        sa.Column('segments_json', JSONB, nullable=True),
        sa.Column('video_duration_s', sa.Float, nullable=True),
        sa.Column('drive_folder_id', sa.String(255), nullable=True),
        sa.Column('clip_count', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('celery_task_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_cr_jobs_status', 'cr_jobs', ['status'])

    op.create_table(
        'cr_clip_assets',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('cr_job_id', UUID(as_uuid=True),
                  sa.ForeignKey('cr_jobs.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('clip_index', sa.Integer, nullable=False),
        sa.Column('start_s', sa.Float, nullable=False),
        sa.Column('end_s', sa.Float, nullable=False),
        sa.Column('virality_score', sa.Float, nullable=True),
        sa.Column('hook', sa.Text, nullable=True),
        sa.Column('drive_clip_id', sa.String(255), nullable=True),
        sa.Column('drive_thumbnail_id', sa.String(255), nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('platform', sa.String(50), nullable=True),
        sa.Column('caption_text', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index('ix_cr_clip_assets_cr_job_id', 'cr_clip_assets', ['cr_job_id'])


def downgrade() -> None:
    op.drop_table('cr_clip_assets')
    op.drop_table('cr_jobs')
