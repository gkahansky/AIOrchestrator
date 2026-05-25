"""Outreach: reusable persona library + campaign_personas join (backfill from JSONB)

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-05-25 00:00:00

Changes:
  personas           — new table (reusable per-venture persona library)
  campaign_personas  — new join table (campaign <-> persona, many-to-many)
  data backfill      — existing outreach_campaigns.personas JSONB is parsed into
                       persona rows (deduped by (venture, lower(name))) and linked.
                       The JSONB column is left populated for rollback safety; a
                       later migration drops it once code is fully cut over.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
from datetime import datetime, timezone

revision: str = 'j5k6l7m8n9o0'
down_revision: Union[str, Sequence[str], None] = 'i4j5k6l7m8n9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'personas',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venture', sa.String(50), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index('ix_personas_venture', 'personas', ['venture'])

    op.create_table(
        'campaign_personas',
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('outreach_campaigns.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('personas.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index('ix_campaign_personas_persona_id', 'campaign_personas', ['persona_id'])

    _backfill_personas()


def _backfill_personas() -> None:
    """Parse outreach_campaigns.personas JSONB into persona rows + links.

    Dedupes by (venture, lower(name)): the same persona name within a venture
    collapses to one persona row (the reuse semantics), keeping the first
    description seen. Idempotent — skips links that already exist.
    """
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    campaigns = bind.execute(sa.text(
        "SELECT id, venture, personas FROM outreach_campaigns "
        "WHERE personas IS NOT NULL"
    )).fetchall()

    # (venture, lower(name)) -> persona_id  for in-run dedup
    persona_by_key: dict[tuple, str] = {}

    for camp_id, venture, personas_json in campaigns:
        if not personas_json:
            continue
        for entry in personas_json:
            if not isinstance(entry, dict):
                continue
            name = (entry.get("name") or "").strip()
            if not name:
                continue
            description = entry.get("description") or ""
            key = (venture, name.lower())

            persona_id = persona_by_key.get(key)
            if persona_id is None:
                # Reuse a matching persona already in the DB (re-run safety),
                # else create a new one.
                existing = bind.execute(sa.text(
                    "SELECT id FROM personas "
                    "WHERE venture IS NOT DISTINCT FROM :venture AND lower(name) = :lname "
                    "LIMIT 1"
                ), {"venture": venture, "lname": name.lower()}).fetchone()
                if existing:
                    persona_id = str(existing[0])
                else:
                    persona_id = str(uuid.uuid4())
                    bind.execute(sa.text(
                        "INSERT INTO personas (id, venture, name, description, created_at, updated_at) "
                        "VALUES (:id, :venture, :name, :description, :now, :now)"
                    ), {"id": persona_id, "venture": venture, "name": name,
                        "description": description, "now": now})
                persona_by_key[key] = persona_id

            # Link (idempotent)
            already = bind.execute(sa.text(
                "SELECT 1 FROM campaign_personas "
                "WHERE campaign_id = :cid AND persona_id = :pid"
            ), {"cid": str(camp_id), "pid": persona_id}).fetchone()
            if not already:
                bind.execute(sa.text(
                    "INSERT INTO campaign_personas (campaign_id, persona_id, created_at) "
                    "VALUES (:cid, :pid, :now)"
                ), {"cid": str(camp_id), "pid": persona_id, "now": now})


def downgrade() -> None:
    op.drop_index('ix_campaign_personas_persona_id', table_name='campaign_personas')
    op.drop_table('campaign_personas')
    op.drop_index('ix_personas_venture', table_name='personas')
    op.drop_table('personas')
