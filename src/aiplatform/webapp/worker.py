"""
Celery worker — one task per venture pipeline.

Start the worker locally with:
    celery -A aiplatform.webapp.worker worker --loglevel=info

On Railway: separate "worker" service runs this same command.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from celery import Celery

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


# ── Etsy venture ──────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="etsy.run_phase", max_retries=2)
def run_etsy_phase(self, phase: int, params: dict) -> dict:
    """Run a single Etsy pipeline phase."""
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

        result = fn(**params)
        return {"phase": phase, "status": "completed", "result": result}

    except Exception as exc:
        raise self.retry(exc=exc, countdown=60) if self.request.retries < self.max_retries else exc


# ── Marketing Audit venture ───────────────────────────────────────────────────

@celery_app.task(bind=True, name="audit.run_order", max_retries=2)
def run_audit_order(self, order: dict) -> dict:
    """Run a marketing audit order through all pipeline phases."""
    try:
        from ventures.marketing_audit import pipeline as audit_pipeline
        result = audit_pipeline.run_order(order)
        return {"order_id": order.get("order_id"), "status": result.get("status"), "result": result}

    except Exception as exc:
        # Write failure status to DB before retrying
        _mark_failed(order.get("order_id"), "marketing_audit", str(exc))
        raise self.retry(exc=exc, countdown=120) if self.request.retries < self.max_retries else exc


# ── Content Studio venture ─────────────────────────────────────────────────────

@celery_app.task(bind=True, name="podcast.run_order", max_retries=2)
def run_podcast_order(self, order: dict) -> dict:
    """Run a podcast show notes order through all pipeline phases."""
    try:
        from ventures.content_studio import pipeline as podcast_pipeline
        result = podcast_pipeline.run_order(order)
        return {"order_id": order.get("order_id"), "status": result.get("status"), "result": result}

    except Exception as exc:
        _mark_failed(order.get("order_id"), "content_studio", str(exc))
        raise self.retry(exc=exc, countdown=120) if self.request.retries < self.max_retries else exc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mark_failed(order_id: str | None, venture: str, error: str) -> None:
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
