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
    import base64, logging
    log = logging.getLogger(__name__)

    # OAuth user token — preferred, works with personal Google Drive
    token_b64 = os.environ.get("GOOGLE_DRIVE_TOKEN_JSON", "")
    if token_b64:
        dest = Path(os.environ.get("GOOGLE_TOKEN_PATH", "./google_token.json"))
        try:
            dest.write_bytes(base64.b64decode(token_b64))
            log.info("Google OAuth token written to %s", dest)
        except Exception as exc:
            log.warning("Failed to write Google OAuth token: %s", exc)

    # Service account — fallback for non-Drive operations
    sa_b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if sa_b64:
        dest = Path(os.environ.get("GOOGLE_CREDENTIALS_PATH", "./google_credentials.json"))
        try:
            dest.write_bytes(base64.b64decode(sa_b64))
            log.info("Google service account written to %s", dest)
        except Exception as exc:
            log.warning("Failed to write Google service account: %s", exc)

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
)


# ── helpers ────────────────────────────────────────────────────────────────────

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
#   Phase 4 — auto (packaging) → sets job to review_pending, sends Phase 5 notification
#   Phase 6 — triggered by POST /api/jobs/{id}/approve in the web UI
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

        # ── Phase 4 → set review_pending, queue Phase 5 notification ──────────
        if phase == 4:
            # Store subject + phase3_result alongside phase4 result so the
            # approve endpoint can pass all three to Phase 6
            full_result = {
                **result,
                "subject":      params.get("subject"),
                "phase3_result": params.get("phase3_result"),
            }
            _etsy_update_job(job_id, "review_pending", full_result, now)
            run_etsy_phase.delay(5, {"pending_subjects": [result]})
            return {"phase": 4, "status": "review_pending", "job_id": job_id, "result": full_result}

        # ── Phase 5 — notification only, no DB job of its own ─────────────────
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
    try:
        from ventures.marketing_audit import pipeline as audit_pipeline

        result = audit_pipeline.run_order(order)

        # If pipeline paused at review gate, signal Redis
        if result.get("status") == "review_pending":
            job_id = _get_job_id(order, "marketing_audit")
            if job_id:
                _set_approval_gate(job_id, "pending")

        return {
            "order_id": order.get("order_id"),
            "status":   result.get("status"),
            "result":   result,
        }

    except Exception as exc:
        _mark_failed(order.get("order_id"), "marketing_audit", str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120)
        raise


# ── Content Studio venture ─────────────────────────────────────────────────────

@celery_app.task(bind=True, name="podcast.run_order", max_retries=2)
def run_podcast_order(self, order: dict) -> dict:
    """
    Run a podcast show notes order through all pipeline phases.

    Same approval gate pattern as run_audit_order.
    """
    try:
        from ventures.content_studio import pipeline as podcast_pipeline

        result = podcast_pipeline.run_order(order)

        if result.get("status") == "review_pending":
            job_id = _get_job_id(order, "content_studio")
            if job_id:
                _set_approval_gate(job_id, "pending")

        return {
            "order_id": order.get("order_id"),
            "status":   result.get("status"),
            "result":   result,
        }

    except Exception as exc:
        _mark_failed(order.get("order_id"), "content_studio", str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120)
        raise
