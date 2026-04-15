"""
Platform jobs router — list, detail, approve, reject, retry, cancel.

Approval gate pattern:
  - When a pipeline reaches review_pending it sets the DB status and returns.
  - POST /approve writes a Redis signal key then re-dispatches the Celery task
    with order["status"] = "approved" so the pipeline skips to the delivery phase.
  - POST /reject writes a Redis signal key and marks the job failed/rejected.
"""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from aiplatform.database.models import Job
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import (
    JobActionResponse,
    JobApproveRequest,
    JobDetail,
    JobListResponse,
    JobRejectRequest,
    JobSummary,
)

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _redis_signal(job_id: str, signal: str) -> None:
    """Write an approval signal to Redis so pipelines / frontends can poll."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        key = f"approval_gate:{job_id}"
        r.set(key, signal, ex=86400)  # 24-hour TTL
    except Exception:
        pass  # Redis unavailable — signal is best-effort; DB status is authoritative


# ── list & detail ─────────────────────────────────────────────────────────────

@router.get("", response_model=JobListResponse)
def list_jobs(
    venture: str | None = Query(None),
    job_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobListResponse:
    q = db.query(Job)
    if venture:
        q = q.filter(Job.venture == venture)
    if job_status:
        q = q.filter(Job.status == job_status)

    total = q.count()
    items = q.order_by(Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return JobListResponse(
        items=[JobSummary.model_validate(j) for j in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: uuid.UUID,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobDetail:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobDetail.model_validate(job)


# ── approve ───────────────────────────────────────────────────────────────────

@router.post("/{job_id}/approve", response_model=JobActionResponse)
def approve_job(
    job_id: uuid.UUID,
    req: JobApproveRequest,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobActionResponse:
    """
    Resume a job that is paused at review_pending.

    Flow:
      1. Validate job is in review_pending status.
      2. Write Redis signal approval_gate:{job_id} = "approve".
      3. Re-dispatch the appropriate Celery task with order["status"] = "approved"
         so the pipeline skips directly to the delivery phase.
    """
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "review_pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job status is '{job.status}', expected 'review_pending'",
        )

    # Redis signal — pipeline / frontend can poll this key
    _redis_signal(str(job_id), "approve")

    # Re-dispatch Celery task with approved order state
    from aiplatform.worker import run_audit_order, run_podcast_order, run_etsy_phase, deliver_accessibility_audit_job

    order = dict(job.output_data or job.input_data)
    order["status"] = "approved"
    if req.notes:
        order["review_notes"] = req.notes

    if job.venture == "marketing_audit":
        task = run_audit_order.delay(order)
    elif job.venture == "content_studio":
        task = run_podcast_order.delay(order)
    elif job.venture == "etsy":
        # For Etsy, approval triggers Phase 6 (Etsy draft upload)
        # output_data contains the Phase 4 result which has subject + phase3_result + phase4_result
        phase4_result = job.output_data or {}
        subject = phase4_result.get("subject") or order.get("subject", {})
        phase3_result = phase4_result.get("phase3_result") or order.get("phase3_result")
        task = run_etsy_phase.delay(6, {
            "subject": subject,
            "phase3_result": phase3_result,
            "phase4_result": phase4_result,
        })
    elif job.venture == "accessibility_audit":
        task = deliver_accessibility_audit_job.delay(str(job_id), req.notes)
    elif job.venture == "security_audit":
        # Security audit approval just marks the job ready for delivery.
        # Delivery is triggered separately via POST /ventures/security-audit/orders/{id}/deliver.
        from aiplatform.database.models import SecurityAudit
        audit = db.query(SecurityAudit).filter(SecurityAudit.job_id == job_id).first()
        if audit:
            audit.status = "approved"
            if req.notes:
                audit.reviewer_notes = req.notes
        out = dict(job.output_data or {})
        out["status"] = "approved"
        if req.notes:
            out["reviewer_notes"] = req.notes
        job.output_data = out
        job.status = "approved"
        db.commit()
        return JobActionResponse(job_id=job_id, action="approve", status="approved")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval not supported for venture '{job.venture}'",
        )

    job.status = "approved"
    job.celery_task_id = task.id
    db.commit()

    return JobActionResponse(job_id=job_id, action="approve", status="approved")


# ── reject ────────────────────────────────────────────────────────────────────

@router.post("/{job_id}/reject", response_model=JobActionResponse)
def reject_job(
    job_id: uuid.UUID,
    req: JobRejectRequest,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobActionResponse:
    """Mark a review_pending job as rejected — no delivery."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "review_pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job status is '{job.status}', expected 'review_pending'",
        )

    _redis_signal(str(job_id), "reject")

    job.status = "failed"
    if req.reason:
        job.error_message = f"Rejected: {req.reason}"
    db.commit()

    return JobActionResponse(job_id=job_id, action="reject", status="failed")


# ── retry ─────────────────────────────────────────────────────────────────────

@router.post("/{job_id}/retry", response_model=JobActionResponse)
def retry_job(
    job_id: uuid.UUID,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobActionResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed jobs can be retried",
        )

    from aiplatform.worker import run_audit_order, run_podcast_order, run_etsy_phase, run_accessibility_scan_job

    order = dict(job.output_data or job.input_data)
    order["status"] = "pending"

    if job.venture == "marketing_audit":
        task = run_audit_order.delay(order)
    elif job.venture == "content_studio":
        task = run_podcast_order.delay(order)
    elif job.venture == "etsy":
        # Re-run the same phase with the same params stored in input_data
        phase = job.phase_current or order.get("phase", 1)
        inp = dict(job.input_data or {})
        inp.pop("order_id", None)
        task = run_etsy_phase.delay(phase, inp)
    elif job.venture == "accessibility_audit":
        task = run_accessibility_scan_job.delay(
            str(order.get("audit_id") or order.get("order_id") or job.input_data.get("audit_id") or job.input_data.get("order_id")),
            str(order.get("url") or job.input_data.get("url") or ""),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Retry not supported for venture '{job.venture}'",
        )

    job.status = "pending"
    job.celery_task_id = task.id
    job.error_message = None
    db.commit()

    return JobActionResponse(job_id=job_id, action="retry", status="pending")


# ── cancel ────────────────────────────────────────────────────────────────────

@router.post("/{job_id}/cancel", response_model=JobActionResponse)
def cancel_job(
    job_id: uuid.UUID,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobActionResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status in ("delivered", "published", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel job in status '{job.status}'",
        )

    if job.celery_task_id:
        try:
            from aiplatform.worker import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)
        except Exception:
            pass

    job.status = "cancelled"
    db.commit()
    return JobActionResponse(job_id=job_id, action="cancel", status="cancelled")
