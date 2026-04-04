"""
Skill: fiverr_email_parser
Poll Gmail for unread Fiverr order emails, parse with Claude, create orders.

Requires env vars:
    GOOGLE_TOKEN_PATH         — path to google_token.json (OAuth user token)
    ANTHROPIC_API_KEY         — for Claude parsing
    FIVERR_PODCAST_GIG_ID     — keyword in subject that identifies podcast orders
                                (default: "Podcast")
    FIVERR_AUDIT_GIG_ID       — keyword that identifies audit orders
                                (default: "Marketing Audit")
    FIVERR_PROCESSED_LABEL    — Gmail label to apply to processed emails
                                (default: "fiverr-processed")

Gmail OAuth scope required: https://www.googleapis.com/auth/gmail.modify
(In addition to existing Drive scope — requires re-authentication if not yet granted.)
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

_FIVERR_SENDER = "notifications@fiverr.com"
_PODCAST_KEYWORD = None   # resolved at runtime from env
_AUDIT_KEYWORD   = None


def _get_gmail_service():
    """Build and return an authenticated Gmail API service."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_path = os.environ.get("GOOGLE_TOKEN_PATH", "./google_token.json")
    if not Path(token_path).exists():
        raise FileNotFoundError(f"Google token not found at {token_path}")

    creds = Credentials.from_authorized_user_file(token_path)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _get_or_create_label(service, label_name: str) -> str:
    """Return label ID, creating the label if it doesn't exist."""
    result = service.users().labels().list(userId="me").execute()
    for lbl in result.get("labels", []):
        if lbl["name"].lower() == label_name.lower():
            return lbl["id"]
    created = service.users().labels().create(
        userId="me", body={"name": label_name, "labelListVisibility": "labelShow"}
    ).execute()
    return created["id"]


def _get_message_body(service, msg_id: str) -> str:
    """Return decoded plain-text body of a Gmail message."""
    import base64
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    payload = msg.get("payload", {})

    def _extract(part):
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            data = part.get("body", {}).get("data", "")
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        for sub in part.get("parts", []):
            result = _extract(sub)
            if result:
                return result
        return ""

    return _extract(payload)


def _parse_order_with_claude(email_body: str, service_type: str) -> dict | None:
    """
    Use Claude to extract structured order data from a Fiverr notification email.
    Returns a dict ready to pass to the pipeline, or None if parsing fails.
    """
    from anthropic import Anthropic

    client = Anthropic()

    if service_type == "podcast":
        fields = (
            "buyer_username, order_id, tier (starter/standard/premium), "
            "audio_url (if provided in requirements), show_name, episode_title, host_name, "
            "client_email (if visible), delivery_due (ISO date if visible)"
        )
    else:  # audit
        fields = (
            "buyer_username, order_id, tier (snapshot/full/premium), "
            "url (the website URL to audit), client_email (if visible), "
            "delivery_due (ISO date if visible), competitor_urls (list, if provided)"
        )

    prompt = (
        f"Extract the following fields from this Fiverr order notification email. "
        f"Return ONLY a JSON object with these keys: {fields}. "
        f"Use null for any field not found. Do not include any other text.\n\n"
        f"EMAIL:\n{email_body[:3000]}"
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as exc:
        log.error("Claude parse failed: %s", exc)
        return None


def parse_fiverr_inbox() -> dict:
    """
    Main entry point. Searches Gmail for unread Fiverr order emails,
    parses each one, creates the appropriate order in the system.

    Returns summary: {processed: N, skipped: M, errors: [...]}
    """
    podcast_keyword = os.environ.get("FIVERR_PODCAST_GIG_ID", "Podcast")
    audit_keyword   = os.environ.get("FIVERR_AUDIT_GIG_ID", "Marketing Audit")
    processed_label = os.environ.get("FIVERR_PROCESSED_LABEL", "fiverr-processed")

    try:
        service = _get_gmail_service()
    except Exception as exc:
        log.error("Gmail auth failed: %s", exc)
        return {"error": str(exc), "processed": 0}

    label_id = _get_or_create_label(service, processed_label)

    # Search for unread Fiverr order emails not yet processed
    query = f"from:{_FIVERR_SENDER} is:unread -label:{processed_label} subject:order"
    result = service.users().messages().list(userId="me", q=query, maxResults=20).execute()
    messages = result.get("messages", [])

    processed = 0
    errors = []

    for msg_ref in messages:
        msg_id = msg_ref["id"]
        try:
            body = _get_message_body(service, msg_id)

            # Determine service type from subject/body
            subject_result = service.users().messages().get(
                userId="me", id=msg_id, format="metadata",
                metadataHeaders=["Subject"],
            ).execute()
            headers = {h["name"]: h["value"] for h in subject_result.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "")

            if podcast_keyword.lower() in subject.lower() or podcast_keyword.lower() in body.lower():
                service_type = "podcast"
            elif audit_keyword.lower() in subject.lower() or audit_keyword.lower() in body.lower():
                service_type = "audit"
            else:
                log.info("Fiverr email %s — unrecognised service type, skipping", msg_id)
                _mark_processed(service, msg_id, label_id)
                continue

            parsed = _parse_order_with_claude(body, service_type)
            if not parsed:
                errors.append({"msg_id": msg_id, "error": "Claude parse returned None"})
                continue

            _create_order(parsed, service_type)
            _mark_processed(service, msg_id, label_id)
            processed += 1
            log.info("Fiverr order created: %s (%s)", parsed.get("order_id"), service_type)

        except Exception as exc:
            log.error("Error processing Gmail message %s: %s", msg_id, exc)
            errors.append({"msg_id": msg_id, "error": str(exc)})

    log.info("Fiverr inbox check complete: %d processed, %d errors", processed, len(errors))
    return {"processed": processed, "skipped": len(messages) - processed - len(errors), "errors": errors}


def _mark_processed(service, msg_id: str, label_id: str) -> None:
    """Mark email as read and apply the processed label."""
    try:
        service.users().messages().modify(
            userId="me",
            id=msg_id,
            body={
                "addLabelIds": [label_id],
                "removeLabelIds": ["UNREAD"],
            },
        ).execute()
    except Exception as exc:
        log.warning("Failed to label message %s: %s", msg_id, exc)


def _create_order(parsed: dict, service_type: str) -> None:
    """Create an order in the system from parsed Fiverr data."""
    from aiplatform.database.job_ops import upsert_job

    order_id = f"fiverr-{parsed.get('order_id') or uuid.uuid4().hex[:8]}"

    if service_type == "podcast":
        from aiplatform.worker import run_podcast_order as celery_task

        order = {
            "order_id":      order_id,
            "audio_url":     parsed.get("audio_url") or "",
            "tier":          parsed.get("tier") or "standard",
            "show_name":     parsed.get("show_name") or "",
            "episode_title": parsed.get("episode_title") or "",
            "host_name":     parsed.get("host_name") or "",
            "client_email":  parsed.get("client_email") or "",
            "source":        "fiverr",
            "fiverr_buyer":  parsed.get("buyer_username") or "",
            "status":        "pending",
        }
        upsert_job(order, "content_studio")
        task = celery_task.delay(order)
        upsert_job(order, "content_studio", celery_task_id=task.id)
        log.info("Podcast order queued: %s", order_id)

    else:  # audit
        from aiplatform.worker import run_audit_order as celery_task

        order = {
            "order_id":        order_id,
            "url":             parsed.get("url") or "",
            "tier":            parsed.get("tier") or "full",
            "client_email":    parsed.get("client_email") or "",
            "competitor_urls": parsed.get("competitor_urls") or [],
            "source":          "fiverr",
            "fiverr_buyer":    parsed.get("buyer_username") or "",
            "status":          "pending",
        }
        upsert_job(order, "marketing_audit")
        task = celery_task.delay(order)
        upsert_job(order, "marketing_audit", celery_task_id=task.id)
        log.info("Audit order queued: %s", order_id)
