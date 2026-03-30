"""Jobs API — list, detail, approve, reject, retry, cancel."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from aiplatform.database.models import Job
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import JobActionResponse, JobDetail, JobListResponse, JobSummary

router = APIRouter()


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot cancel job in status '{job.status}'")

    if job.celery_task_id:
        try:
            from aiplatform.webapp.worker import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)
        except Exception:
            pass

    job.status = "cancelled"
    db.commit()
    return JobActionResponse(job_id=job_id, action="cancel", status="cancelled")


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed jobs can be retried")

    from aiplatform.webapp import worker as w
    venture = job.venture
    order = job.output_data or job.input_data

    if venture == "marketing_audit":
        task = w.run_audit_order.delay(order)
    elif venture == "content_studio":
        task = w.run_podcast_order.delay(order)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Retry not supported for venture '{venture}'")

    job.status = "pending"
    job.celery_task_id = task.id
    job.error_message = None
    db.commit()

    return JobActionResponse(job_id=job_id, action="retry", status="pending")
