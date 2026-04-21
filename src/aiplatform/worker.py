"""
Celery worker — one task per venture pipeline.

This is the canonical worker module. The webapp re-exports from here.

Start locally:
    celery -A aiplatform.worker worker --loglevel=info

On Railway: the separate "worker" service runs this command.

Approval gate pattern
─────────────────────
When a pipeline reaches review_pending it writes to DB and returns normally.
The Celery task also sets a Redis key:

    approval_gate:{job_id} = "pending"

POST /api/jobs/{id}/approve updates that key to "approve" and re-dispatches
the same Celery task with order["status"] = "approved".  The pipeline's
checkpoint logic (if order["status"] in (..., "review_pending")) re-enters
the review phase, sees "approved", and continues to delivery.

This keeps CLI scripts unchanged — they call pipeline.run_order() directly
without Redis.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from celery import Celery


def _materialise_google_credentials() -> None:
    """Write Google credential env vars to disk so Drive auth can find them."""
    import base64

    # OAuth user token — preferred, works with personal Google Drive
    token_b64 = os.environ.get("GOOGLE_DRIVE_TOKEN_JSON", "")
    if token_b64:
        dest = Path(os.environ.get("GOOGLE_TOKEN_PATH", "./google_token.json"))
        try:
            dest.write_bytes(base64.b64decode(token_b64))
            print(f"[startup] Google OAuth token written to {dest}", flush=True)
        except Exception as exc:
            print(f"[startup] ERROR: Failed to write Google OAuth token: {exc}", flush=True)
    else:
        print("[startup] WARNING: GOOGLE_DRIVE_TOKEN_JSON is not set — Drive uploads will fall back to service account (may fail on personal Drive folders)", flush=True)

    # Service account — fallback for non-Drive operations
    sa_b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if sa_b64:
        dest = Path(os.environ.get("GOOGLE_CREDENTIALS_PATH", "./google_credentials.json"))
        try:
            dest.write_bytes(base64.b64decode(sa_b64))
            print(f"[startup] Google service account written to {dest}", flush=True)
        except Exception as exc:
            print(f"[startup] ERROR: Failed to write Google service account: {exc}", flush=True)
    else:
        print("[startup] WARNING: GOOGLE_SERVICE_ACCOUNT_JSON is not set — service account fallback unavailable", flush=True)

_materialise_google_credentials()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aiplatform",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,           # re-queue if worker dies mid-task
    worker_prefetch_multiplier=1,  # one task at a time per worker thread
    result_expires=86400,          # 24 hours
    beat_schedule={
        # Daily — purge SecurityAudit records and associated data older than 30 days
        "security-audit-data-retention": {
            "task": "platform.purge_old_security_audits",
            "schedule": 86400,           # 24 hours
            "options": {"expires": 3600},
        },
        # Every Monday at 08:00 UTC
        "weekly-finance-digest": {
            "task": "platform.weekly_digest",
            "schedule": 604800,          # 7 days in seconds — use crontab in prod
            "options": {"expires": 3600},
        },
        # EO Weekly Review (Sunday 21:00 schedule emulated)
        "eo-weekly-review": {
            "task": "platform.eo_weekly_review",
            "schedule": 604800,
            "options": {"expires": 3600},
        },
        # DISABLED — Google token lacks gmail.modify scope (only Drive scopes granted).
        # Re-enable after re-running OAuth flow with gmail.modify scope and updating GOOGLE_TOKEN_PATH.
        # "fiverr-email-check": {
        #     "task": "platform.check_fiverr_emails",
        #     "schedule": 900,
        #     "options": {"expires": 300},
        # },
        # Every 10 min — re-queue market research sessions stuck in in-progress states
        "market-research-watchdog": {
            "task": "platform.market_research_watchdog",
            "schedule": 600,             # 10 minutes
            "options": {"expires": 300},
        },
        # Hourly — fetch spend from vendor APIs; auto-pause campaigns that hit 100% budget
        "campaign-budget-monitor": {
            "task": "platform.monitor_campaign_budgets",
            "schedule": 3600,            # 1 hour
            "options": {"expires": 600},
        },
        # Weekly — AI insight engine for all active campaigns
        "campaign-weekly-insights": {
            "task": "platform.generate_campaign_insights",
            "schedule": 604800,          # 7 days
            "options": {"expires": 3600},
        },
    },
    beat_schedule_filename="/tmp/celerybeat-schedule",
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _slack_alert_failure(venture: str, order_id: str | None, exc: Exception, phase: int | None = None) -> None:
    """Post a failure alert to Slack. Best-effort — never raises."""
    try:
        from aiplatform.skills.comms.send_slack import send_slack
        channel = os.environ.get("SLACK_ALERTS_CHANNEL") or os.environ.get("SLACK_REVIEW_CHANNEL", "#platform-alerts")
        phase_str = f" · Phase {phase}" if phase else ""
        order_str = order_id or "unknown"
        admin_url = f"https://planBadmin.com"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":rotating_light: *Pipeline failure* — `{venture}`{phase_str}\n"
                        f"*Order:* `{order_str}`\n"
                        f"*Error:* {str(exc)[:300]}"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open Dashboard"},
                        "url": admin_url,
                    }
                ],
            },
        ]
        send_slack(channel=channel, text=f"Pipeline failure — {venture} · {order_str}", blocks=blocks)
    except Exception:
        pass


def _slack_alert_new_order(venture: str, order_id: str, detail: str = "") -> None:
    """Post a new-order alert to Slack. Best-effort — never raises."""
    try:
        from aiplatform.skills.comms.send_slack import send_slack
        channel = os.environ.get("SLACK_ALERTS_CHANNEL", "#platform-alerts")
        label = venture.replace("_", " ").title()
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":new: *New order* — `{label}`\n"
                        f"*Order:* `{order_id}`"
                        + (f"\n{detail}" if detail else "")
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open Dashboard"},
                        "url": "https://planBadmin.com",
                    }
                ],
            },
        ]
        send_slack(channel=channel, text=f"New order — {label} · {order_id}", blocks=blocks)
    except Exception:
        pass


def _slack_alert_review_needed(venture: str, order_id: str, detail: str = "") -> None:
    """Post a review-needed alert to Slack. Best-effort — never raises."""
    try:
        from aiplatform.skills.comms.send_slack import send_slack
        channel = os.environ.get("SLACK_ALERTS_CHANNEL", "#platform-alerts")
        label = venture.replace("_", " ").title()
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":eyes: *Review needed* — `{label}`\n"
                        f"*Order:* `{order_id}`"
                        + (f"\n{detail}" if detail else "")
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Review in Dashboard"},
                        "url": "https://planBadmin.com",
                        "style": "primary",
                    }
                ],
            },
        ]
        send_slack(channel=channel, text=f"Review needed — {label} · {order_id}", blocks=blocks)
    except Exception:
        pass


def _mark_failed(order_id: str | None, venture: str, error: str) -> None:
    """Write a failure status to the DB — best-effort, never raises."""
    if not order_id:
        return
    try:
        from aiplatform.database.models import Job
        from aiplatform.database.session import get_session

        with get_session() as db:
            job = db.query(Job).filter(
                Job.venture == venture,
                Job.input_data["order_id"].astext == order_id,
            ).first()
            if job:
                job.status = "failed"
                job.error_message = error[:500]
    except Exception:
        pass


def _set_approval_gate(job_id: str, signal: str) -> None:
    """Write an approval signal to Redis so the API + frontend can poll."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(REDIS_URL)
        r.set(f"approval_gate:{job_id}", signal, ex=86400)
    except Exception:
        pass


def _get_job_id(order: dict, venture: str) -> str | None:
    """Look up the DB job UUID for an order — returns None if not found."""
    try:
        from aiplatform.database.models import Job
        from aiplatform.database.session import get_session

        with get_session() as db:
            job = db.query(Job).filter(
                Job.venture == venture,
                Job.input_data["order_id"].astext == order.get("order_id", ""),
            ).first()
            return str(job.id) if job else None
    except Exception:
        return None


# ── Etsy venture ───────────────────────────────────────────────────────────────
#
# Automated pipeline flow:
#   Phase 1 — manual trigger (one-time theme research)
#   Phase 2 — manual trigger (select theme) → auto-chains Phase 3 per subject
#   Phase 3 — auto (image gen) → auto-chains Phase 4
#   Phase 4 — auto (packaging) → auto-chains Phase 6 directly
#   Phase 5 — skipped (human review moved to Etsy draft approval in the shop)
#   Phase 6 — auto-triggered by Phase 4; human reviews and publishes in Etsy
#
# Each phase stores its full result in output_data so downstream phases
# can retrieve subject + phase3_result + phase4_result from the DB.

def _etsy_update_job(job_id: str, status: str, result: dict, dt) -> None:
    """Update Etsy job row status + output_data. Best-effort, never raises."""
    try:
        from aiplatform.database.models import Job
        from aiplatform.database.session import get_session
        with get_session() as db:
            job = db.query(Job).filter(
                Job.venture == "etsy",
                Job.input_data["order_id"].astext == job_id,
            ).first()
            if job:
                job.status = status
                job.output_data = result
                if status in ("completed", "review_pending", "failed") and not job.completed_at:
                    job.completed_at = dt
    except Exception:
        pass


@celery_app.task(bind=True, name="etsy.run_phase", max_retries=2)
def run_etsy_phase(self, phase: int, params: dict) -> dict:
    """
    Run a single Etsy pipeline phase.

    Phases 1 & 2 are triggered manually from the UI.
    Phases 3, 4, 5 are chained automatically.
    Phase 6 is triggered by the /approve endpoint.
    """
    import uuid
    from datetime import datetime, timezone

    job_id = params.get("job_id") or str(uuid.uuid4())
    params["job_id"] = job_id
    now = datetime.now(timezone.utc)

    order = {
        "order_id": job_id,
        "phase":    phase,
        "status":   "running",
        **{k: v for k, v in params.items() if k != "job_id"},
    }

    # Alert on new order (phase 1 first attempt only)
    if phase == 1 and self.request.retries == 0:
        _slack_alert_new_order("etsy", job_id)

    try:
        from aiplatform.database.job_ops import upsert_job
        upsert_job(order, "etsy", celery_task_id=self.request.id)
    except Exception:
        pass

    try:
        from ventures.etsy import pipeline as etsy_pipeline

        phase_fns = {
            1: etsy_pipeline.run_phase_1,
            2: etsy_pipeline.run_phase_2,
            3: etsy_pipeline.run_phase_3,
            4: etsy_pipeline.run_phase_4,
            5: etsy_pipeline.run_phase_5_notify,
            6: etsy_pipeline.run_phase_6,
            7: etsy_pipeline.run_phase_7,
        }

        fn = phase_fns.get(phase)
        if fn is None:
            raise ValueError(f"Unknown Etsy phase: {phase}")

        pipeline_params = {k: v for k, v in params.items() if k not in ("job_id",)}
        result = fn(**pipeline_params)

        # ── Phase 2 → queue Phase 3 for every subject ──────────────────────────
        if phase == 2 and result.get("subjects"):
            _etsy_update_job(job_id, "completed", result, now)
            for subject in result["subjects"]:
                run_etsy_phase.delay(3, {"subject": subject})
            return {"phase": 2, "status": "completed", "job_id": job_id, "result": result}

        # ── Phase 3 → queue Phase 4 for same subject ───────────────────────────
        if phase == 3:
            _etsy_update_job(job_id, "completed", result, now)
            subject = params.get("subject", {})
            run_etsy_phase.delay(4, {"subject": subject, "phase3_result": result})
            return {"phase": 3, "status": "completed", "job_id": job_id, "result": result}

        # ── Phase 4 → queue Phase 6 directly (Phase 5 review gate removed) ──────
        if phase == 4:
            full_result = {
                **result,
                "subject":       params.get("subject"),
                "phase3_result": params.get("phase3_result"),
            }
            _etsy_update_job(job_id, "completed", full_result, now)
            subject      = params.get("subject", {})
            phase3_result = params.get("phase3_result", {})
            run_etsy_phase.delay(6, {
                "subject":       subject,
                "phase3_result": phase3_result,
                "phase4_result": result,
            })
            return {"phase": 4, "status": "completed", "job_id": job_id, "result": full_result}

        # ── Phase 5 — kept for manual invocation but no longer auto-chained ────
        if phase == 5:
            _etsy_update_job(job_id, "completed", result, now)
            return {"phase": 5, "status": "completed", "job_id": job_id, "result": result}

        # ── All other phases (1, 6, 7) — complete normally ────────────────────
        _etsy_update_job(job_id, "completed", result, now)
        return {"phase": phase, "status": "completed", "job_id": job_id, "result": result}

    except Exception as exc:
        try:
            from aiplatform.database.models import Job
            from aiplatform.database.session import get_session
            with get_session() as db:
                job = db.query(Job).filter(
                    Job.venture == "etsy",
                    Job.input_data["order_id"].astext == job_id,
                ).first()
                if job:
                    job.status = "failed"
                    job.error_message = str(exc)[:500]
        except Exception:
            pass

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        _slack_alert_failure("etsy", job_id, exc, phase=phase)
        raise


# ── Marketing Audit venture ────────────────────────────────────────────────────

@celery_app.task(bind=True, name="audit.run_order", max_retries=2)
def run_audit_order(self, order: dict) -> dict:
    """
    Run a marketing audit order through all pipeline phases.

    The pipeline pauses naturally at review_pending — it returns the order dict
    with status="review_pending".  This task then sets the Redis approval gate
    key to "pending" so the frontend can poll its state.

    On re-dispatch from POST /api/jobs/{id}/approve, the order arrives with
    status="approved" and the pipeline continues directly to delivery.
    """
    order_id = order.get("order_id", "")
    # Only alert on first attempt (not retries)
    if self.request.retries == 0:
        _slack_alert_new_order(
            "marketing_audit", order_id,
            detail=f"URL: {order.get('url', '')}  ·  Tier: {order.get('tier', '')}",
        )

    try:
        from ventures.marketing_audit import pipeline as audit_pipeline

        result = audit_pipeline.run_order(order)

        # If pipeline paused at review gate, signal Redis + alert Slack
        if result.get("status") == "review_pending":
            job_id = _get_job_id(order, "marketing_audit")
            if job_id:
                _set_approval_gate(job_id, "pending")
            _slack_alert_review_needed(
                "marketing_audit", order_id,
                detail=f"URL: {order.get('url', '')}  ·  Tier: {order.get('tier', '')}",
            )

        return {
            "order_id": order_id,
            "status":   result.get("status"),
            "result":   result,
        }

    except Exception as exc:
        _mark_failed(order_id, "marketing_audit", str(exc))
        # Scrape failures are deterministic — retrying the same blocked URL wastes time.
        is_scrape_failure = "Could not fetch page" in str(exc) or "Failed to scrape" in str(exc)
        if not is_scrape_failure and self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120)
        _slack_alert_failure("marketing_audit", order_id, exc)
        raise


# ── Marketing Audit — free sample (public website) ────────────────────────────

@celery_app.task(bind=True, name="audit.run_sample", max_retries=1)
def run_audit_sample(self, order: dict) -> dict:
    """
    Run a marketing audit sample for a website visitor (no payment, no review gate).
    Generates the censored sample PDF and emails it to order["sample_email"].
    """
    sample_email = order.get("sample_email", "")
    try:
        from ventures.marketing_audit import pipeline as audit_pipeline
        from aiplatform.skills.comms.send_email import send_email
        from aiplatform.database.crm_ops import can_send_sample, log_contact_message
        from aiplatform.database.crm_ops import can_send_sample, log_contact_message
        from pathlib import Path

        if sample_email and not can_send_sample(sample_email, "marketing_audit"):
            return {
                "order_id": order.get("order_id"), 
                "status": "skipped_throttle", 
                "error": "Sample limit reached (30 days)"
            }

        # Force sample-only mode and skip human review
        order["report_type"] = "sample"
        order["auto_approve"] = True
        order["client_email"] = ""   # pipeline must not send a client delivery email

        result = audit_pipeline.run_order(order)

        sample_pdf   = result.get("sample_pdf_path", "")
        drive_link   = result.get("drive_sample_PDF_link", "") or result.get("drive_sample_pdf_link", "")

        if sample_email:
            url = result.get("url", order.get("url", "your website"))

            # Include Drive link in body if we have one (works even if local file is gone)
            drive_section = (
                f'<p><a href="{drive_link}">View your sample report in Google Drive &rarr;</a></p>'
                if drive_link else ""
            )
            body = (
                f"<p>Hi there,</p>"
                f"<p>Here's your free marketing audit sample for <b>{url}</b>.</p>"
                f"<p>The sample shows your overall score and a selection of findings. "
                f"The full audit includes all findings, a complete action plan, competitor benchmarking, "
                f"and before/after copy examples.</p>"
                f"{drive_section}"
                f"<p><b>Interested in the full report?</b> Visit "
                f'<a href="https://echoforge.biz">echoforge.biz</a> to order.</p>'
                f"<p>— EchoForge</p>"
            )
            # Attach PDF if local file is still available; fall back to link-only
            attachments = [sample_pdf] if (sample_pdf and Path(sample_pdf).exists()) else []
            result_send = send_email(
                to=sample_email,
                subject=f"Your Free Marketing Audit Sample — {url}",
                body_html=body,
                attachments=attachments,
            )
            if isinstance(result_send, dict) and result_send.get("error"):
                raise RuntimeError(f"send_email failed: {result_send['error']}")

            log_contact_message(
                email=sample_email,
                venture="marketing_audit",
                message_type="sample",
                subject=f"Your Free Marketing Audit Sample — {url}",
                body_snippet=body[:200],
                message_id=result_send.get("message_id") if isinstance(result_send, dict) else None
            )

            # Schedule nurture follow-ups
            from datetime import datetime, timezone, timedelta
            run_nurture_email.apply_async(
                args=[sample_email, "audit", order.get("order_id", ""), 3],
                eta=datetime.now(timezone.utc) + timedelta(days=3),
            )
            run_nurture_email.apply_async(
                args=[sample_email, "audit", order.get("order_id", ""), 7],
                eta=datetime.now(timezone.utc) + timedelta(days=7),
            )

        return {"order_id": order.get("order_id"), "status": "sample_delivered"}

    except Exception as exc:
        _mark_failed(order.get("order_id"), "marketing_audit", str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        _slack_alert_failure("audit_sample", order.get("order_id"), exc)
        raise


# ── Content Studio venture ─────────────────────────────────────────────────────

@celery_app.task(bind=True, name="podcast.run_order", max_retries=2)
def run_podcast_order(self, order: dict) -> dict:
    """
    Run a podcast show notes order through all pipeline phases.

    Same approval gate pattern as run_audit_order.
    """
    order_id = order.get("order_id", "")
    if self.request.retries == 0:
        _slack_alert_new_order(
            "content_studio", order_id,
            detail=f"Show: {order.get('show_name', '')}  ·  Tier: {order.get('tier', '')}",
        )

    try:
        from ventures.content_studio import pipeline as podcast_pipeline

        result = podcast_pipeline.run_order(order)

        if result.get("status") == "review_pending":
            job_id = _get_job_id(order, "content_studio")
            if job_id:
                _set_approval_gate(job_id, "pending")
            _slack_alert_review_needed(
                "content_studio", order_id,
                detail=f"Show: {order.get('show_name', '')}  ·  Tier: {order.get('tier', '')}",
            )

        return {
            "order_id": order_id,
            "status":   result.get("status"),
            "result":   result,
        }

    except Exception as exc:
        _mark_failed(order.get("order_id"), "content_studio", str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120)
        _slack_alert_failure("content_studio", order.get("order_id"), exc)
        raise


# ── Content Studio — free sample (public website) ─────────────────────────────

@celery_app.task(bind=True, name="podcast.run_sample", max_retries=1)
def run_podcast_sample(self, order: dict) -> dict:
    """
    Run a podcast sample for a website visitor (no payment, no review gate).
    Transcribes the uploaded audio (stored in Drive), generates content,
    and emails the watermarked sample PDF to order["sample_email"].
    """
    sample_email = order.get("sample_email", "")
    try:
        from ventures.content_studio import pipeline as podcast_pipeline
        from aiplatform.skills.comms.send_email import send_email
        from aiplatform.database.crm_ops import can_send_sample, log_contact_message
        from pathlib import Path

        if sample_email and not can_send_sample(sample_email, "podcast_notes"):
            return {
                "order_id": order.get("order_id"), 
                "status": "skipped_throttle", 
                "error": "Sample limit reached (30 days)"
            }

        # Skip human review; pipeline must not send a client delivery email
        order["auto_approve"] = True
        order["client_email"] = ""

        result = podcast_pipeline.run_order(order)

        sample_pdf  = result.get("sample_pdf_path", "")
        drive_link  = result.get("drive_sample_pdf_link", "")

        if sample_email:
            show    = result.get("show_name", order.get("show_name", "your podcast"))
            episode = result.get("episode_title", order.get("episode_title", "your episode"))

            drive_section = (
                f'<p><a href="{drive_link}">View your sample package in Google Drive &rarr;</a></p>'
                if drive_link else ""
            )
            body = (
                f"<p>Hi there,</p>"
                f"<p>Here's your free content package sample for <b>{episode}</b> "
                f"from <b>{show}</b>.</p>"
                f"<p>The sample includes full timestamps and guest bio, plus a preview "
                f"of show notes, social captions, and more.</p>"
                f"{drive_section}"
                f"<p><b>Want the complete package?</b> Visit "
                f'<a href="https://echoforge.biz">echoforge.biz</a> to order — '
                f"delivered within 24 hours.</p>"
                f"<p>— EchoForge</p>"
            )
            attachments = [sample_pdf] if (sample_pdf and Path(sample_pdf).exists()) else []
            result_send = send_email(
                to=sample_email,
                subject=f"Your Free Podcast Sample — {episode}",
                body_html=body,
                attachments=attachments,
            )
            if isinstance(result_send, dict) and result_send.get("error"):
                raise RuntimeError(f"send_email failed: {result_send['error']}")

            log_contact_message(
                email=sample_email,
                venture="podcast_notes",
                message_type="sample",
                subject=f"Your Free Podcast Sample — {episode}",
                body_snippet=body[:200],
                message_id=result_send.get("message_id") if isinstance(result_send, dict) else None
            )

            # Schedule nurture follow-ups
            from datetime import datetime, timezone, timedelta
            run_nurture_email.apply_async(
                args=[sample_email, "podcast", order.get("order_id", ""), 3],
                eta=datetime.now(timezone.utc) + timedelta(days=3),
            )
            run_nurture_email.apply_async(
                args=[sample_email, "podcast", order.get("order_id", ""), 7],
                eta=datetime.now(timezone.utc) + timedelta(days=7),
            )

        return {"order_id": order.get("order_id"), "status": "sample_delivered"}

    except Exception as exc:
        _mark_failed(order.get("order_id"), "content_studio", str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        _slack_alert_failure("podcast_sample", order.get("order_id"), exc)
        raise


# ── Sample nurture emails ──────────────────────────────────────────────────────

@celery_app.task(bind=True, name="platform.nurture_email", max_retries=1)
def run_nurture_email(self, email: str, service: str, order_id: str, day: int) -> dict:
    """
    Send a nurture follow-up to someone who received a free sample.
    Dispatched with an ETA of day 3 and day 7 after sample delivery.

    service: "podcast" | "audit"
    day:     3 | 7
    """
    try:
        from aiplatform.skills.comms.send_email import send_email
        from aiplatform.database.crm_ops import can_send_sample, log_contact_message

        if service == "podcast":
            if day == 3:
                subject = "Did you see your free podcast sample?"
                body = (
                    "<p>Hi,</p>"
                    "<p>Just checking in — we sent you a free podcast content package sample a few days ago.</p>"
                    "<p>If you liked what you saw, the full package includes complete show notes, "
                    "social captions, newsletter excerpt, and SEO metadata — delivered within 24 hours.</p>"
                    '<p><a href="https://echoforge.biz"><b>Order your full package →</b></a></p>'
                    "<p>— EchoForge</p>"
                )
            else:  # day 7
                subject = "Last chance — 20% off your first podcast package"
                body = (
                    "<p>Hi,</p>"
                    "<p>It's been a week since we sent your free sample. "
                    "If you're still on the fence, here's a one-time offer:</p>"
                    "<p><b>20% off your first full content package.</b> "
                    "Reply to this email with code <b>SAMPLE20</b> when placing your order.</p>"
                    '<p><a href="https://echoforge.biz"><b>Claim your discount →</b></a></p>'
                    "<p>— EchoForge</p>"
                )
        else:  # audit
            if day == 3:
                subject = "Your marketing audit sample — did you check your score?"
                body = (
                    "<p>Hi,</p>"
                    "<p>A few days ago we sent you a free marketing audit sample for your website.</p>"
                    "<p>The sample shows your overall score and a few key findings. "
                    "The full audit unlocks all findings, a complete action plan, and competitor benchmarking.</p>"
                    '<p><a href="https://echoforge.biz"><b>Order the full audit →</b></a></p>'
                    "<p>— EchoForge</p>"
                )
            else:  # day 7
                subject = "Last chance — 20% off your full marketing audit"
                body = (
                    "<p>Hi,</p>"
                    "<p>Your free audit sample has been sitting in your inbox for a week. "
                    "We want to make it easy to act on it.</p>"
                    "<p><b>20% off your first full audit.</b> "
                    "Reply with code <b>AUDIT20</b> when ordering.</p>"
                    '<p><a href="https://echoforge.biz"><b>Claim your discount →</b></a></p>'
                    "<p>— EchoForge</p>"
                )

        result_send = send_email(to=email, subject=subject, body_html=body)
        log_contact_message(
            email=email,
            venture=f'{service}_notes' if service == 'podcast' else 'marketing_audit',
            message_type='nurture',
            subject=subject,
            body_snippet=body[:200],
            message_id=result_send.get('message_id') if isinstance(result_send, dict) else None
        )
        return {"email": email, "service": service, "day": day, "status": "sent"}

    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=3600)  # retry in 1 hour
        return {"error": str(exc)}


# ── Weekly finance digest ──────────────────────────────────────────────────────

@celery_app.task(bind=True, name="platform.weekly_digest", max_retries=1)
def run_weekly_digest(self) -> dict:
    """
    Send weekly finance digests — one per venture + one combined platform summary.

    Per-venture recipients (set any combination):
        DIGEST_EMAIL_ETSY      → MiroPrintStudio digest
        DIGEST_EMAIL_PODCAST   → Podcast Notes / Content Studio digest
        DIGEST_EMAIL_AUDIT     → Marketing Audit digest
        DIGEST_EMAIL_PLATFORM  → Combined all-ventures summary
    """
    # Venture → env var name → friendly label
    _VENTURE_MAP = {
        "etsy":          ("DIGEST_EMAIL_ETSY",     "MiroPrintStudio"),
        "content_studio":("DIGEST_EMAIL_PODCAST",  "Podcast Notes"),
        "marketing_audit":("DIGEST_EMAIL_AUDIT",   "Marketing Audit"),
    }

    try:
        from datetime import datetime, timezone, timedelta
        from aiplatform.database.models import Job, CostEvent, RevenueEvent
        from aiplatform.database.session import get_session
        from aiplatform.skills.comms.send_email import send_email
        from aiplatform.database.crm_ops import can_send_sample, log_contact_message

        since = datetime.now(timezone.utc) - timedelta(days=7)
        week_str = since.strftime("%b %d") + " – " + datetime.now(timezone.utc).strftime("%b %d, %Y")
        emails_sent = []

        with get_session() as db:
            all_completed = [
                j for j in db.query(Job).filter(Job.completed_at >= since).all()
                if j.status in ("completed", "delivered", "published")
            ]
            all_revenue = db.query(RevenueEvent).filter(RevenueEvent.created_at >= since).all()
            all_costs   = db.query(CostEvent).filter(CostEvent.created_at >= since).all()

        # Build per-venture data
        ventures: dict[str, dict] = {}
        for j in all_completed:
            v = j.venture or "unknown"
            ventures.setdefault(v, {"jobs": 0, "revenue": 0.0, "cost": 0.0})
            ventures[v]["jobs"] += 1
        for r in all_revenue:
            v = r.venture or "unknown"
            ventures.setdefault(v, {"jobs": 0, "revenue": 0.0, "cost": 0.0})
            ventures[v]["revenue"] += float(r.amount_usd)
        for c in all_costs:
            v = c.venture or "unknown"
            ventures.setdefault(v, {"jobs": 0, "revenue": 0.0, "cost": 0.0})
            ventures[v]["cost"] += float(c.cost_usd)

        # ── Send per-venture digest ────────────────────────────────────────────
        for venture_key, (env_var, label) in _VENTURE_MAP.items():
            recipient = os.environ.get(env_var, "")
            if not recipient:
                continue
            d = ventures.get(venture_key, {"jobs": 0, "revenue": 0.0, "cost": 0.0})
            roas = (d["revenue"] / d["cost"]) if d["cost"] > 0 else 0
            body = _digest_html(label, week_str, d["jobs"], d["revenue"], d["cost"], roas, {label: d})
            send_email(
                to=recipient,
                subject=f"{label} Weekly — {d['jobs']} jobs · ${d['revenue']:.2f}",
                body_html=body,
            )
            emails_sent.append(f"{label} → {recipient}")

        # ── Send combined platform digest ──────────────────────────────────────
        platform_email = os.environ.get("DIGEST_EMAIL_PLATFORM", "")
        if platform_email:
            total_jobs    = sum(d["jobs"]    for d in ventures.values())
            total_revenue = sum(d["revenue"] for d in ventures.values())
            total_cost    = sum(d["cost"]    for d in ventures.values())
            roas = (total_revenue / total_cost) if total_cost > 0 else 0
            # Rename keys to friendly labels for the table
            named = {_VENTURE_MAP.get(k, (None, k))[1]: v for k, v in ventures.items()}
            body = _digest_html("Platform", week_str, total_jobs, total_revenue, total_cost, roas, named)
            send_email(
                to=platform_email,
                subject=f"Platform Weekly — {total_jobs} jobs · ${total_revenue:.2f} revenue",
                body_html=body,
            )
            emails_sent.append(f"Platform → {platform_email}")

        if not emails_sent:
            return {"skipped": "No DIGEST_EMAIL_* vars set"}

        return {"emails_sent": emails_sent, "ventures": list(ventures.keys())}

    except Exception as exc:
        _slack_alert_failure("platform", "weekly_digest", exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=3600)
        raise


def _digest_html(
    title: str, week_str: str,
    jobs: int, revenue: float, cost: float, roas: float,
    ventures: dict,
) -> str:
    roas_color = "#00C853" if roas >= 3 else "#FF6B35"
    venture_rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{v}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:center'>{d.get('jobs',0)}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:right'>${d.get('revenue',0):.2f}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:right'>${d.get('cost',0):.4f}</td>"
        f"</tr>"
        for v, d in sorted(ventures.items())
    )
    return f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <h2 style="color:#1B2A4A">{title} — Weekly Digest</h2>
      <p style="color:#666">{week_str}</p>
      <table style="width:100%;border-collapse:collapse;margin:20px 0">
        <tr style="background:#f5f7fa">
          <td style="padding:12px;font-weight:bold">Jobs completed</td>
          <td style="padding:12px;text-align:right;font-size:1.4em;font-weight:bold">{jobs}</td>
        </tr>
        <tr>
          <td style="padding:12px;font-weight:bold">Revenue</td>
          <td style="padding:12px;text-align:right;font-size:1.4em;font-weight:bold;color:#00C853">${revenue:.2f}</td>
        </tr>
        <tr style="background:#f5f7fa">
          <td style="padding:12px;font-weight:bold">API costs</td>
          <td style="padding:12px;text-align:right;font-size:1.4em">${cost:.4f}</td>
        </tr>
        <tr>
          <td style="padding:12px;font-weight:bold">ROAS</td>
          <td style="padding:12px;text-align:right;font-size:1.4em;font-weight:bold;color:{roas_color}">{roas:.1f}x</td>
        </tr>
      </table>
      {"<h3 style='color:#1B2A4A'>By Venture</h3><table style='width:100%;border-collapse:collapse'><tr style='background:#1B2A4A;color:white'><th style='padding:8px 12px;text-align:left'>Venture</th><th style='padding:8px 12px'>Jobs</th><th style='padding:8px 12px;text-align:right'>Revenue</th><th style='padding:8px 12px;text-align:right'>Cost</th></tr>" + venture_rows + "</table>" if len(ventures) > 1 else ""}
      <p style="margin-top:24px;font-size:0.8em;color:#999">
        <a href="https://planBadmin.com">Open Dashboard</a>
      </p>
    </div>
    """


# ── Fiverr email parser ────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="platform.check_fiverr_emails", max_retries=1)
def check_fiverr_emails(self) -> dict:
    """
    Poll Gmail for unread Fiverr order notification emails.
    Parse each email with Claude and create orders in the system.
    Requires: GMAIL_FIVERR_LABEL env var (Gmail label applied to processed emails).
    """
    try:
        from aiplatform.skills.marketplace.fiverr_email_parser import parse_fiverr_inbox
        results = parse_fiverr_inbox()
        return results
    except Exception as exc:
        _slack_alert_failure("platform", "fiverr_email_check", exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300)
        raise
from celery.signals import task_success
from aiplatform.skills.strategy.run_advisor import run_advisor


@celery_app.task(name="platform.run_advisor_async")
def run_advisor_async(advisor_id: str, context_data: dict, job_id: str = None) -> None:
    """Async wrapper so advisors can be dispatched without blocking pipeline tasks."""
    run_advisor(advisor_id, context_data, job_id)


@task_success.connect
def advisory_task_success_handler(sender=None, result=None, **kwargs):
    """Fire the Product advisor after every completed pipeline task."""
    if not isinstance(result, dict) or not result.get("job_id"):
        return
    job_id = result["job_id"]
    run_advisor_async.delay("product", {"event": "task_success", "job_id": job_id}, job_id)


@celery_app.task(name="platform.eo_weekly_review")
def eo_weekly_review() -> None:
    """Aggregate weekly cost/revenue data and run the Executive advisor."""
    run_advisor("executive", {"event": "weekly_review"})


@celery_app.task(name="platform.run_accessibility_scan_job")
def run_accessibility_scan_job(audit_id: str, url: str) -> dict:
    from ventures.accessibility_audit.pipeline import run_order
    return run_order(audit_id, url)


@celery_app.task(name="platform.deliver_accessibility_audit_job")
def deliver_accessibility_audit_job(job_id: str, review_notes: str | None = None) -> dict:
    from ventures.accessibility_audit.pipeline import deliver_order
    return deliver_order(job_id, review_notes)


@celery_app.task(name="platform.run_security_audit_job", bind=True, max_retries=1)
def run_security_audit_job(self, audit_id: str) -> dict:
    from ventures.security_audit.pipeline import run_order
    try:
        result = run_order(audit_id)
        # Enrich return so callers can distinguish whether Phase 5 ran
        phase5_ran = False
        try:
            from aiplatform.database.session import SessionLocal
            from aiplatform.database.models import SecurityAudit
            db = SessionLocal()
            try:
                audit = db.query(SecurityAudit).filter(
                    SecurityAudit.audit_id == audit_id
                ).first()
                if audit and audit.phase5_auth_data:
                    auth_data = audit.phase5_auth_data
                    phase5_ran = bool(
                        auth_data.get("tools_run") or auth_data.get("findings")
                    )
            finally:
                db.close()
        except Exception:
            pass
        result["phase5_ran"] = phase5_ran
        return result
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120)
        _slack_alert_failure("security_audit", audit_id, exc)
        raise


@celery_app.task(name="platform.deliver_security_audit_job")
def deliver_security_audit_job(job_id: str, review_notes: str | None = None) -> dict:
    from ventures.security_audit.pipeline import deliver_order
    return deliver_order(job_id, review_notes)


@celery_app.task(name="platform.run_security_audit_retest_job", bind=True, max_retries=1)
def run_security_audit_retest_job(self, retest_audit_id: str) -> dict:
    from ventures.security_audit.pipeline import run_retest
    return run_retest(retest_audit_id)


@celery_app.task(name="platform.purge_old_security_audits")
def purge_old_security_audits() -> dict:
    """
    Purge SecurityAudit records (and twin Job records) older than 30 days.

    Runs daily via Celery beat. Implements the data retention policy promised in the
    Security Audit CLAUDE.md (Section 10) — raw artifacts and DB records are removed
    after 30 days.

    MinIO/S3 artifact cleanup is not yet wired here (artifacts are stored under
    audit_id keys); add an minio.remove_objects() call when MinIO is provisioned.
    """
    from datetime import datetime, timezone, timedelta
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import SecurityAudit, Job

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    db = SessionLocal()
    try:
        old_audits = (
            db.query(SecurityAudit)
            .filter(SecurityAudit.created_at < cutoff)
            .all()
        )
        purged = 0
        for audit in old_audits:
            if audit.job_id:
                job = db.get(Job, audit.job_id)
                if job:
                    db.delete(job)
            db.delete(audit)
            purged += 1
        db.commit()
        print(f"[data-retention] Purged {purged} SecurityAudit record(s) older than {cutoff.date()}", flush=True)
        return {"purged": purged, "cutoff": cutoff.isoformat()}
    finally:
        db.close()


# ── Outreach tasks ─────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="outreach.find_leads", max_retries=1)
def run_find_leads(self, campaign_id: str, venture: str, max_leads: int = 20, channels: list | None = None, search_prompt: str | None = None) -> dict:
    """
    Search configured channels for potential customers and persist them as leads.
    Skips duplicates by checking existing lead source_url in this campaign.
    search_prompt: user-reviewed AI criteria prompt that guides Claude qualification.
    """
    from aiplatform.skills.research.find_leads import find_leads
    from aiplatform.database.models import Lead, OutreachCampaign
    from aiplatform.database.session import SessionLocal
    import uuid

    db = SessionLocal()
    try:
        raw_leads = find_leads(venture, max_leads=max_leads, channels=channels, search_prompt=search_prompt)

        # Deduplicate against existing leads in DB (by source_url)
        campaign_uuid = uuid.UUID(campaign_id)
        existing_urls = {
            row[0] for row in db.query(Lead.source_url).filter(
                Lead.campaign_id == campaign_uuid,
                Lead.source_url.isnot(None),
            ).all()
        }

        new_count = 0
        for lead_data in raw_leads:
            if lead_data.get("source_url") in existing_urls:
                continue
            l = Lead(
                venture=lead_data["venture"],
                source_channel=lead_data["source_channel"],
                source_url=lead_data.get("source_url"),
                name=lead_data.get("name"),
                email=lead_data.get("email"),
                website_url=lead_data.get("website_url"),
                company=lead_data.get("company"),
                notes=lead_data.get("notes"),
                status="new",
                campaign_id=campaign_uuid,
            )
            db.add(l)
            new_count += 1

        db.commit()
        return {"campaign_id": campaign_id, "leads_found": len(raw_leads), "leads_added": new_count}

    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="outreach.send", max_retries=1)
def run_send_outreach(self, campaign_id: str, lead_ids: list | None = None, template_variant: str | None = None) -> dict:
    """
    Send approved outreach emails to leads in a campaign.
    Distributes leads round-robin across approved template variants.
    Only sends to leads with status='new' and a valid email.

    Cross-venture spam guard:
      - Never sends to a contact that has unsubscribed (any campaign, any venture).
      - Never sends a second email to the same address within 30 days across all campaigns.

    After each successful send, upserts the Contact record for CRM tracking.
    """
    from aiplatform.skills.comms.send_email import send_email
    from aiplatform.database.crm_ops import can_send_sample, log_contact_message
    from aiplatform.database.models import Contact, Lead, OutreachTemplate, OutreachSend, OutreachCampaign
    from aiplatform.database.session import SessionLocal
    from datetime import timedelta
    import uuid, os

    db = SessionLocal()
    try:
        campaign_uuid = uuid.UUID(campaign_id)
        campaign = db.get(OutreachCampaign, campaign_uuid)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Get approved templates
        tq = db.query(OutreachTemplate).filter(
            OutreachTemplate.campaign_id == campaign_uuid,
            OutreachTemplate.approved == "approved",
        )
        if template_variant:
            tq = tq.filter(OutreachTemplate.variant == template_variant)
        templates = tq.all()
        if not templates:
            return {"error": "No approved templates found"}

        # Get eligible leads
        lq = db.query(Lead).filter(
            Lead.campaign_id == campaign_uuid,
            Lead.status == "new",
            Lead.email.isnot(None),
        )
        if lead_ids:
            lead_uuids = [uuid.UUID(lid) for lid in lead_ids]
            lq = lq.filter(Lead.id.in_(lead_uuids))
        leads = lq.all()

        sent_count = 0
        skipped_spam = 0
        base_url = os.environ.get("RAILWAY_PUBLIC_URL", "https://api.planbadmin.com")
        cooldown_days = 30
        now = datetime.now(timezone.utc)

        for i, lead in enumerate(leads):
            # ── Cross-venture spam guard ─────────────────────────────────────
            if lead.email:
                contact = db.query(Contact).filter(Contact.email == lead.email).first()
                if contact:
                    # Never send to unsubscribed contacts
                    if contact.status == "unsubscribed":
                        lead.status = "unsubscribed"
                        skipped_spam += 1
                        continue
                    # Cooldown: skip if contacted within last 30 days from ANY campaign
                    if contact.last_activity_at and (now - contact.last_activity_at).days < cooldown_days:
                        skipped_spam += 1
                        continue

            # Pick template round-robin across variants
            template = templates[i % len(templates)]

            # ── Build tracking URLs ──────────────────────────────────────────
            send_id = str(uuid.uuid4())
            pixel_url = f"{base_url}/api/outreach/track/open/{send_id}"
            unsub_url = f"{base_url}/api/outreach/unsubscribe/{send_id}"

            # Replace unsubscribe placeholder in body text
            body_text = (template.body_text or "").replace("{{UNSUBSCRIBE_URL}}", unsub_url)

            # Build HTML: inject pixel + unsubscribe link
            body_html = template.body_html
            # Replace placeholder if present, otherwise append footer
            if "{{UNSUBSCRIBE_URL}}" in body_html:
                body_html = body_html.replace("{{UNSUBSCRIBE_URL}}", unsub_url)
            else:
                body_html += (
                    f'\n<p style="margin-top:24px;font-size:11px;color:#999;">'
                    f'<a href="{unsub_url}" style="color:#999;">Unsubscribe</a></p>'
                )
            body_html += f'\n<img src="{pixel_url}" width="1" height="1" style="display:none" alt="" />'

            result = send_email(
                to=lead.email,
                subject=template.subject,
                body_html=body_html,
                body_text=body_text,
            )

            if result.get("error"):
                continue  # keep lead as "new" for retry

            # Record the send
            send_record = OutreachSend(
                id=uuid.UUID(send_id),
                lead_id=lead.id,
                template_id=template.id,
                campaign_id=campaign_uuid,
                message_id=result.get("message_id", ""),
                status="sent",
            )
            db.add(send_record)
            template.sends_count = (template.sends_count or 0) + 1
            lead.status = "email_sent"
            sent_count += 1

            # ── Upsert Contact for CRM tracking ─────────────────────────────
            if lead.email:
                contact = db.query(Contact).filter(Contact.email == lead.email).first()
                if contact:
                    contact.last_activity_at = now
                    ventures = list(contact.ventures_approached or [])
                    if campaign.venture not in ventures:
                        ventures.append(campaign.venture)
                        contact.ventures_approached = ventures
                    if contact.status not in ("unsubscribed", "purchased", "inquired"):
                        contact.status = "approached"
                else:
                    contact = Contact(
                        email=lead.email,
                        name=lead.name,
                        company=lead.company,
                        website_url=lead.website_url,
                        status="approached",
                        ventures_approached=[campaign.venture],
                        last_activity_at=now,
                    )
                    db.add(contact)

        db.commit()
        return {
            "campaign_id": campaign_id,
            "sent": sent_count,
            "skipped_spam_or_cooldown": skipped_spam,
            "total_leads": len(leads),
        }

    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        raise
    finally:
        db.close()


# ── Campaign Manager ──────────────────────────────────────────────────────────

@celery_app.task(name="platform.monitor_campaign_budgets")
def monitor_campaign_budgets() -> dict:
    """
    Hourly beat task: fetch spend from vendor APIs for all active campaigns.
    Records a MetricsHistory snapshot and auto-pauses any campaign at/over 100% budget.
    """
    from decimal import Decimal
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import Campaign, MetricsHistory
    from aiplatform.skills.ads.meta_ads_adapter import get_adapter

    db = SessionLocal()
    try:
        active = db.query(Campaign).filter(
            Campaign.status == "active",
            Campaign.external_id.isnot(None),
        ).all()

        paused_count = 0
        snapshot_count = 0
        for campaign in active:
            try:
                adapter = get_adapter(campaign.vendor)
                if not adapter.is_configured():
                    continue
                stats = adapter.get_stats(campaign.external_id)

                snap = MetricsHistory(
                    campaign_id=campaign.id,
                    spend=stats.spend,
                    clicks=stats.clicks,
                    impressions=stats.impressions,
                    cpa=stats.cpa,
                )
                db.add(snap)
                snapshot_count += 1

                # Auto-pause at 100% of daily budget
                if campaign.daily_budget_limit and stats.spend >= Decimal(str(campaign.daily_budget_limit)):
                    adapter.toggle_status(campaign.external_id, active=False)
                    campaign.status = "paused"
                    paused_count += 1
                    print(
                        f"[budget-monitor] Auto-paused {campaign.name} "
                        f"(spend ${stats.spend} >= budget ${campaign.daily_budget_limit})",
                        flush=True,
                    )
            except Exception as e:
                print(f"[budget-monitor] Error for campaign {campaign.id}: {e}", flush=True)

        db.commit()
        return {"snapshots": snapshot_count, "auto_paused": paused_count}
    finally:
        db.close()


@celery_app.task(name="platform.generate_campaign_insights")
def generate_campaign_insights() -> dict:
    """
    Weekly beat task: run the AI insight engine for all active campaigns
    that haven't had insights generated in the last 6 days.
    """
    from datetime import timedelta
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import Campaign
    from datetime import datetime, timezone
    import anthropic, json, os

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=6)
        campaigns = db.query(Campaign).filter(
            Campaign.status.in_(["active", "paused"]),
        ).all()

        refreshed = 0
        for campaign in campaigns:
            if campaign.insights_at and campaign.insights_at > cutoff:
                continue
            try:
                metrics_summary = ""
                if campaign.metrics:
                    m = campaign.metrics[0]
                    metrics_summary = (
                        f"Spend: ${m.spend}, Clicks: {m.clicks}, Impressions: {m.impressions}"
                    )
                prompt = (
                    f"Campaign: {campaign.name}\nVendor: {campaign.vendor}\n"
                    f"Status: {campaign.status}\nBudget: ${campaign.daily_budget_limit}/day\n"
                    f"Metrics: {metrics_summary or 'none yet'}\n\n"
                    "Return a JSON object with summary, suggestions (list of action+reason+priority), "
                    "and budget_recommendation. Return ONLY the JSON."
                )
                client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = msg.content[0].text.strip()
                s, e = raw.find("{"), raw.rfind("}") + 1
                campaign.ai_insights = json.loads(raw[s:e]) if s != -1 else {"raw": raw}
                campaign.insights_at = datetime.now(timezone.utc)
                refreshed += 1
            except Exception as ex:
                print(f"[weekly-insights] Failed for {campaign.id}: {ex}", flush=True)

        db.commit()
        return {"campaigns_refreshed": refreshed}
    finally:
        db.close()


# ── Market Research ────────────────────────────────────────────────────────────

_MR_IN_PROGRESS = {"optimizing", "researching", "merging", "reflecting", "generating_pdf"}
_MR_STUCK_THRESHOLD_MINUTES = 40  # max realistic single-package runtime; anything older is stuck


@celery_app.task(name="platform.market_research_watchdog", bind=False)
def market_research_watchdog() -> dict:
    """
    Scan for market research sessions stuck in in-progress states and re-queue them.

    A session is considered stuck if its status is in _MR_IN_PROGRESS and updated_at
    has not changed in more than _MR_STUCK_THRESHOLD_MINUTES minutes (i.e. no package
    completed and no status transition happened). Runs every 10 minutes via Beat.
    """
    from aiplatform.database.models import MarketResearch
    from aiplatform.database.session import SessionLocal
    from datetime import datetime, timezone, timedelta

    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=_MR_STUCK_THRESHOLD_MINUTES)
        stuck = (
            db.query(MarketResearch)
            .filter(
                MarketResearch.status.in_(list(_MR_IN_PROGRESS)),
                MarketResearch.updated_at < threshold,
            )
            .all()
        )

        requeued = []
        for record in stuck:
            logger.warning(
                "market_research_watchdog: session %s stuck in '%s' since %s — requeuing",
                record.id, record.status, record.updated_at,
            )
            prior_status = record.status
            record.status = "pending"
            record.error = f"Auto-requeued by watchdog (was stuck in '{prior_status}' since {record.updated_at})"
            db.commit()
            task = run_market_research.delay(str(record.id))
            record.celery_task_id = task.id
            db.commit()
            requeued.append(str(record.id))

        if requeued:
            _slack_alert_failure("market_research_watchdog", None,
                                 Exception(f"Requeued {len(requeued)} stuck session(s): {requeued}"))
        return {"requeued": requeued, "count": len(requeued)}
    finally:
        db.close()


@celery_app.task(name="platform.run_market_research", bind=True, max_retries=2,
                 soft_time_limit=1800, time_limit=1900)
def run_market_research(self, research_id: str) -> dict:
    """Run the full market research pipeline for a given session ID."""
    from ventures.market_research.pipeline import run_market_research as _run
    from aiplatform.database.session import SessionLocal

    db = SessionLocal()
    try:
        _run(research_id, db)
        return {"research_id": research_id, "status": "done"}
    except Exception as exc:
        _slack_alert_failure("market_research", research_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        raise
    finally:
        db.close()
