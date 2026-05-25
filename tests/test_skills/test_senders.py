"""Unit tests for the outreach send-handler registry."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from aiplatform.skills.comms.senders import HANDLERS, VALID_SEND_PLATFORMS
from aiplatform.skills.comms.senders.base import SendRequest


def test_registry_has_expected_platforms():
    assert VALID_SEND_PLATFORMS == {"email", "linkedin", "instagram", "facebook"}


def test_linkedin_assisted_uses_source_url_as_deep_link():
    req = SendRequest(message_body="hi", venture="marketing_audit",
                      deep_link_hint="https://www.linkedin.com/posts/abc")
    res = HANDLERS["linkedin"].send(req, None)
    assert res.status == "awaiting_manual"
    assert res.provider == "manual"
    assert res.deep_link == "https://www.linkedin.com/posts/abc"
    assert res.instructions


def test_instagram_assisted_falls_back_to_profile():
    req = SendRequest(message_body="hi", venture="x", platform_username="@bob")
    res = HANDLERS["instagram"].send(req, None)
    assert res.status == "awaiting_manual"
    assert res.deep_link == "https://www.instagram.com/bob/"


def test_email_handler_maps_send_result(monkeypatch):
    import aiplatform.skills.comms.senders.email as email_mod
    monkeypatch.setattr(email_mod, "send_email",
                        lambda **kw: {"message_id": "abc123"})
    req = SendRequest(message_body="hello", venture="marketing_audit",
                      to_email="x@example.com", subject="Hi",
                      meta={"unsub_url": "u", "pixel_url": "p"})
    res = email_mod.send(req, None)
    assert res.status == "sent"
    assert res.provider == "resend"
    assert res.message_id == "abc123"


def test_email_handler_reports_failure(monkeypatch):
    import aiplatform.skills.comms.senders.email as email_mod
    monkeypatch.setattr(email_mod, "send_email", lambda **kw: {"error": "boom"})
    req = SendRequest(message_body="hello", venture="x", to_email="x@example.com")
    res = email_mod.send(req, None)
    assert res.status == "failed"
    assert res.error == "boom"


def test_email_handler_no_address_fails():
    req = SendRequest(message_body="hello", venture="x", to_email=None)
    res = HANDLERS["email"].send(req, None)
    assert res.status == "failed"
