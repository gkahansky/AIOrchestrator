"""
Send-handler contract — shared types for the outreach send registry.

Each platform handler exposes a single function:
    send(req: SendRequest, config: dict) -> SendResult

Handlers are venture-agnostic and stateless: they receive everything they need
on the SendRequest and return a SendResult. They never touch the database — all
persistence (send records, contacts, draft status) is the caller's job.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SendRequest:
    """Everything a handler needs to deliver (or stage) one message."""
    message_body: str
    venture: str
    to_email: str | None = None
    platform_username: str | None = None
    subject: str | None = None
    deep_link_hint: str | None = None   # lead.source_url — the post/profile to reply on
    lead_name: str | None = None
    # Caller-injected extras, e.g. {"pixel_url": ..., "unsub_url": ...} for email.
    meta: dict = field(default_factory=dict)


@dataclass
class SendResult:
    """Outcome of a send attempt.

    status:
      sent            — delivered now (email, or a future provider API)
      awaiting_manual — staged for assisted send; operator must send + confirm
      failed          — delivery failed; caller leaves the draft approved
    """
    status: str
    message_id: str = ""    # provider/Resend id when actually delivered
    deep_link: str = ""     # URL the operator opens to send manually (assisted)
    instructions: str = ""  # short operator guidance for assisted send
    error: str = ""
    provider: str = ""      # "resend" | "manual" | "unipile" | ...
