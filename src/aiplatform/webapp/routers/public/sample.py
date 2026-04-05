"""
Public sample endpoints — no authentication required.

  POST /api/sample/podcast   — upload audio/video, get a watermarked sample PDF by email
  POST /api/sample/audit     — provide a URL, get a censored sample audit PDF by email

Rate limit: one request per email per 24 hours (enforced via DB).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, status

from aiplatform.database.models import Job
from aiplatform.database.session import get_db

router = APIRouter()

_ALLOWED_AUDIO_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".mpeg", ".mpga", ".ogg"}
_MAX_UPLOAD_BYTES    = 200 * 1024 * 1024   # 200 MB


# ─── helpers ──────────────────────────────────────────────────────────────────

def _check_rate_limit(email: str, venture: str, db) -> None:
    """Raise 429 if this email already submitted a sample in the last 24 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    existing = (
        db.query(Job)
        .filter(
            Job.venture == venture,
            Job.created_at >= cutoff,
            Job.input_data["sample_email"].astext != None,  # noqa: E711 — only sample jobs
        )
        .all()
    )
    for job in existing:
        if (job.input_data or {}).get("sample_email", "").lower() == email.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="You already requested a sample in the last 24 hours. Check your inbox.",
            )


def _upload_audio_to_drive(file: UploadFile, order_id: str) -> tuple[str, str]:
    """
    Save uploaded file to a temp path, upload to Drive, return (drive_file_id, suffix).
    Falls back to local path storage if Drive is not configured.
    """
    suffix = Path(file.filename or "audio.mp3").suffix.lower() or ".mp3"
    tmp_dir = Path("/tmp") / order_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"audio{suffix}"

    content = file.file.read()
    tmp_path.write_bytes(content)

    drive_folder = os.environ.get("DRIVE_SAMPLES_FOLDER_ID") or os.environ.get("DRIVE_PODCAST_ROOT_ID", "")
    if drive_folder:
        from aiplatform.skills.storage.drive_write import drive_write
        result = drive_write(str(tmp_path), drive_folder, filename=f"{order_id}{suffix}")
        return result["file_id"], suffix

    # Drive not configured — keep local path and pass as audio_path directly.
    # NOTE: this only works if the web and worker services share a filesystem.
    return "", suffix


# ─── POST /api/sample/podcast ─────────────────────────────────────────────────

@router.post("/podcast", status_code=status.HTTP_202_ACCEPTED)
async def request_podcast_sample(
    email:         str                  = Form(...),
    show_name:     str                  = Form(default=""),
    episode_title: str                  = Form(default="Sample Episode"),
    host_name:     str                  = Form(default=""),
    audio:         UploadFile | None    = File(default=None),
    db=Depends(get_db),
) -> dict:
    """
    Accept an audio/video upload (or use demo audio) and email a watermarked sample.
    One request per email per 24 hours.
    """
    _check_rate_limit(email, "content_studio", db)

    order_id = f"sample-pod-{uuid.uuid4().hex[:10]}"
    use_demo = audio is None or not audio.filename

    if use_demo:
        # No file uploaded — run in demo mode (uses built-in demo transcript)
        drive_audio_id, audio_suffix = "", ".mp3"
        order: dict = {
            "order_id":              order_id,
            "sample_email":          email,
            "show_name":             show_name or "My Podcast",
            "episode_title":         episode_title or "Sample Episode",
            "host_name":             host_name,
            "tier":                  "standard",
            "status":                "pending",
            "demo":                  True,
            "drive_audio_id":        "",
            "audio_filename_suffix": audio_suffix,
        }
    else:
        # Validate file type
        suffix = Path(audio.filename or "").suffix.lower()
        if suffix not in _ALLOWED_AUDIO_EXTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported file type '{suffix}'. Accepted: mp3, mp4, m4a, wav, webm.",
            )

        # Read and check size
        content = await audio.read()
        if len(content) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large. Maximum 200 MB.",
            )
        from io import BytesIO
        audio.file = BytesIO(content)

        drive_audio_id, audio_suffix = _upload_audio_to_drive(audio, order_id)
        order = {
            "order_id":              order_id,
            "sample_email":          email,
            "show_name":             show_name or "My Podcast",
            "episode_title":         episode_title or "Sample Episode",
            "host_name":             host_name,
            "tier":                  "standard",
            "status":                "pending",
            "drive_audio_id":        drive_audio_id,
            "audio_filename_suffix": audio_suffix,
        }
        if not drive_audio_id:
            order["audio_path"] = str(Path("/tmp") / order_id / f"audio{audio_suffix}")

    # Persist job record
    from aiplatform.database.job_ops import upsert_job
    upsert_job(order, "content_studio")

    # Queue Celery task
    from aiplatform.worker import run_podcast_sample as celery_task
    task = celery_task.delay(order)
    upsert_job(order, "content_studio", celery_task_id=task.id)

    return {
        "message": "Your sample is being generated — check your inbox in 5–10 minutes.",
        "order_id": order_id,
    }


# ─── POST /api/sample/audit ───────────────────────────────────────────────────

@router.post("/audit", status_code=status.HTTP_202_ACCEPTED)
def request_audit_sample(
    email: str = Form(...),
    url:   str = Form(...),
    db=Depends(get_db),
) -> dict:
    """
    Run a full marketing audit on the provided URL and email a censored sample PDF.
    One request per email per 24 hours.
    """
    # Basic URL normalisation
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    _check_rate_limit(email, "marketing_audit", db)

    order_id = f"sample-aud-{uuid.uuid4().hex[:10]}"
    order: dict = {
        "order_id":    order_id,
        "sample_email": email,
        "client_email": "",
        "url":         url,
        "tier":        "full",
        "report_type": "sample",
        "status":      "pending",
    }

    from aiplatform.database.job_ops import upsert_job
    upsert_job(order, "marketing_audit")

    from aiplatform.worker import run_audit_sample as celery_task
    task = celery_task.delay(order)
    upsert_job(order, "marketing_audit", celery_task_id=task.id)

    return {
        "message": "Your audit sample is being generated — check your inbox in 10–20 minutes.",
        "order_id": order_id,
    }
