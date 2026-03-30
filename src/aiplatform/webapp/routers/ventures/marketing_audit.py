"""
Marketing Audit venture router.

  POST /api/ventures/marketing-audit/orders   — create a new audit order
  GET  /api/ventures/marketing-audit/orders   — list audit orders
  GET  /api/ventures/marketing-audit/orders/{order_id}
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from aiplatform.database.models import Job
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import (
    AuditOrderRequest,
    AuditOrderResponse,
    JobDetail,
    JobListResponse,
    JobSummary,
)

router = APIRouter()


@router.post("/orders", response_model=AuditOrderResponse, status_code=status.HTTP_202_ACCEPTED)
def create_audit_order(
    req: AuditOrderRequest,
    _: str = Depends(require_auth),
) -> AuditOrderResponse:
    """Submit a new marketing audit order and queue it as a Celery task."""
    from aiplatform.worker import run_audit_order as celery_task

    order_id = req.order_id or f"audit-{uuid.uuid4().hex[:8]}"
    order = {
        "order_id":     order_id,
        "url":          req.url,
        "tier":         req.tier,
        "report_type":  req.report_type,
        "client_email": req.client_email,
        "status":       "pending",
    }
    task = celery_task.delay(order)
    return AuditOrderResponse(order_id=order_id, celery_task_id=task.id)


@router.get("/orders", response_model=JobListResponse)
def list_audit_orders(
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobListResponse:
    items = (
        db.query(Job)
        .filter(Job.venture == "marketing_audit")
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
def get_audit_order(
    order_id: str,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> JobDetail:
    job = db.query(Job).filter(
        Job.venture == "marketing_audit",
        Job.input_data["order_id"].astext == order_id,
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return JobDetail.model_validate(job)
