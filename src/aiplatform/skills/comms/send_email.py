"""
Skill: send_email
Send an email via the Resend API (https://resend.com).

Requires env vars:
    RESEND_API_KEY   — API key from resend.com dashboard
    EMAIL_FROM       — verified sender address (e.g. noreply@yourdomain.com)
                       or use the Resend sandbox address for testing:
                       onboarding@resend.dev

Resend is used instead of SMTP because Railway blocks outbound port 587.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


def send_email(
    to: str,
    subject: str,
    body_html: str,
    attachments: list[str] | None = None,
    body_text: str | None = None,
    consent_type: str = "transactional",
    skip_suppression: bool = False,
) -> dict:
    """
    Send an email via the Resend HTTP API.

    Args:
        to:               Recipient address (or comma-separated list)
        subject:          Email subject line
        body_html:        HTML body (required)
        attachments:      Optional list of local file paths to attach
        body_text:        Optional plain-text fallback (auto-stripped from HTML if omitted)
        consent_type:     transactional | marketing | outreach — categorises the message
                          for the consent ledger. Suppression applies regardless.
        skip_suppression: Set True only for purely internal/operator mail (digests,
                          error alerts) that must never be silently dropped.

    Returns:
        {message_id, to, subject} on success, {error} on failure,
        {suppressed: True, ...} when every recipient is on the suppression list.

    Compliance (CRM module H-11): every recipient is checked against the CRM
    suppression list (unsubscribed / erased / do-not-contact window) before the
    Resend call. Suppressed recipients are dropped. The lookup fails open (sends
    anyway, with a loud error log) if the database is unreachable, so a DB blip
    never blocks transactional delivery.
    """
    recipients = [r.strip() for r in to.split(",") if r.strip()]

    if not skip_suppression:
        recipients = _filter_suppressed(recipients)
        if not recipients:
            log.warning("send_email: all recipients suppressed for subject %r", subject)
            return {"suppressed": True, "to": to, "subject": subject}

    api_key   = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("EMAIL_FROM", "")

    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set — email cannot be sent.")
    if not from_addr:
        raise RuntimeError("EMAIL_FROM is not set — email cannot be sent.")

    payload: dict = {
        "from":    from_addr,
        "to":      recipients,
        "subject": subject,
        "html":    body_html,
    }

    if body_text:
        payload["text"] = body_text

    # Attachments — Resend accepts base64-encoded content
    if attachments:
        encoded = []
        for path_str in attachments:
            path = Path(path_str)
            if not path.exists():
                log.warning("Attachment not found, skipping: %s", path)
                continue
            ctype, _ = mimetypes.guess_type(str(path))
            with open(path, "rb") as f:
                encoded.append({
                    "filename":     path.name,
                    "content":      base64.b64encode(f.read()).decode(),
                    "content_type": ctype or "application/octet-stream",
                })
        if encoded:
            payload["attachments"] = encoded

    try:
        resp = requests.post(
            _RESEND_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            timeout=30,
        )
        data = resp.json()
        if resp.status_code not in (200, 201):
            err = data.get("message") or data.get("error") or str(data)
            log.error("send_email failed (%s): %s", resp.status_code, err)
            return {"error": err}

        message_id = data.get("id", "")
        log.info("Email sent to %s — subject: %s  id: %s", to, subject, message_id)
        return {"message_id": message_id, "to": to, "subject": subject}

    except Exception as exc:
        log.error("send_email failed: %s", exc)
        return {"error": str(exc)}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _filter_suppressed(recipients: list[str]) -> list[str]:
    """Drop recipients on the CRM suppression list. Fails open on DB error."""
    try:
        from aiplatform.database.crm_ops import is_suppressed
    except Exception as exc:  # import-time failure — never block delivery
        log.error("send_email: suppression check unavailable (%s) — sending anyway", exc)
        return recipients

    allowed = []
    for r in recipients:
        try:
            if is_suppressed(r):
                log.warning("send_email: recipient suppressed, skipping: %s", r)
                continue
        except Exception as exc:  # DB blip — fail open for this recipient
            log.error("send_email: suppression lookup failed for %s (%s) — sending", r, exc)
        allowed.append(r)
    return allowed


def _strip_html(html: str) -> str:
    """Very light HTML → plain text for the fallback part."""
    import re
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
