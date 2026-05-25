"""
Email send handler — delivers via Resend (wraps the send_email skill).

meta keys (injected by the caller):
    pixel_url  — open-tracking pixel URL (optional)
    unsub_url  — unsubscribe link URL (optional)
"""
from __future__ import annotations

from aiplatform.skills.comms.send_email import send_email
from aiplatform.skills.comms.senders.base import SendRequest, SendResult


def _build_html(message_body: str, unsub_url: str | None, pixel_url: str | None) -> str:
    body = message_body.replace("{{UNSUBSCRIBE_URL}}", unsub_url or "")
    parts = [f"<p>{body.replace(chr(10), '<br>')}</p>"]
    if unsub_url:
        parts.append(
            f'<p style="font-size:11px;color:#999;"><a href="{unsub_url}">Unsubscribe</a></p>'
        )
    if pixel_url:
        parts.append(
            f'<img src="{pixel_url}" width="1" height="1" style="display:none" alt="" />'
        )
    return "\n".join(parts)


def send(req: SendRequest, config: dict | None = None) -> SendResult:
    if not req.to_email:
        return SendResult(status="failed", provider="resend",
                          error="no email address on lead")

    unsub_url = req.meta.get("unsub_url")
    pixel_url = req.meta.get("pixel_url")
    body_html = _build_html(req.message_body, unsub_url, pixel_url)
    body_text = req.message_body.replace("{{UNSUBSCRIBE_URL}}", unsub_url or "")

    subject = req.subject or f"Quick question about your {req.venture.replace('_', ' ')}"
    result = send_email(
        to=req.to_email, subject=subject,
        body_html=body_html, body_text=body_text,
    )
    if result.get("error"):
        return SendResult(status="failed", provider="resend", error=result["error"])
    return SendResult(status="sent", provider="resend",
                      message_id=result.get("message_id", ""))
