"""
Platform utility: upsert a Job row from a pipeline order dict.

Phase 1 dual-write — JSON files remain primary source of truth.
DB writes are non-blocking: any failure is logged and swallowed.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from aiplatform.database.models import Job, PhaseEvent
from aiplatform.database.session import get_session


# Status → (phase_current, phase_total) per venture
_PHASE_MAPS: dict[str, dict[str, tuple[int, int]]] = {
    "marketing_audit": {
        "pending":           (1, 6),
        "scraping":          (1, 6),
        "scraped":           (2, 6),
        "auditing":          (3, 6),
        "audited":           (3, 6),
        "generating_report": (4, 6),
        "report_ready":      (4, 6),
        "review_pending":    (5, 6),
        "approved":          (5, 6),
        "delivering":        (6, 6),
        "delivered":         (6, 6),
        "failed":            (None, 6),
    },
    "content_studio": {
        "pending":        (1, 5),
        "transcribing":   (1, 5),
        "transcribed":    (1, 5),
        "generating":     (2, 5),
        "generated":      (2, 5),
        "packaging":      (3, 5),
        "packaged":       (3, 5),
        "review_pending": (4, 5),
        "approved":       (4, 5),
        "delivering":     (5, 5),
        "delivered":      (5, 5),
        "failed":         (None, 5),
    },
    "etsy": {
        "pending":           (0, 7),
        "researching":       (1, 7),
        "researched":        (1, 7),
        "generating":        (2, 7),
        "generated":         (2, 7),
        "imaging":           (3, 7),
        "imaged":            (3, 7),
        "packaging":         (4, 7),
        "packaged":          (4, 7),
        "review_pending":    (5, 7),
        "approved":          (5, 7),
        "listing":           (6, 7),
        "listed":            (6, 7),
        "published":         (7, 7),
        "failed":            (None, 7),
    },
}

_TERMINAL_STATUSES = {"delivered", "published", "failed"}
_STARTED_STATUSES  = {"pending"}  # anything NOT in this set counts as started

# Status → (phase_number, event_type) — only meaningful transition milestones.
# "pending" and intermediate non-transition statuses are intentionally omitted.
_STATUS_EVENTS: dict[str, dict[str, tuple[int | None, str]]] = {
    "marketing_audit": {
        "scraping":          (1, "started"),
        "scraped":           (1, "completed"),
        "auditing":          (3, "started"),
        "audited":           (3, "completed"),
        "generating_report": (4, "started"),
        "report_ready":      (4, "completed"),
        "review_pending":    (5, "paused"),
        "approved":          (5, "resumed"),
        "delivering":        (6, "started"),
        "delivered":         (6, "completed"),
        "failed":            (None, "failed"),
    },
    "content_studio": {
        "transcribing":   (1, "started"),
        "transcribed":    (1, "completed"),
        "generating":     (2, "started"),
        "generated":      (2, "completed"),
        "packaging":      (3, "started"),
        "packaged":       (3, "completed"),
        "review_pending": (4, "paused"),
        "approved":       (4, "resumed"),
        "delivering":     (5, "started"),
        "delivered":      (5, "completed"),
        "failed":         (None, "failed"),
    },
}


def upsert_job(order: dict, venture: str, *, celery_task_id: str | None = None) -> None:
    """
    Insert or update a Job row from a pipeline order dict.

    Looks up the existing job by venture + order_id stored in input_data.
    If not found, inserts a new row.

    Args:
        order:           The full order dict written by the pipeline (must contain "order_id").
        venture:         One of "marketing_audit", "content_studio", "etsy".
        celery_task_id:  Optional Celery task ID to store on the job row (set by the API router
                         after queuing, not available inside the pipeline itself).
    """
    order_id = str(order.get("order_id") or order.get("id") or "").strip()
    if not order_id:
        return

    phase_map = _PHASE_MAPS.get(venture, {})
    status = order.get("status", "pending")
    phase_current, phase_total = phase_map.get(status, (None, None))
    now = datetime.now(timezone.utc)

    try:
        with get_session() as db:
            existing: Job | None = db.query(Job).filter(
                Job.venture == venture,
                Job.input_data["order_id"].astext == order_id,
            ).first()

            old_status = existing.status if existing else None

            if existing:
                existing.status = status
                existing.phase_current = phase_current
                existing.output_data = dict(order)
                existing.updated_at = now
                if celery_task_id:
                    existing.celery_task_id = celery_task_id
                if status in _TERMINAL_STATUSES and not existing.completed_at:
                    existing.completed_at = now
                if status not in _STARTED_STATUSES and not existing.started_at:
                    existing.started_at = now
                job_id = existing.id
            else:
                new_job = Job(
                    venture=venture,
                    status=status,
                    phase_current=phase_current,
                    phase_total=phase_total,
                    input_data={"order_id": order_id},
                    output_data=dict(order),
                    celery_task_id=celery_task_id,
                    started_at=now if status not in _STARTED_STATUSES else None,
                )
                db.add(new_job)
                db.flush()  # populate new_job.id before logging the phase event
                job_id = new_job.id

            # Append a PhaseEvent if this status represents a meaningful transition
            event_spec = _STATUS_EVENTS.get(venture, {}).get(status)
            if event_spec and old_status != status:
                phase_n, event_type = event_spec
                db.add(PhaseEvent(
                    job_id=job_id,
                    phase=phase_n,
                    event_type=event_type,
                    details={},
                ))
    except SQLAlchemyError as exc:
        print(f"[upsert_job:{venture}] non-fatal DB write failed: {exc}")
