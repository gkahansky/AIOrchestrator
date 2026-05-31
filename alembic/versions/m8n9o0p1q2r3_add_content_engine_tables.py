"""Add content engine tables — brands, strategies, items, assets, social accounts, publish jobs

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-05-31

Adds the Content Engine venture: multi-channel social content creation +
publishing for EchoForge Accessibility (and future brands).

Tables:
  content_brands       — per-brand voice profile, themes, banned phrases
  content_strategies   — versioned editorial calendar per brand
  content_items        — one piece of content (status machine + per-channel variants)
  content_assets       — generated media (image/video/audio/doc) per item
  social_accounts      — OAuth tokens per (brand × channel)
  publish_jobs         — one row per (item × channel) publish attempt

Also extends venture_enum with 'content_engine'.

Uses IF NOT EXISTS throughout so re-running on a partially-migrated DB is safe.
"""
from alembic import op


revision = "m8n9o0p1q2r3"
down_revision = "l7m8n9o0p1q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend venture_enum with the new venture value (idempotent).
    op.execute("ALTER TYPE venture_enum ADD VALUE IF NOT EXISTS 'content_engine'")

    op.execute("""
        CREATE TABLE IF NOT EXISTS content_brands (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug                 VARCHAR(64) NOT NULL UNIQUE,
            name                 VARCHAR(255) NOT NULL,
            venture_tag          VARCHAR(64),
            description          TEXT,
            voice_profile_json   JSONB NOT NULL DEFAULT '{}',
            theme_weights        JSONB NOT NULL DEFAULT '{}',
            banned_phrases       JSONB NOT NULL DEFAULT '[]',
            channel_cadence      JSONB NOT NULL DEFAULT '{}',
            target_personas      JSONB NOT NULL DEFAULT '[]',
            auto_strategy_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_brands_slug ON content_brands (slug)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS content_strategies (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            brand_id             UUID NOT NULL REFERENCES content_brands(id) ON DELETE CASCADE,
            title                VARCHAR(255) NOT NULL,
            period_days          INTEGER NOT NULL DEFAULT 30,
            status               VARCHAR(32) NOT NULL DEFAULT 'draft',
            pillars_json         JSONB NOT NULL DEFAULT '[]',
            channel_cadence_json JSONB NOT NULL DEFAULT '{}',
            calendar_json        JSONB NOT NULL DEFAULT '[]',
            notes                TEXT,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            approved_at          TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_strategies_brand ON content_strategies (brand_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_strategies_status ON content_strategies (status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS content_items (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            brand_id            UUID NOT NULL REFERENCES content_brands(id) ON DELETE CASCADE,
            strategy_id         UUID REFERENCES content_strategies(id) ON DELETE SET NULL,
            job_id              UUID REFERENCES jobs(id) ON DELETE SET NULL,
            title               VARCHAR(500),
            format              VARCHAR(32) NOT NULL DEFAULT 'post',
            channels            JSONB NOT NULL DEFAULT '[]',
            pillar              VARCHAR(128),
            topic               TEXT,
            status              VARCHAR(32) NOT NULL DEFAULT 'brief',
            scheduled_for       TIMESTAMPTZ,
            brief_json          JSONB NOT NULL DEFAULT '{}',
            variants_json       JSONB NOT NULL DEFAULT '{}',
            quality_report_json JSONB NOT NULL DEFAULT '{}',
            review_notes        TEXT,
            error_message       TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            approved_at         TIMESTAMPTZ,
            published_at        TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_brand ON content_items (brand_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_strategy ON content_items (strategy_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_status ON content_items (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_items_scheduled_for ON content_items (scheduled_for)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS content_assets (
            id          BIGSERIAL PRIMARY KEY,
            item_id     UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            kind        VARCHAR(32) NOT NULL,
            role        VARCHAR(64),
            channel     VARCHAR(64),
            drive_id    VARCHAR(255),
            url         VARCHAR(2048),
            local_path  VARCHAR(1024),
            meta_json   JSONB NOT NULL DEFAULT '{}',
            cost_usd    NUMERIC(10, 6),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_assets_item ON content_assets (item_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS social_accounts (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            brand_id      UUID NOT NULL REFERENCES content_brands(id) ON DELETE CASCADE,
            platform      VARCHAR(48) NOT NULL,
            account_id    VARCHAR(255),
            account_name  VARCHAR(255),
            access_token  TEXT,
            refresh_token TEXT,
            expires_at    TIMESTAMPTZ,
            scopes        JSONB NOT NULL DEFAULT '[]',
            meta_json     JSONB NOT NULL DEFAULT '{}',
            enabled       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_social_accounts_brand ON social_accounts (brand_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_social_accounts_platform ON social_accounts (platform)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS publish_jobs (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id          UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
            channel          VARCHAR(48) NOT NULL,
            status           VARCHAR(32) NOT NULL DEFAULT 'pending',
            external_post_id VARCHAR(255),
            external_url     VARCHAR(2048),
            deep_link        VARCHAR(2048),
            error_message    TEXT,
            payload_json     JSONB NOT NULL DEFAULT '{}',
            response_json    JSONB NOT NULL DEFAULT '{}',
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            published_at     TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_publish_jobs_item ON publish_jobs (item_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_publish_jobs_status ON publish_jobs (status)")


def downgrade() -> None:
    # Note: removing an enum value requires recreating the type. We leave the
    # 'content_engine' value in place on downgrade — harmless if unused.
    op.execute("DROP TABLE IF EXISTS publish_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS social_accounts CASCADE")
    op.execute("DROP TABLE IF EXISTS content_assets CASCADE")
    op.execute("DROP TABLE IF EXISTS content_items CASCADE")
    op.execute("DROP TABLE IF EXISTS content_strategies CASCADE")
    op.execute("DROP TABLE IF EXISTS content_brands CASCADE")
