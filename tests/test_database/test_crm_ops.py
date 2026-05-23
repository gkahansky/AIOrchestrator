"""
Unit tests for the pure (DB-free) logic in aiplatform.database.crm_ops.

DB-touching helpers (upsert_contact, merge_contacts, etc.) require Postgres and
are exercised by the integration verification, not here — importing the module
does not open a connection, so these run anywhere.
"""
import pytest

from aiplatform.database import crm_ops as c


def test_email_hash_is_deterministic_and_case_insensitive():
    a = c.email_hash("Foo@Example.com")
    b = c.email_hash("  foo@example.com ")
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_advance_stage_moves_forward():
    assert c._advance_stage("lead", "customer") == "customer"
    assert c._advance_stage("sample", "repeat") == "repeat"


def test_advance_stage_never_downgrades():
    assert c._advance_stage("customer", "lead") == "customer"
    assert c._advance_stage("repeat", "sample") == "repeat"


def test_advance_stage_terminal_is_sticky():
    assert c._advance_stage("unsubscribed", "customer") == "unsubscribed"
    assert c._advance_stage("erased", "repeat") == "erased"


def test_advance_stage_dormant_reactivates():
    assert c._advance_stage("dormant", "customer") == "customer"


def test_advance_stage_to_special_stage():
    assert c._advance_stage("customer", "unsubscribed") == "unsubscribed"
    assert c._advance_stage("lead", "dormant") == "dormant"


def test_validate_outbound_body_requires_unsubscribe():
    with pytest.raises(c.MissingUnsubscribe):
        c.validate_outbound_body("Hello, no opt-out here.")


def test_validate_outbound_body_passes_with_token():
    c.validate_outbound_body("<a href='/api/outreach/unsubscribe/x'>Unsubscribe</a>")
    c.validate_outbound_body("Reply STOP or click unsubscribe below.")


def test_legacy_status_mapping():
    assert c._legacy_status("customer") == "purchased"
    assert c._legacy_status("repeat") == "purchased"
    assert c._legacy_status("unsubscribed") == "unsubscribed"
    assert c._legacy_status("lead") == "approached"
    assert c._legacy_status("sample") == "inquired"
