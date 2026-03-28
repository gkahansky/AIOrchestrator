"""
Skill: send_email
Send an email via Gmail using SMTP with an app password.

Requires env vars:
    GMAIL_ADDRESS       — sender address (e.g. you@gmail.com)
    GMAIL_APP_PASSWORD  — 16-char Google App Password (not your account password)

To create a Gmail App Password:
    Google Account → Security → 2-Step Verification → App Passwords
"""

from __future__ import annotations

import logging
import mimetypes
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

log = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def send_email(
    to: str,
    subject: str,
    body_html: str,
    attachments: list[str] | None = None,
    body_text: str | None = None,
) -> dict:
    """
    Send an email via Gmail SMTP.

    Args:
        to:           Recipient address (or comma-separated list)
        subject:      Email subject line
        body_html:    HTML body (required)
        attachments:  Optional list of local file paths to attach
        body_text:    Optional plain-text fallback (auto-stripped from HTML if omitted)

    Returns:
        {message_id, to, subject} on success, {error} on failure.
    """
    sender  = os.environ.get("GMAIL_ADDRESS", "")
    app_pwd = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not sender or not app_pwd:
        return {"error": "GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in environment."}

    try:
        msg = MIMEMultipart("alternative") if not attachments else MIMEMultipart("mixed")
        msg["From"]    = sender
        msg["To"]      = to
        msg["Subject"] = subject

        # Plain-text fallback
        plain = body_text or _strip_html(body_html)
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        # Attachments
        for path_str in (attachments or []):
            path = Path(path_str)
            if not path.exists():
                log.warning("Attachment not found, skipping: %s", path)
                continue
            ctype, _ = mimetypes.guess_type(str(path))
            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
            with open(path, "rb") as f:
                part = MIMEBase(maintype, subtype)
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=path.name)
            msg.attach(part)

        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(sender, app_pwd)
            smtp.sendmail(sender, [r.strip() for r in to.split(",")], msg.as_string())

        message_id = msg.get("Message-ID", "")
        log.info("Email sent to %s — subject: %s", to, subject)
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
