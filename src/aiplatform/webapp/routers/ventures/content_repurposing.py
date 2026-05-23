"""
Content Repurposing venture router.

Admin-triggered pipeline (planBadmin.com).
Operator uploads the video file directly; the router writes it to Drive and
passes the Drive file ID to the Celery worker.

  POST /api/ventures/content-repurposing/jobs   — queue a new repurposing job
  GET  /api/ventures/content-repurposing/jobs   — list jobs (newest first)
  GET  /api/ventures/content-repurposing/jobs/{job_id}   — job detail + clips
  POST /api/ventures/content-repurposing/jobs/{job_id}/approve — mark done / deliver
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aiplatform.database.models import CRJob, CRClipAsset
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth

router = APIRouter()

_VALID_PLANS = {"free", "starter", "pro", "studio"}
_ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mpeg", ".wmv"}
_MAX_VIDEO_BYTES = int(os.getenv("CR_MAX_UPLOAD_MB", "2000")) * 1024 * 1024


# ── Schemas ────────────────────────────────────────────────────────────────────

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


class CRChapterOut(BaseModel):
    index: int
    title: str
    start_s: float
    end_s: float
    summary: str


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
    chapters: list[CRChapterOut] | None = None
    suggested_chapter_ids: list[int] | None = None


class CRJobSummary(BaseModel):
    id: str
    status: str
    plan: str
    show_name: str | None
    episode_title: str | None
    clip_count: int | None
    error_message: str | None
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
    chapters = None
    if job.chapters_json:
        chapters = [
            CRChapterOut(
                index=ch.get("index", i),
                title=ch.get("title", f"Chapter {i+1}"),
                start_s=float(ch.get("start_s", 0)),
                end_s=float(ch.get("end_s", 0)),
                summary=ch.get("summary", ""),
            )
            for i, ch in enumerate(job.chapters_json)
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
        chapters=chapters,
        suggested_chapter_ids=list(job.selected_chapter_ids) if job.selected_chapter_ids else None,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_cr_job(
    plan:           str              = Form("starter"),
    show_name:      str              = Form(default=""),
    episode_title:  str              = Form(default=""),
    host_name:      str              = Form(default=""),
    guest_name:     str              = Form(default=""),
    client_email:   str              = Form(default=""),
    niche:          str              = Form(default="general"),
    audience:       str              = Form(default="general audience"),
    brand_voice:       str              = Form(default=""),
    clip_instructions: str              = Form(default=""),
    video:             UploadFile | None = File(default=None),
    db:             Session          = Depends(get_db),
    _:              str              = Depends(require_auth),
) -> dict:
    """
    Queue a content repurposing job.

    Accepts multipart/form-data with a video file upload.
    The video is written to Drive; the worker downloads it from there.
    Returns job_id immediately; poll GET /jobs/{job_id} for status.
    """
    if plan not in _VALID_PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan '{plan}'. Must be one of: {sorted(_VALID_PLANS)}",
        )

    if video is None or not video.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A video file is required.",
        )

    suffix = Path(video.filename).suffix.lower()
    if suffix not in _ALLOWED_VIDEO_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported file type '{suffix}'. "
                f"Supported: {', '.join(sorted(_ALLOWED_VIDEO_EXTS))}."
            ),
        )

    content = await video.read()
    if len(content) > _MAX_VIDEO_BYTES:
        limit_mb = _MAX_VIDEO_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum {limit_mb} MB.",
        )

    # Write to tmp then upload to Drive (worker + web are separate containers)
    job_id = uuid.uuid4()
    tmp_dir = Path("/tmp") / f"cr_{job_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"source{suffix}"
    tmp_path.write_bytes(content)

    drive_root = (
        os.environ.get("DRIVE_CR_ROOT_ID")
        or os.environ.get("DRIVE_PODCAST_ORDERS_ID", "")
    )
    if not drive_root:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Drive is not configured (DRIVE_PODCAST_ORDERS_ID missing).",
        )

    try:
        from aiplatform.skills.storage.drive_write import drive_write
        result = drive_write(str(tmp_path), drive_root, filename=f"cr_{job_id}{suffix}")
        drive_video_id = result["file_id"]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to upload video to Google Drive: {exc}",
        )
    finally:
        tmp_path.unlink(missing_ok=True)
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    order = {
        "plan":           plan,
        "drive_video_id": drive_video_id,
        "video_suffix":   suffix,
        "show_name":      show_name or "",
        "episode_title":  episode_title or "",
        "host_name":      host_name or "",
        "guest_name":     guest_name or "",
        "client_email":   client_email or "",
        "niche":          niche or "general",
        "audience":       audience or "general audience",
        "brand_voice":       brand_voice or "",
        "clip_instructions": clip_instructions or "",
    }

    job = CRJob(
        id=job_id,
        status="pending",
        plan=plan,
        show_name=show_name or None,
        episode_title=episode_title or None,
        client_email=client_email or None,
        input_data=order,
    )
    db.add(job)
    db.commit()

    # CRM ingestion (H-11): record the paying customer.
    from aiplatform.database.crm_ops import ingest_customer
    ingest_customer(client_email or None, "content_repurposing")

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
            error_message=j.error_message,
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
            pass

    return {"job_id": job_id, "status": "delivered"}


@router.get("/jobs/{job_id}/chapters")
async def get_cr_job_chapters(
    job_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """Return generated chapters for a job (populated after transcription, before chapter_review)."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id")

    job = db.query(CRJob).filter(CRJob.id == uid).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return {"job_id": job_id, "chapters": job.chapters_json or []}


class ChapterApproveRequest(BaseModel):
    selected_ids: list[int] | None = None   # None or [] → use all chapters


@router.post("/jobs/{job_id}/chapters/approve", status_code=status.HTTP_202_ACCEPTED)
async def approve_cr_job_chapters(
    job_id: str,
    body: ChapterApproveRequest = Body(default=ChapterApproveRequest()),
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """
    Accept the admin's chapter selection and dispatch Phase 2.

    body.selected_ids: list of chapter indexes to clip from.
    Empty list or null → use all chapters (automatic virality selection on full episode).
    Only valid when job status == 'chapter_review'.
    """
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id")

    job = db.query(CRJob).filter(CRJob.id == uid).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status != "chapter_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is in status '{job.status}', not 'chapter_review'.",
        )

    selected_ids = body.selected_ids if body.selected_ids else None

    job.status = "pending"
    job.selected_chapter_ids = selected_ids
    job.error_message = None
    db.commit()

    from aiplatform.worker import run_cr_job_resume
    order = job.input_data or {}
    task = run_cr_job_resume.delay(str(job_id), order, selected_ids)

    job.celery_task_id = task.id
    db.commit()

    return {
        "job_id":        job_id,
        "status":        "pending",
        "selected_ids":  selected_ids,
        "message":       "Phase 2 queued. Clips will be processed from selected chapters.",
    }


@router.post("/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_cr_job(
    job_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """Re-queue a failed job using the same input_data (no re-upload needed)."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id")

    job = db.query(CRJob).filter(CRJob.id == uid).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    _RETRYABLE = {
        "failed", "cancelled",
        # allow manual retry of stuck in-progress jobs (e.g. after a deploy interrupted them)
        "pending", "downloading", "transcribing", "chapter_review",
        "scoring", "processing", "generating_text", "packaging",
    }
    if job.status not in _RETRYABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is in status '{job.status}'; cannot retry from this state.",
        )

    job.status = "pending"
    job.error_message = None
    job.celery_task_id = None
    job.completed_at = None
    db.commit()

    from aiplatform.worker import run_cr_job
    order = job.input_data or {}
    task = run_cr_job.delay(str(job_id), order)

    job.celery_task_id = task.id
    db.commit()

    return {"job_id": job_id, "status": "pending", "message": "Job re-queued."}


@router.post("/jobs/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_cr_job(
    job_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """Cancel a job that is stuck or still queued. Sets status to cancelled."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id")

    job = db.query(CRJob).filter(CRJob.id == uid).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    _NOT_CANCELLABLE = {"delivered", "cancelled"}
    if job.status in _NOT_CANCELLABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is already in status '{job.status}'; cannot cancel.",
        )

    # Revoke the Celery task if one is running (best-effort — task may have already finished)
    if job.celery_task_id:
        try:
            from aiplatform.worker import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass  # non-fatal — DB state is the source of truth

    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"job_id": job_id, "status": "cancelled", "message": "Job cancelled."}
