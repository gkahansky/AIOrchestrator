"""Dispatch tests for _send_one_draft (no DB — uses lightweight fakes).

Covers the branches that don't touch the database: dry-run and assisted
(non-email) sends. The email "sent" path is exercised end-to-end in the
manual verification flow against Postgres.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from datetime import datetime, timezone

from aiplatform.worker import _send_one_draft


class _FakeQuery:
    def filter(self, *a, **k):
        return self

    def first(self):
        return None


class _FakeDB:
    """Minimal stand-in: queries return nothing, writes are recorded."""
    def __init__(self):
        self.added = []

    def query(self, *a, **k):
        return _FakeQuery()

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass


def _draft():
    return types.SimpleNamespace(
        id="d1", status="approved", message_body="hello", subject=None,
        sent_at=None, send_record_id=None, send_deep_link=None, send_platform=None,
    )


def _lead(source_channel, **kw):
    base = dict(id="l1", source_channel=source_channel, email=None,
                platform_username=None, source_url=None, name="Bob", status="new")
    base.update(kw)
    return types.SimpleNamespace(**base)


def _campaign():
    return types.SimpleNamespace(id="c1", venture="marketing_audit",
                                 platform="email", dry_run=False)


def test_dry_run_marks_test_sent():
    db, draft, lead, camp = _FakeDB(), _draft(), _lead("linkedin"), _campaign()
    now = datetime.now(timezone.utc)
    r = _send_one_draft(db, draft, lead, camp, "https://api", 30, now, dry_run=True)
    assert r["status"] == "test_sent"
    assert draft.status == "test_sent"


def test_linkedin_lead_is_staged_for_assisted_send():
    db = _FakeDB()
    draft = _draft()
    lead = _lead("linkedin", source_url="https://www.linkedin.com/posts/xyz")
    camp = _campaign()
    now = datetime.now(timezone.utc)
    r = _send_one_draft(db, draft, lead, camp, "https://api", 30, now, dry_run=False)
    assert r["status"] == "awaiting_manual"
    assert r["platform"] == "linkedin"
    assert r["deep_link"] == "https://www.linkedin.com/posts/xyz"
    assert draft.status == "awaiting_send"
    assert draft.send_platform == "linkedin"
    assert draft.send_deep_link == "https://www.linkedin.com/posts/xyz"
    # No send record / contact written while awaiting manual confirmation.
    assert db.added == []


def test_email_lead_without_address_is_skipped():
    db, draft, lead, camp = _FakeDB(), _draft(), _lead("google"), _campaign()
    now = datetime.now(timezone.utc)
    r = _send_one_draft(db, draft, lead, camp, "https://api", 30, now, dry_run=False)
    assert r["status"] == "skipped"
    assert r["reason"] == "no_email"
