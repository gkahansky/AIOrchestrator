"""Add content repurposing tables — cr_jobs and cr_clip_assets

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-04-28

Changes:
  cr_jobs        — one per uploaded video; tracks pipeline status + transcript
  cr_clip_assets — one per extracted clip within a job

Note: uses IF NOT EXISTS throughout so re-running on a DB that already has the
tables (from a partial migration) is safe.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f7'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS cr_jobs (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            status           VARCHAR(50)  NOT NULL DEFAULT 'pending',
            plan             VARCHAR(50)  NOT NULL DEFAULT 'starter',
            show_name        VARCHAR(255),
            episode_title    VARCHAR(255),
            client_email     VARCHAR(255),
            input_data       JSONB        NOT NULL DEFAULT '{}',
            transcript       TEXT,
            segments_json    JSONB,
            video_duration_s DOUBLE PRECISION,
            drive_folder_id  VARCHAR(255),
            clip_count       INTEGER,
            error_message    TEXT,
            celery_task_id   VARCHAR(100),
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
            completed_at     TIMESTAMPTZ
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cr_jobs_status ON cr_jobs (status)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS cr_clip_assets (
            id                 BIGSERIAL PRIMARY KEY,
            cr_job_id          UUID         NOT NULL REFERENCES cr_jobs(id) ON DELETE CASCADE,
            clip_index         INTEGER      NOT NULL,
            start_s            DOUBLE PRECISION NOT NULL,
            end_s              DOUBLE PRECISION NOT NULL,
            virality_score     DOUBLE PRECISION,
            hook               TEXT,
            drive_clip_id      VARCHAR(255),
            drive_thumbnail_id VARCHAR(255),
            title              VARCHAR(500),
            description        TEXT,
            platform           VARCHAR(50),
            caption_text       TEXT,
            created_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cr_clip_assets_cr_job_id ON cr_clip_assets (cr_job_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cr_clip_assets")
    op.execute("DROP TABLE IF EXISTS cr_jobs")
