"""
Skill: send_email
Send a human-review notification email via Gmail SMTP.

Requires env vars:
    GMAIL_SENDER       — Gmail address used to send (e.g. yourshop@gmail.com)
    GMAIL_APP_PASSWORD — Gmail App Password (not your regular password)
    REVIEW_EMAIL_TO    — Recipient address(es), comma-separated

TLS port 587 (STARTTLS) is used. App Passwords are required when
2-Step Verification is enabled on the sending account.
"""

import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def send_review_email(
    subject: str,
    body_html: str,
    attachments: list[str] = None,
) -> dict:
    """
    Send a review-notification email.

    Args:
        subject:     Email subject line.
        body_html:   HTML body (plain-text fallback auto-generated).
        attachments: Optional list of local file paths to attach.

    Returns:
        { sent (bool), recipients (list[str]), error (str | None) }
    """
    sender   = os.environ.get("GMAIL_SENDER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    to_raw   = os.environ.get("REVIEW_EMAIL_TO", "").strip()

    if not sender or not password or not to_raw:
        raise EnvironmentError(
            "GMAIL_SENDER, GMAIL_APP_PASSWORD, and REVIEW_EMAIL_TO must all be set."
        )

    recipients = [r.strip() for r in to_raw.split(",") if r.strip()]

    msg = MIMEMultipart("mixed")
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject

    # Plain-text fallback (strip basic HTML tags)
    import re
    plain = re.sub(r"<[^>]+>", "", body_html).strip()
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain, "plain"))
    alt.attach(MIMEText(body_html, "html"))
    msg.attach(alt)

    # Attachments
    for file_path in (attachments or []):
        path = Path(file_path)
        if not path.exists():
            continue
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
        msg.attach(part)

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        return {"sent": True, "recipients": recipients, "error": None}
    except smtplib.SMTPException as exc:
        return {"sent": False, "recipients": recipients, "error": str(exc)}


def build_review_email_body(subject_data: dict, pdf_drive_link: str = None) -> str:
    """
    Build an HTML email body for a single listing review notification.

    Args:
        subject_data:   Subject dict (from Phase 2 or Phase 3 result).
        pdf_drive_link: Optional Drive link to the review-sheet PDF.

    Returns:
        HTML string.
    """
    slug        = subject_data.get("subject_id", "unknown")
    title       = subject_data.get("title_draft", "")
    price       = subject_data.get("price_usd", 0.0)
    tier        = subject_data.get("quality_tier", "standard")
    tags        = subject_data.get("etsy_tags", subject_data.get("target_keywords", []))
    tags_str    = ", ".join(tags) if tags else "—"
    drive_link  = pdf_drive_link or ""

    drive_section = ""
    if drive_link:
        drive_section = f"""
        <p>
          <a href="{drive_link}" style="background:#4a90d9;color:white;padding:8px 16px;
             border-radius:4px;text-decoration:none;">Open Review PDF in Drive</a>
        </p>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
      <h2 style="border-bottom:2px solid #4a90d9;padding-bottom:8px">
        🎨 New Etsy Listing Ready for Review
      </h2>
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:6px 0;color:#666;width:120px"><b>Slug</b></td>
            <td style="padding:6px 0">{slug}</td></tr>
        <tr><td style="padding:6px 0;color:#666"><b>Title</b></td>
            <td style="padding:6px 0">{title}</td></tr>
        <tr><td style="padding:6px 0;color:#666"><b>Price</b></td>
            <td style="padding:6px 0">${price:.2f} ({tier})</td></tr>
        <tr><td style="padding:6px 0;color:#666"><b>Tags</b></td>
            <td style="padding:6px 0;font-size:12px">{tags_str}</td></tr>
      </table>
      {drive_section}
      <p style="font-size:12px;color:#999;margin-top:24px">
        Sent by AIOrchestrator · Etsy Pipeline · Phase 5
      </p>
    </body></html>
    """
