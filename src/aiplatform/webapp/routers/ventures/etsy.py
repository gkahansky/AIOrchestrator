"""
Etsy venture router.

  POST /api/ventures/etsy/phase/{n}   — queue a pipeline phase via Celery
  GET  /api/ventures/etsy/listings    — list Etsy jobs from the DB
  GET  /api/ventures/etsy/themes      — scored themes from latest Phase 1 run
  GET  /api/ventures/etsy/subjects    — subjects from latest Phase 2 run
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
    """Return scored themes from the most recent Phase 1 job or Drive fallback."""
    themes_raw = []
    run_date = None

    # 1. DB: prefer phase_current==1; status filter deliberately omitted so jobs
    #    that stalled at "running" (silent _etsy_update_job failure) are still found.
    candidates = (
        db.query(Job)
        .filter(Job.venture == "etsy")
        .order_by(Job.created_at.desc())
        .limit(50)
        .all()
    )
    for j in candidates:
        out = j.output_data or {}
        raw = out.get("themes") or out.get("result", {}).get("themes")
        if raw:
            themes_raw = raw
            run_date = out.get("run_date") or out.get("result", {}).get("run_date")
            break

    # 2. Drive fallback — scan /01-research/ for the most recent themes JSON file
    if not themes_raw:
        try:
            import json as _json
            import os as _os
            from aiplatform.skills.storage.drive_organise import list_folder
            from aiplatform.skills.storage.drive_read import drive_read
            import tempfile
            drive_folder = _os.environ.get("DRIVE_01_RESEARCH_ID", "")
            if drive_folder:
                files = list_folder(drive_folder)
                json_files = sorted(
                    [f for f in files if f["name"].endswith(".json")],
                    key=lambda f: f["name"], reverse=True,
                )
                if json_files:
                    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                        tmp_path = tmp.name
                    drive_read(json_files[0]["file_id"], tmp_path)
                    data = _json.loads(open(tmp_path).read())
                    themes_raw = data.get("themes", [])
                    run_date = data.get("run_date")
        except Exception:
            pass  # Drive unavailable — return empty

    if not themes_raw:
        return {"themes": [], "run_date": None}

    return {
        "run_date": run_date,
        "themes": [
            {
                "theme": t.get("theme"),
                "score": t.get("score") or t.get("total_score"),
                "proceed": t.get("proceed", False),
            }
            for t in themes_raw
            if t.get("theme")
        ],
    }


@router.get("/subjects")
def get_etsy_subjects(
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> dict:
    """Return subjects from the most recent completed Phase 2 job."""
    job = (
        db.query(Job)
        .filter(
            Job.venture == "etsy",
            Job.status == "completed",
            Job.phase_current == 2,
        )
        .order_by(Job.created_at.desc())
        .first()
    )

    if not job:
        candidates = (
            db.query(Job)
            .filter(Job.venture == "etsy", Job.status == "completed")
            .order_by(Job.created_at.desc())
            .limit(20)
            .all()
        )
        for j in candidates:
            if j.output_data and j.output_data.get("subjects"):
                job = j
                break

    if not job or not job.output_data:
        return {"subjects": [], "theme": None}

    out = job.output_data
    subjects = out.get("subjects", [])
    return {
        "theme": out.get("theme"),
        "theme_slug": out.get("theme_slug"),
        "subjects": [
            {
                "subject_id": s.get("subject_id"),
                "title_draft": s.get("title_draft"),
                "quality_tier": s.get("quality_tier"),
                "price_usd": s.get("price_usd"),
                "subject": s,  # full dict for passing to phase 3/4
            }
            for s in subjects
        ],
    }
