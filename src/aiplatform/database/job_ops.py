"""
Platform utility: upsert a Job row from a pipeline order dict.

Phase 1 dual-write — JSON files remain primary source of truth.
DB writes are non-blocking: any failure is logged and swallowed.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from aiplatform.database.models import Job
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


def upsert_job(order: dict, venture: str) -> None:
    """
    Insert or update a Job row from a pipeline order dict.

    Looks up the existing job by venture + order_id stored in input_data.
    If not found, inserts a new row.

    Args:
        order:   The full order dict written by the pipeline (must contain "order_id").
        venture: One of "marketing_audit", "content_studio", "etsy".
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

            if existing:
                existing.status = status
                existing.phase_current = phase_current
                existing.output_data = dict(order)
                existing.updated_at = now
                if status in _TERMINAL_STATUSES and not existing.completed_at:
                    existing.completed_at = now
                if status not in _STARTED_STATUSES and not existing.started_at:
                    existing.started_at = now
            else:
                db.add(Job(
                    venture=venture,
                    status=status,
                    phase_current=phase_current,
                    phase_total=phase_total,
                    input_data={"order_id": order_id},
                    output_data=dict(order),
                    started_at=now if status not in _STARTED_STATUSES else None,
                ))
    except SQLAlchemyError as exc:
        print(f"[upsert_job:{venture}] non-fatal DB write failed: {exc}")
