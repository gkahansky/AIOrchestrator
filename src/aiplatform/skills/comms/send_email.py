"""
Skill: send_email
Send an email via Gmail.

Status: Sprint 3 — not yet implemented.
Requires: GMAIL_ADDRESS, GMAIL_APP_PASSWORD env vars.
"""


def send_email(to: str, subject: str, body_html: str, attachments: list[str] = None) -> dict:
    """
    Send an email.

    Returns:
        { message_id, to, subject }
    """
    raise NotImplementedError("send_email is a Sprint 3 feature.")
