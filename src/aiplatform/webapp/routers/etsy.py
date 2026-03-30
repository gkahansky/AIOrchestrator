"""Etsy venture router — phase triggers + status."""

from fastapi import APIRouter, Depends, HTTPException, status

from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import EtsyPhaseResponse, EtsyRunPhaseRequest

router = APIRouter()


@router.post("/run", response_model=EtsyPhaseResponse)
def run_etsy_phase(
    req: EtsyRunPhaseRequest,
    _: str = Depends(require_auth),
) -> EtsyPhaseResponse:
    """Queue an Etsy pipeline phase via Celery."""
    from aiplatform.webapp.worker import run_etsy_phase as celery_task

    task = celery_task.delay(req.phase, req.params)
    return EtsyPhaseResponse(celery_task_id=task.id, phase=req.phase)


@router.get("/status/{task_id}")
def etsy_task_status(
    task_id: str,
    _: str = Depends(require_auth),
) -> dict:
    """Poll Celery task status for an Etsy phase run."""
    from celery.result import AsyncResult
    from aiplatform.webapp.worker import celery_app

    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "state": result.state,
        "result": result.result if result.ready() else None,
        "traceback": result.traceback if result.failed() else None,
    }
