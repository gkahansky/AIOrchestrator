"""CRM module — Contact lifecycle/compliance columns, crm_audit_log, crm_consent

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-05-23 00:00:00.000000

H-11. Adds the data foundation for the unified CRM module:
  - new compliance/lifecycle columns on `contacts`
  - `leads.contact_id` FK linking discovered leads to their unified Contact
  - `crm_audit_log` (append-only audit trail)
  - `crm_consent` (per-venture/per-channel consent ledger)
Backfills lifecycle_stage from the legacy `status`, email_hash, lifetime value
from revenue events, and a far-future suppression date for unsubscribed rows.
Fully reversible.
"""
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "j5k6l7m8n9o0"
down_revision: Union[str, Sequence[str], None] = "i4j5k6l7m8n9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FAR_FUTURE = "2099-01-01 00:00:00+00"


def upgrade() -> None:
    # ── contacts: new columns ────────────────────────────────────────────
    op.add_column("contacts", sa.Column("lifecycle_stage", sa.String(length=20),
                                         nullable=False, server_default="lead"))
    op.add_column("contacts", sa.Column("lifetime_value_cents", sa.Integer(),
                                         nullable=False, server_default="0"))
    op.add_column("contacts", sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()),
                                         nullable=False, server_default="[]"))
    op.add_column("contacts", sa.Column("owner_user", sa.String(length=255), nullable=True))
    op.add_column("contacts", sa.Column("do_not_contact_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("gdpr_erasure_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("email_hash", sa.String(length=64), nullable=True))
    op.add_column("contacts", sa.Column("primary_source", sa.String(length=50), nullable=True))

    op.create_index(op.f("ix_contacts_lifecycle_stage"), "contacts", ["lifecycle_stage"])
    op.create_index(op.f("ix_contacts_do_not_contact_until"), "contacts", ["do_not_contact_until"])
    op.create_index(op.f("ix_contacts_email_hash"), "contacts", ["email_hash"])
    op.create_index(op.f("ix_contacts_primary_source"), "contacts", ["primary_source"])

    # ── leads: contact_id FK ─────────────────────────────────────────────
    op.add_column("leads", sa.Column("contact_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_leads_contact_id"), "leads", ["contact_id"])
    op.create_foreign_key("fk_leads_contact_id", "leads", "contacts",
                          ["contact_id"], ["id"], ondelete="SET NULL")

    # ── crm_audit_log ────────────────────────────────────────────────────
    op.create_table(
        "crm_audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("actor_user", sa.String(length=255), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_crm_audit_log_actor_user"), "crm_audit_log", ["actor_user"])
    op.create_index(op.f("ix_crm_audit_log_contact_id"), "crm_audit_log", ["contact_id"])
    op.create_index(op.f("ix_crm_audit_log_action"), "crm_audit_log", ["action"])
    op.create_index(op.f("ix_crm_audit_log_at"), "crm_audit_log", ["at"])

    # ── crm_consent ──────────────────────────────────────────────────────
    op.create_table(
        "crm_consent",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column("venture", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("consent_type", sa.String(length=20), nullable=False),
        sa.Column("lawful_basis", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contact_id", "venture", "channel", "consent_type",
                            name="uq_crm_consent_scope"),
    )
    op.create_index(op.f("ix_crm_consent_contact_id"), "crm_consent", ["contact_id"])
    op.create_index(op.f("ix_crm_consent_venture"), "crm_consent", ["venture"])

    # ── backfill ─────────────────────────────────────────────────────────
    bind = op.get_bind()

    # lifecycle_stage from legacy status
    bind.execute(sa.text("""
        UPDATE contacts SET lifecycle_stage = CASE
            WHEN status = 'purchased'    THEN 'customer'
            WHEN status = 'unsubscribed' THEN 'unsubscribed'
            WHEN status = 'inquired'     THEN 'sample'
            ELSE 'lead'
        END
    """))

    # suppress unsubscribed contacts so the send_email gate catches them
    bind.execute(sa.text(
        "UPDATE contacts SET do_not_contact_until = :ff WHERE status = 'unsubscribed'"
    ), {"ff": FAR_FUTURE})

    # lifetime value from revenue events joined via jobs.input_data->>'client_email'
    bind.execute(sa.text("""
        UPDATE contacts c SET lifetime_value_cents = sub.cents
        FROM (
            SELECT lower(j.input_data->>'client_email') AS email,
                   (COALESCE(SUM(r.net_usd), 0) * 100)::int AS cents
            FROM revenue_events r
            JOIN jobs j ON r.job_id = j.id
            WHERE j.input_data->>'client_email' IS NOT NULL
            GROUP BY lower(j.input_data->>'client_email')
        ) sub
        WHERE c.email IS NOT NULL AND lower(c.email) = sub.email
    """))
    # promote multi-purchase customers to repeat
    bind.execute(sa.text("""
        UPDATE contacts c SET lifecycle_stage = 'repeat'
        FROM (
            SELECT lower(j.input_data->>'client_email') AS email, COUNT(*) AS n
            FROM revenue_events r
            JOIN jobs j ON r.job_id = j.id
            WHERE r.net_usd > 0 AND j.input_data->>'client_email' IS NOT NULL
            GROUP BY lower(j.input_data->>'client_email')
            HAVING COUNT(*) >= 2
        ) sub
        WHERE c.email IS NOT NULL AND lower(c.email) = sub.email
          AND c.lifecycle_stage = 'customer'
    """))

    # email_hash — computed in Python to avoid a pgcrypto dependency
    rows = bind.execute(sa.text(
        "SELECT id, email FROM contacts WHERE email IS NOT NULL"
    )).fetchall()
    for row in rows:
        h = hashlib.sha256(row.email.strip().lower().encode("utf-8")).hexdigest()
        bind.execute(sa.text("UPDATE contacts SET email_hash = :h WHERE id = :id"),
                     {"h": h, "id": row.id})


def downgrade() -> None:
    op.drop_index(op.f("ix_crm_consent_venture"), table_name="crm_consent")
    op.drop_index(op.f("ix_crm_consent_contact_id"), table_name="crm_consent")
    op.drop_table("crm_consent")

    op.drop_index(op.f("ix_crm_audit_log_at"), table_name="crm_audit_log")
    op.drop_index(op.f("ix_crm_audit_log_action"), table_name="crm_audit_log")
    op.drop_index(op.f("ix_crm_audit_log_contact_id"), table_name="crm_audit_log")
    op.drop_index(op.f("ix_crm_audit_log_actor_user"), table_name="crm_audit_log")
    op.drop_table("crm_audit_log")

    op.drop_constraint("fk_leads_contact_id", "leads", type_="foreignkey")
    op.drop_index(op.f("ix_leads_contact_id"), table_name="leads")
    op.drop_column("leads", "contact_id")

    op.drop_index(op.f("ix_contacts_primary_source"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_email_hash"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_do_not_contact_until"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_lifecycle_stage"), table_name="contacts")
    for col in ("primary_source", "email_hash", "gdpr_erasure_at", "do_not_contact_until",
                "owner_user", "tags", "lifetime_value_cents", "lifecycle_stage"):
        op.drop_column("contacts", col)
