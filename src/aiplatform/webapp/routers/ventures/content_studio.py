"""
Content Studio (Podcast Notes) venture router.

  POST /api/ventures/content-studio/orders   — create a new podcast order
  GET  /api/ventures/content-studio/orders   — list podcast orders
  GET  /api/ventures/content-studio/orders/{order_id}
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from aiplatform.database.models import Job
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import (
    JobDetail,
    JobListResponse,
    JobSummary,
    PodcastOrderRequest,
    PodcastOrderResponse,
)

router = APIRouter()


@router.post("/orders", response_model=PodcastOrderResponse, status_code=status.HTTP_202_ACCEPTED)
def create_podcast_order(
    req: PodcastOrderRequest,
    _: str = Depends(require_auth),
) -> PodcastOrderResponse:
    """Submit a new podcast show notes order and queue it as a Celery task."""
    from aiplatform.worker import run_podcast_order as celery_task

    order_id = req.order_id or f"podcast-{uuid.uuid4().hex[:8]}"
    order = {
        "order_id":     order_id,
        "audio_url":    req.audio_url,
        "tier":         req.tier,
        "show_name":    req.show_name or "",
        "client_email": req.client_email,
        "status":       "pending",
    }
    # Write initial job record immediately — ensures the job is visible in the
    # jobs list even if the worker hasn't picked up the task yet or fails.
    from aiplatform.database.job_ops import upsert_job
    upsert_job(order, "content_studio")

    task = celery_task.delay(order)
    # Update the job row with the Celery task ID now that we have it.
    upsert_job(order, "content_studio", celery_task_id=task.id)

    return PodcastOrderResponse(order_id=order_id, celery_task_id=task.id)


@router.get("/orders", response_model=JobListResponse)
def list_podcast_orders(
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobListResponse:
    items = (
        db.query(Job)
        .filter(Job.venture == "content_studio")
        .order_by(Job.created_at.desc())
        .limit(50)
        .all()
    )
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
