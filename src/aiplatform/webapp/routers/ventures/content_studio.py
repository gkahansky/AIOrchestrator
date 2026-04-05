"""
Content Studio (Podcast Notes) venture router.

  POST /api/ventures/content-studio/orders   — create a new podcast order (multipart/form-data)
  GET  /api/ventures/content-studio/orders   — list podcast orders
  GET  /api/ventures/content-studio/orders/{order_id}
"""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from aiplatform.database.models import Job
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import (
    JobDetail,
    JobListResponse,
    JobSummary,
    PodcastOrderResponse,
)

router = APIRouter()

_ALLOWED_AUDIO_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".mpeg", ".mpga", ".ogg", ".flac"}
_MAX_UPLOAD_BYTES   = 200 * 1024 * 1024  # 200 MB


@router.post("/orders", response_model=PodcastOrderResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_podcast_order(
    tier:                 str              = Form("standard"),
    client_email:         str              = Form(default=""),
    show_name:            str              = Form(default=""),
    episode_title:        str              = Form(default=""),
    host_name:            str              = Form(default=""),
    guest_name:           str              = Form(default=""),
    special_instructions: str              = Form(default=""),
    order_id:             str | None       = Form(default=None),
    audio:                UploadFile | None = File(default=None),
    _: str = Depends(require_auth),
) -> PodcastOrderResponse:
    """Submit a new podcast show notes order and queue it as a Celery task."""
    from aiplatform.worker import run_podcast_order as celery_task

    if tier not in ("starter", "standard", "premium"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="tier must be starter, standard, or premium")

    order_id = order_id or f"podcast-{uuid.uuid4().hex[:8]}"

    # ── Handle audio file upload ──────────────────────────────────────────────
    if audio is None or not audio.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An audio file is required.",
        )

    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in _ALLOWED_AUDIO_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{suffix}'. Accepted: mp3, mp4, m4a, wav, webm, flac.",
        )

    content = await audio.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum 200 MB.",
        )

    # Always write to /tmp first
    tmp_dir = Path("/tmp") / order_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"audio{suffix}"
    tmp_path.write_bytes(content)

    # Upload to Drive — required because web + worker are separate containers.
    drive_folder = os.environ.get("DRIVE_PODCAST_ROOT_ID", "") or os.environ.get("DRIVE_SAMPLES_FOLDER_ID", "")
    if not drive_folder:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Drive is not configured (DRIVE_PODCAST_ROOT_ID missing). Cannot accept file uploads.",
        )

    try:
        from aiplatform.skills.storage.drive_write import drive_write
        result = drive_write(str(tmp_path), drive_folder, filename=f"{order_id}{suffix}")
        drive_audio_id = result["file_id"]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to upload audio to Google Drive: {exc}",
        )

    order = {
        "order_id":              order_id,
        "tier":                  tier,
        "client_email":          client_email or None,
        "show_name":             show_name or "",
        "episode_title":         episode_title or "",
        "host_name":             host_name or "",
        "guest_name":            guest_name or "",
        "special_instructions":  special_instructions or "",
        "status":                "pending",
        "drive_audio_id":        drive_audio_id,
        "audio_filename_suffix": suffix,
    }
    # Write initial job record immediately — ensures the job is visible in the
    # jobs list even if the worker hasn't picked up the task yet or fails.
    from aiplatform.database.job_ops import upsert_job
    upsert_job(order, "content_studio")

    task = celery_task.delay(order)
    upsert_job(order, "content_studio", celery_task_id=task.id)

    from sqlalchemy.orm import Session
    db_sess: Session = next(get_db())
    job = db_sess.query(Job).filter(
        Job.venture == "content_studio",
        Job.input_data["order_id"].astext == order_id,
    ).first()
    job_id = str(job.id) if job else order_id

    return PodcastOrderResponse(job_id=job_id, order_id=order_id, celery_task_id=task.id)


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
