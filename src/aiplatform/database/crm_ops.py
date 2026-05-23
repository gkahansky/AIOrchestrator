"""
CRM operations — the single choke point for writing Contact records, consent,
audit log, and for the compliance checks (suppression, cooldowns, unsubscribe
token validation). CRM module (H-11).

Every ingestion path (sample endpoints, venture order routers, outreach worker,
revenue logging) writes through `upsert_contact()` so lifecycle transitions,
provenance, and audit entries stay in one place.

Helpers accept an optional `db` session: when supplied they operate inside the
caller's transaction and do NOT commit (the caller owns the commit); when
omitted they open and commit their own session.
"""
from __future__ import annotations

import hashlib
import logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select, func

from aiplatform.database.session import SessionLocal
from aiplatform.database.models import (
    Contact, ContactMessage, CrmAuditLog, CrmConsent, Lead, Job, RevenueEvent,
)

log = logging.getLogger(__name__)

# ── Lifecycle stages ──────────────────────────────────────────────────────
STAGE_LEAD = "lead"
STAGE_SAMPLE = "sample"
STAGE_CUSTOMER = "customer"
STAGE_REPEAT = "repeat"
STAGE_DORMANT = "dormant"
STAGE_UNSUBSCRIBED = "unsubscribed"
STAGE_ERASED = "erased"

# Linear progression weights; higher only ever replaces lower.
_STAGE_WEIGHT = {STAGE_LEAD: 0, STAGE_SAMPLE: 1, STAGE_CUSTOMER: 2, STAGE_REPEAT: 3}
_TERMINAL = {STAGE_UNSUBSCRIBED, STAGE_ERASED}

FAR_FUTURE = datetime(2099, 1, 1, tzinfo=timezone.utc)


class ContactSuppressed(Exception):
    """Raised by upsert_contact(block_if_suppressed=True) when the contact must not be contacted."""


class MissingUnsubscribe(ValueError):
    """Raised when an outbound body lacks a working unsubscribe affordance."""


# ── Internal helpers ────────────────────────────────────────────────────────

@contextmanager
def _session(db=None):
    """Yield (session, owns). If db is passed, reuse it without committing."""
    if db is not None:
        yield db, False
        return
    s = SessionLocal()
    s.expire_on_commit = False  # keep returned ORM objects usable after commit
    try:
        yield s, True
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _advance_stage(current: str | None, proposed: str | None) -> str:
    """Monotonic forward-only transition. Terminal stages are never overwritten."""
    if not proposed:
        return current or STAGE_LEAD
    if current in _TERMINAL:
        return current
    if current == STAGE_DORMANT and proposed in _STAGE_WEIGHT:
        return proposed  # reactivation
    cw = _STAGE_WEIGHT.get(current, -1)
    pw = _STAGE_WEIGHT.get(proposed, -1)
    if pw == -1:        # proposed is a special stage (dormant/unsubscribed/erased)
        return proposed
    return proposed if pw > cw else (current or proposed)


def log_audit(db, actor_user: str, contact_id, action: str,
              before: dict | None = None, after: dict | None = None,
              reason: str | None = None) -> None:
    """Append a CrmAuditLog row inside the given session (no commit)."""
    db.add(CrmAuditLog(
        actor_user=actor_user or "system",
        contact_id=contact_id,
        action=action,
        before=before,
        after=after,
        reason=reason,
        at=datetime.now(timezone.utc),
    ))


def _is_suppressed_contact(contact: Contact) -> bool:
    if contact is None:
        return False
    if contact.lifecycle_stage in _TERMINAL:
        return True
    if contact.do_not_contact_until is not None:
        dnc = contact.do_not_contact_until
        if dnc.tzinfo is None:
            dnc = dnc.replace(tzinfo=timezone.utc)
        if dnc > datetime.now(timezone.utc):
            return True
    return False


def _find_contact(db, clean_email: str | None, usernames: dict | None) -> Contact | None:
    if clean_email:
        c = db.execute(select(Contact).filter(Contact.email == clean_email)).scalars().first()
        if c:
            return c
    if usernames:
        for platform, handle in usernames.items():
            if not handle:
                continue
            c = db.execute(
                select(Contact).filter(Contact.usernames[platform].astext == handle)
            ).scalars().first()
            if c:
                return c
    return None


# ── Core upsert ─────────────────────────────────────────────────────────────

def upsert_contact(
    email: str | None = None,
    usernames: dict | None = None,
    lifecycle_stage: str | None = None,
    primary_source: str | None = None,
    venture: str | None = None,
    owner_user: str | None = None,
    name: str | None = None,
    actor_user: str = "system",
    block_if_suppressed: bool = False,
    db=None,
) -> Contact:
    """
    Find-or-create a Contact, merging provenance. Forward-only lifecycle.

    block_if_suppressed=True raises ContactSuppressed when the matched contact
    is unsubscribed/erased or under an active do-not-contact window (used by the
    sample endpoints, which must not email suppressed people). Order intake
    leaves it False so a paid order is never rejected.
    """
    clean_email = email.strip().lower() if email else None
    usernames = {k: v for k, v in (usernames or {}).items() if v}

    with _session(db) as (s, owns):
        contact = _find_contact(s, clean_email, usernames)

        if contact and block_if_suppressed and _is_suppressed_contact(contact):
            raise ContactSuppressed(f"contact {clean_email or usernames} is suppressed")

        if contact is None:
            contact = Contact(
                email=clean_email,
                email_hash=email_hash(clean_email) if clean_email else None,
                usernames=usernames or None,
                name=name,
                lifecycle_stage=lifecycle_stage or STAGE_LEAD,
                status=_legacy_status(lifecycle_stage or STAGE_LEAD),
                primary_source=primary_source,
                owner_user=owner_user,
                ventures_approached=[venture] if venture else [],
                tags=[],
            )
            s.add(contact)
            s.flush()
            log_audit(s, actor_user, contact.id, "status_change",
                      before=None,
                      after={"lifecycle_stage": contact.lifecycle_stage,
                             "primary_source": primary_source},
                      reason="contact created")
        else:
            before = {"lifecycle_stage": contact.lifecycle_stage,
                      "usernames": contact.usernames,
                      "ventures_approached": list(contact.ventures_approached or [])}
            # union usernames
            if usernames:
                merged = dict(contact.usernames or {})
                merged.update(usernames)
                contact.usernames = merged
            # fill missing scalars
            if clean_email and not contact.email:
                contact.email = clean_email
                contact.email_hash = email_hash(clean_email)
            if name and not contact.name:
                contact.name = name
            if owner_user and not contact.owner_user:
                contact.owner_user = owner_user
            if primary_source and not contact.primary_source:
                contact.primary_source = primary_source
            # venture provenance
            if venture and venture not in (contact.ventures_approached or []):
                contact.ventures_approached = list(contact.ventures_approached or []) + [venture]
            # forward-only stage
            new_stage = _advance_stage(contact.lifecycle_stage, lifecycle_stage)
            if new_stage != contact.lifecycle_stage:
                contact.lifecycle_stage = new_stage
                contact.status = _legacy_status(new_stage)
            contact.last_activity_at = datetime.now(timezone.utc)
            after = {"lifecycle_stage": contact.lifecycle_stage,
                     "usernames": contact.usernames,
                     "ventures_approached": list(contact.ventures_approached or [])}
            if after != before:
                log_audit(s, actor_user, contact.id, "edit", before=before, after=after,
                          reason="contact upserted")

        if lifecycle_stage in (STAGE_CUSTOMER, STAGE_REPEAT) and contact.purchased_at is None:
            contact.purchased_at = datetime.now(timezone.utc)

        return contact


def _legacy_status(stage: str) -> str:
    """Mirror lifecycle_stage onto the legacy `status` column for the Marketing module."""
    return {
        STAGE_LEAD: "approached",
        STAGE_SAMPLE: "inquired",
        STAGE_CUSTOMER: "purchased",
        STAGE_REPEAT: "purchased",
        STAGE_DORMANT: "approached",
        STAGE_UNSUBSCRIBED: "unsubscribed",
        STAGE_ERASED: "unsubscribed",
    }.get(stage, "approached")


# ── Revenue → lifetime value / stage ─────────────────────────────────────────

def add_revenue_to_contact(email: str | None, cents: int, db=None) -> None:
    """Increment LTV and advance customer→repeat. No-op when email is missing."""
    if not email:
        return
    clean_email = email.strip().lower()
    with _session(db) as (s, owns):
        contact = s.execute(select(Contact).filter(Contact.email == clean_email)).scalars().first()
        if contact is None:
            contact = upsert_contact(email=clean_email, lifecycle_stage=STAGE_CUSTOMER,
                                     primary_source="revenue", db=s)
        contact.lifetime_value_cents = (contact.lifetime_value_cents or 0) + int(cents)
        if contact.purchased_at is None:
            contact.purchased_at = datetime.now(timezone.utc)
        paid_count = s.execute(
            select(func.count()).select_from(RevenueEvent)
            .join(Job, RevenueEvent.job_id == Job.id)
            .filter(RevenueEvent.net_usd > 0,
                    func.lower(Job.input_data["client_email"].astext) == clean_email)
        ).scalar() or 0
        proposed = STAGE_REPEAT if paid_count >= 2 else STAGE_CUSTOMER
        new_stage = _advance_stage(contact.lifecycle_stage, proposed)
        if new_stage != contact.lifecycle_stage:
            contact.lifecycle_stage = new_stage
            contact.status = _legacy_status(new_stage)


def recompute_stage(contact_id, db=None) -> str | None:
    """Recompute a contact's stage from revenue + activity. Used by the nightly sweep."""
    with _session(db) as (s, owns):
        contact = s.get(Contact, contact_id)
        if contact is None or contact.lifecycle_stage in _TERMINAL:
            return None if contact is None else contact.lifecycle_stage
        if contact.email:
            paid_count = s.execute(
                select(func.count()).select_from(RevenueEvent)
                .join(Job, RevenueEvent.job_id == Job.id)
                .filter(RevenueEvent.net_usd > 0,
                        func.lower(Job.input_data["client_email"].astext) == contact.email.lower())
            ).scalar() or 0
            if paid_count >= 2:
                contact.lifecycle_stage = _advance_stage(contact.lifecycle_stage, STAGE_REPEAT)
            elif paid_count == 1:
                contact.lifecycle_stage = _advance_stage(contact.lifecycle_stage, STAGE_CUSTOMER)
        contact.status = _legacy_status(contact.lifecycle_stage)
        return contact.lifecycle_stage


# ── Compliance: suppression, cooldowns, unsubscribe token ────────────────────

def is_suppressed(email: str, db=None) -> bool:
    """True when this email must not receive any mail (unsubscribed/erased/DNC)."""
    if not email:
        return False
    clean_email = email.strip().lower()
    with _session(db) as (s, owns):
        contact = s.execute(select(Contact).filter(Contact.email == clean_email)).scalars().first()
        return _is_suppressed_contact(contact)


def _recent_message(db, contact_id, types: tuple[str, ...], cutoff) -> bool:
    return db.execute(
        select(ContactMessage).filter(
            ContactMessage.contact_id == contact_id,
            ContactMessage.message_type.in_(types),
            ContactMessage.sent_at >= cutoff,
        )
    ).scalars().first() is not None


def can_send_sample(email: str, venture: str, days: int = 30) -> bool:
    """False if a sample for this venture was sent within `days`, or if suppressed."""
    clean_email = email.strip().lower()
    with _session(None) as (s, owns):
        contact = s.execute(select(Contact).filter(Contact.email == clean_email)).scalars().first()
        if contact is None:
            return True
        if _is_suppressed_contact(contact):
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = s.execute(
            select(ContactMessage).filter(
                ContactMessage.contact_id == contact.id,
                ContactMessage.venture == venture,
                ContactMessage.message_type == "sample",
                ContactMessage.sent_at >= cutoff,
            )
        ).scalars().first()
        return recent is None


def can_send_outreach(email: str, venture: str, days: int = 60) -> bool:
    """False if outreach to this email happened within `days`, or if suppressed."""
    clean_email = email.strip().lower()
    with _session(None) as (s, owns):
        contact = s.execute(select(Contact).filter(Contact.email == clean_email)).scalars().first()
        if contact is None:
            return True
        if _is_suppressed_contact(contact):
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return not _recent_message(s, contact.id, ("outreach", "nurture"), cutoff)


def can_send_marketing(email: str, days: int = 7) -> bool:
    """False if a marketing email went out within `days`, or if suppressed."""
    clean_email = email.strip().lower()
    with _session(None) as (s, owns):
        contact = s.execute(select(Contact).filter(Contact.email == clean_email)).scalars().first()
        if contact is None:
            return True
        if _is_suppressed_contact(contact):
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return not _recent_message(s, contact.id, ("marketing", "nurture"), cutoff)


def validate_outbound_body(body: str, send_id=None) -> None:
    """Raise MissingUnsubscribe if the body has no unsubscribe affordance (CAN-SPAM/§6.2)."""
    if not body or "unsubscribe" not in body.lower():
        raise MissingUnsubscribe(
            f"outbound body is missing an unsubscribe link (send_id={send_id})"
        )


# ── Merge ─────────────────────────────────────────────────────────────────

def merge_contacts(winner_id, loser_id, actor_user: str = "system", db=None) -> Contact:
    """Fold loser into winner: move FKs, union provenance, sum LTV, delete loser."""
    with _session(db) as (s, owns):
        winner = s.get(Contact, winner_id)
        loser = s.get(Contact, loser_id)
        if winner is None or loser is None:
            raise ValueError("both winner and loser contacts must exist")

        before = {"winner_ltv": winner.lifetime_value_cents,
                  "loser_id": str(loser_id), "loser_email": loser.email}

        for model in (Lead, ContactMessage, CrmConsent, CrmAuditLog):
            s.query(model).filter(model.contact_id == loser_id).update(
                {model.contact_id: winner_id}, synchronize_session=False)

        merged_un = dict(winner.usernames or {})
        merged_un.update(loser.usernames or {})
        winner.usernames = merged_un or None
        winner.ventures_approached = list(
            dict.fromkeys((winner.ventures_approached or []) + (loser.ventures_approached or [])))
        winner.tags = list(dict.fromkeys((winner.tags or []) + (loser.tags or [])))
        winner.lifetime_value_cents = (winner.lifetime_value_cents or 0) + (loser.lifetime_value_cents or 0)
        winner.lifecycle_stage = _advance_stage(winner.lifecycle_stage, loser.lifecycle_stage)
        winner.status = _legacy_status(winner.lifecycle_stage)
        if not winner.email and loser.email:
            winner.email = loser.email
            winner.email_hash = email_hash(loser.email)
        if winner.created_at and loser.created_at and loser.created_at < winner.created_at:
            winner.created_at = loser.created_at

        s.delete(loser)
        log_audit(s, actor_user, winner_id, "merge", before=before,
                  after={"winner_ltv": winner.lifetime_value_cents}, reason="contact merge")
        return winner


def ingest_customer(email: str | None, venture: str, source_prefix: str = "order") -> None:
    """Best-effort: record a paying customer at the `customer` stage.

    Never raises — order creation must never fail because of a CRM write. A paid
    order is not blocked by suppression (unlike samples), so block_if_suppressed
    stays False here.
    """
    if not email:
        return
    try:
        upsert_contact(
            email=email,
            lifecycle_stage=STAGE_CUSTOMER,
            primary_source=f"{source_prefix}_{venture}",
            venture=venture,
        )
    except Exception:
        log.exception("ingest_customer failed for %s / %s", venture, email)


# ── Backwards-compatible message logger ──────────────────────────────────────

def log_contact_message(
    email: str,
    venture: str,
    message_type: str,
    subject: str,
    body_snippet: str | None = None,
    message_id: str | None = None,
) -> None:
    """Upsert the contact and log an outbound email. Used by the worker tasks."""
    with _session(None) as (s, owns):
        contact = upsert_contact(email=email, venture=venture, db=s)
        s.add(ContactMessage(
            contact_id=contact.id,
            venture=venture,
            message_type=message_type,
            subject=subject,
            body_snippet=body_snippet,
            message_id=message_id,
        ))
