"""Content Studio (Podcast Notes) venture router — orders + audio upload."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from aiplatform.database.models import Job
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import (
    JobDetail,
    JobListResponse,
    JobSummary,
    PodcastApproveRequest,
    PodcastOrderRequest,
    PodcastOrderResponse,
)

router = APIRouter()


@router.post("/orders", response_model=PodcastOrderResponse, status_code=status.HTTP_202_ACCEPTED)
def create_podcast_order(
    req: PodcastOrderRequest,
    _: str = Depends(require_auth),
) -> PodcastOrderResponse:
    """Submit a new podcast show notes order."""
    from aiplatform.webapp.worker import run_podcast_order as celery_task

    order_id = req.order_id or f"podcast-{uuid.uuid4().hex[:8]}"
    order = {
        "order_id":     order_id,
        "audio_url":    req.audio_url,
        "tier":         req.tier,
        "show_name":    req.show_name or "",
        "client_email": req.client_email,
        "status":       "pending",
    }
    task = celery_task.delay(order)
    return PodcastOrderResponse(order_id=order_id, celery_task_id=task.id)


@router.get("/orders", response_model=JobListResponse)
def list_podcast_orders(
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobListResponse:
    items = db.query(Job).filter(Job.venture == "content_studio").order_by(
        Job.created_at.desc()
    ).limit(50).all()
    return JobListResponse(
        items=[JobSummary.model_validate(j) for j in items],
        total=len(items),
        page=1,
        page_size=50,
    )


@router.get("/orders/{order_id}", response_model=JobDetail)
def get_podcast_order(
    order_id: str,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobDetail:
    job = db.query(Job).filter(
        Job.venture == "content_studio",
        Job.input_data["order_id"].astext == order_id,
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return JobDetail.model_validate(job)


@router.post("/orders/{order_id}/review")
def review_podcast_order(
    order_id: str,
    req: PodcastApproveRequest,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    """Approve, reject, or request revision for a review-pending podcast order."""
    job = db.query(Job).filter(
        Job.venture == "content_studio",
        Job.input_data["order_id"].astext == order_id,
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if job.status != "review_pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order status is '{job.status}', expected 'review_pending'",
        )

    from aiplatform.webapp.worker import run_podcast_order as celery_task

    order = dict(job.output_data or job.input_data)
    order["review_action"] = req.action
    order["review_notes"]  = req.notes or ""

    if req.action == "approve":
        order["status"] = "approved"
        task = celery_task.delay(order)
        job.celery_task_id = task.id
    elif req.action == "reject":
        order["status"] = "failed"
    else:
        order["status"] = "pending"
        task = celery_task.delay(order)
        job.celery_task_id = task.id

    job.status = order["status"]
    job.output_data = order
    db.commit()

    return {"order_id": order_id, "action": req.action, "status": order["status"]}
