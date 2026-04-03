"""
Etsy venture router.

  POST /api/ventures/etsy/phase/{n}   — queue a pipeline phase via Celery
  GET  /api/ventures/etsy/listings    — list Etsy jobs from the DB
  GET  /api/ventures/etsy/themes      — scored themes from latest Phase 1 run
"""

from typing import Any

from fastapi import APIRouter, Body, Depends, Path

from aiplatform.database.models import Job
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import (
    EtsyListing,
    EtsyListingsResponse,
    EtsyPhaseResponse,
)

router = APIRouter()


@router.post("/phase/{n}", response_model=EtsyPhaseResponse)
def run_etsy_phase(
    n: int = Path(..., ge=1, le=7),
    params: dict[str, Any] = Body(default_factory=dict),
    _: str = Depends(require_auth),
) -> EtsyPhaseResponse:
    """Queue an Etsy pipeline phase as a Celery task. Body is optional extra params."""
    import uuid
    from aiplatform.worker import run_etsy_phase as celery_task
    from aiplatform.database.job_ops import upsert_job

    job_id = params.get("job_id") or str(uuid.uuid4())
    params["job_id"] = job_id

    order = {"order_id": job_id, "phase": n, "status": "pending", **params}
    upsert_job(order, "etsy")

    task = celery_task.delay(n, params)
    upsert_job(order, "etsy", celery_task_id=task.id)

    return EtsyPhaseResponse(celery_task_id=task.id, phase=n)


@router.get("/listings", response_model=EtsyListingsResponse)
def get_etsy_listings(
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> EtsyListingsResponse:
    """Return all Etsy jobs (subjects), mapped to listing objects for the UI."""
    jobs = (
        db.query(Job)
        .filter(Job.venture == "etsy")
        .order_by(Job.created_at.desc())
        .limit(200)
        .all()
    )

    listings = []
    for job in jobs:
        out = job.output_data or {}
        inp = job.input_data  or {}
        listings.append(
            EtsyListing(
                listing_id=out.get("listing_id") or inp.get("listing_id"),
                title=out.get("title") or inp.get("title") or inp.get("slug"),
                status=job.status,
                drive_folder=out.get("drive_folder_url") or out.get("drive_folder"),
                tags=out.get("tags", []),
                price_usd=out.get("price_usd") or inp.get("price_usd"),
                created_at=job.created_at,
            )
        )

    return EtsyListingsResponse(items=listings, total=len(listings))


@router.get("/themes")
def get_etsy_themes(
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    """Return scored themes from the most recent completed Phase 1 job."""
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import JSONB

    job = (
        db.query(Job)
        .filter(
            Job.venture == "etsy",
            Job.status == "completed",
            cast(Job.input_data["phase"].astext, type_=None).isnot(None),
        )
        .filter(Job.input_data["phase"].astext == "1")
        .order_by(Job.created_at.desc())
        .first()
    )

    if not job or not job.output_data:
        return {"themes": [], "run_date": None}

    themes = job.output_data.get("themes", [])
    return {
        "run_date": job.output_data.get("run_date"),
        "themes": [
            {
                "theme": t.get("theme"),
                "score": t.get("total_score") or t.get("score"),
                "proceed": t.get("proceed", False),
            }
            for t in themes
        ],
    }
