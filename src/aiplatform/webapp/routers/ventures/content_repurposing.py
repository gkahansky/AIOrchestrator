"""
Content Repurposing venture router.

Admin-triggered pipeline (planBadmin.com).
The operator uploads the video to Drive first, then submits the Drive file ID here.

  POST /api/ventures/content-repurposing/jobs   — queue a new repurposing job
  GET  /api/ventures/content-repurposing/jobs   — list jobs (newest first)
  GET  /api/ventures/content-repurposing/jobs/{job_id}   — job detail + clips
  POST /api/ventures/content-repurposing/jobs/{job_id}/approve — mark done / deliver
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aiplatform.database.models import CRJob, CRClipAsset
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth

router = APIRouter()

_VALID_PLANS = {"free", "starter", "pro", "studio"}

_MIME_TO_EXT = {
    "video/mp4":        ".mp4",
    "video/quicktime":  ".mov",
    "video/x-matroska": ".mkv",
    "video/x-msvideo":  ".avi",
    "video/webm":       ".webm",
    "video/mpeg":       ".mpeg",
    "video/x-ms-wmv":   ".wmv",
    "video/3gpp":       ".3gp",
}


def _detect_video_suffix(drive_video_id: str) -> str:
    """Detect video extension from Drive file metadata. Raises 400 if unsupported."""
    from aiplatform.skills.storage._drive_auth import get_drive_service
    try:
        svc = get_drive_service()
        meta = svc.files().get(fileId=drive_video_id, fields="mimeType,name").execute()
        mime = meta.get("mimeType", "")
        name = meta.get("name", "")

        if mime in _MIME_TO_EXT:
            return _MIME_TO_EXT[mime]

        for ext in _MIME_TO_EXT.values():
            if name.lower().endswith(ext):
                return ext

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported video format '{mime}' (file: {name!r}). "
                "Supported: MP4, MOV, MKV, AVI, WebM."
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read Drive file metadata for ID '{drive_video_id}': {exc}",
        )


# ── Schemas ────────────────────────────────────────────────────────────────────

class CROrderRequest(BaseModel):
    plan: str = "starter"
    drive_video_id: str                 # Drive file ID of the uploaded video
    show_name: str = ""
    episode_title: str = ""
    host_name: str = ""
    guest_name: str = ""
    client_email: str = ""
    niche: str = "general"
    audience: str = "general audience"
    brand_voice: str = ""              # Studio plan only — brand voice guide text


class CRClipOut(BaseModel):
    id: int
    clip_index: int
    start_s: float
    end_s: float
    virality_score: float | None
    hook: str | None
    drive_clip_id: str | None
    drive_thumbnail_id: str | None
    title: str | None
    platform: str | None
    created_at: str


class CRJobDetail(BaseModel):
    id: str
    status: str
    plan: str
    show_name: str | None
    episode_title: str | None
    client_email: str | None
    drive_folder_id: str | None
    clip_count: int | None
    video_duration_s: float | None
    error_message: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    clips: list[CRClipOut]


class CRJobSummary(BaseModel):
    id: str
    status: str
    plan: str
    show_name: str | None
    episode_title: str | None
    clip_count: int | None
    created_at: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _job_to_detail(job: CRJob) -> CRJobDetail:
    clips = [
        CRClipOut(
            id=c.id,
            clip_index=c.clip_index,
            start_s=c.start_s,
            end_s=c.end_s,
            virality_score=c.virality_score,
            hook=c.hook,
            drive_clip_id=c.drive_clip_id,
            drive_thumbnail_id=c.drive_thumbnail_id,
            title=c.title,
            platform=c.platform,
            created_at=c.created_at.isoformat(),
        )
        for c in (job.clips or [])
    ]
    return CRJobDetail(
        id=str(job.id),
        status=job.status,
        plan=job.plan,
        show_name=job.show_name,
        episode_title=job.episode_title,
        client_email=job.client_email,
        drive_folder_id=job.drive_folder_id,
        clip_count=job.clip_count,
        video_duration_s=job.video_duration_s,
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        clips=clips,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_cr_job(
    payload: CROrderRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """
    Queue a content repurposing job.

    The video must already be uploaded to Google Drive.
    Returns the job_id immediately; poll GET /jobs/{job_id} for status.
    """
    if payload.plan not in _VALID_PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan '{payload.plan}'. Must be one of: {sorted(_VALID_PLANS)}",
        )

    video_suffix = _detect_video_suffix(payload.drive_video_id)

    job_id = uuid.uuid4()
    order = payload.model_dump()
    order["video_suffix"] = video_suffix   # injected by backend; not in request schema

    job = CRJob(
        id=job_id,
        status="pending",
        plan=payload.plan,
        show_name=payload.show_name or None,
        episode_title=payload.episode_title or None,
        client_email=payload.client_email or None,
        input_data=order,
    )
    db.add(job)
    db.commit()

    # Dispatch Celery task
    from aiplatform.worker import run_cr_job
    task = run_cr_job.delay(str(job_id), order)

    job.celery_task_id = task.id
    db.commit()

    return {
        "job_id": str(job_id),
        "status": "pending",
        "message": "Job queued. Poll GET /jobs/{job_id} for status.",
    }


@router.get("/jobs", response_model=list[CRJobSummary])
async def list_cr_jobs(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> list[CRJobSummary]:
    """List content repurposing jobs, newest first."""
    jobs = (
        db.query(CRJob)
        .order_by(CRJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        CRJobSummary(
            id=str(j.id),
            status=j.status,
            plan=j.plan,
            show_name=j.show_name,
            episode_title=j.episode_title,
            clip_count=j.clip_count,
            created_at=j.created_at.isoformat(),
        )
        for j in jobs
    ]


@router.get("/jobs/{job_id}", response_model=CRJobDetail)
async def get_cr_job(
    job_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> CRJobDetail:
    """Get job detail including all clip assets."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id")

    job = db.query(CRJob).filter(CRJob.id == uid).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return _job_to_detail(job)


@router.post("/jobs/{job_id}/approve", status_code=status.HTTP_200_OK)
async def approve_cr_job(
    job_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """
    Mark a review_pending job as approved and trigger delivery email.
    Only valid when status == 'review_pending'.
    """
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id")

    job = db.query(CRJob).filter(CRJob.id == uid).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status != "review_pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is in status '{job.status}', not 'review_pending'.",
        )

    job.status = "delivered"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()

    # Send delivery email if client_email is set
    if job.client_email:
        try:
            from aiplatform.skills.comms.send_email import send_email
            drive_link = (
                f"https://drive.google.com/drive/folders/{job.drive_folder_id}"
                if job.drive_folder_id else ""
            )
            send_email(
                to=job.client_email,
                subject=f"Your Content Pack is Ready — {job.episode_title or job_id}",
                body_html=(
                    f"<p>Hi,</p>"
                    f"<p>Your content repurposing pack for <b>{job.episode_title or 'your episode'}</b> is ready.</p>"
                    f"<p>Clips generated: <b>{job.clip_count or 0}</b></p>"
                    + (f'<p><a href="{drive_link}">View your files in Google Drive &rarr;</a></p>' if drive_link else "")
                    + "<p>— EchoForge</p>"
                ),
            )
        except Exception:
            pass  # never block approval on email failure

    return {"job_id": job_id, "status": "delivered"}
