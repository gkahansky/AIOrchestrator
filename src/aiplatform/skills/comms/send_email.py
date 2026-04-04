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
) -> dict:
    """
    Send an email via the Resend HTTP API.

    Args:
        to:           Recipient address (or comma-separated list)
        subject:      Email subject line
        body_html:    HTML body (required)
        attachments:  Optional list of local file paths to attach
        body_text:    Optional plain-text fallback (auto-stripped from HTML if omitted)

    Returns:
        {message_id, to, subject} on success, {error} on failure.
    """
    api_key   = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("EMAIL_FROM", "")

    if not api_key:
        return {"error": "RESEND_API_KEY must be set in environment."}
    if not from_addr:
        return {"error": "EMAIL_FROM must be set in environment."}

    recipients = [r.strip() for r in to.split(",")]

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

def _strip_html(html: str) -> str:
    """Very light HTML → plain text for the fallback part."""
    import re
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
