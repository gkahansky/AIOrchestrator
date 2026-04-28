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
_ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
_ALLOWED_MEDIA_EXTS = _ALLOWED_AUDIO_EXTS | _ALLOWED_VIDEO_EXTS

_MAX_AUDIO_BYTES = 200 * 1024 * 1024   # 200 MB — Service A
_MAX_VIDEO_BYTES = 500 * 1024 * 1024   # 500 MB — Service B

_SERVICE_A_TIERS = {"starter", "standard", "premium"}
_SERVICE_B_TIERS = {"starter", "standard", "pro"}


@router.post("/orders", response_model=PodcastOrderResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_podcast_order(
    service_type:         str              = Form("show_notes"),
    tier:                 str              = Form("standard"),
    client_email:         str              = Form(default=""),
    show_name:            str              = Form(default=""),
    episode_title:        str              = Form(default=""),
    host_name:            str              = Form(default=""),
    guest_name:           str              = Form(default=""),
    special_instructions: str              = Form(default=""),
    niche:                str              = Form(default=""),
    audience:             str              = Form(default=""),
    show_url:             str              = Form(default=""),
    guest_expertise:      str              = Form(default=""),
    competitor_urls:      str              = Form(default=""),
    show_concept:         str              = Form(default=""),
    host_background:      str              = Form(default=""),
    launch_type:          str              = Form(default="new"),
    bundle_sku:           str              = Form(default=""),
    add_ons:              str              = Form(default=""),
    order_id:             str | None       = Form(default=None),
    audio:                UploadFile | None = File(default=None),
    _: str = Depends(require_auth),
) -> PodcastOrderResponse:
    """Submit a new content studio order (Service A: show notes, or Service B: repurposing pack)."""
    from aiplatform.worker import run_podcast_order as celery_task

    if service_type not in ("show_notes", "repurposing_pack"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="service_type must be show_notes or repurposing_pack")

    # ── Bundle expansion ──────────────────────────────────────────────────────
    # If a bundle SKU is supplied, override tier + add_ons from the bundle config.
    resolved_add_ons: list[str] = [a.strip() for a in add_ons.split(",") if a.strip()]
    if bundle_sku:
        from ventures.content_studio.config import BUNDLES
        bundle_cfg = BUNDLES.get(bundle_sku)
        if not bundle_cfg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown bundle_sku '{bundle_sku}'. Valid: {', '.join(BUNDLES)}",
            )
        tier = bundle_cfg["requires_tier"]
        # Bundles are always Service A (show notes) packages
        service_type = "show_notes"
        # Merge bundle add-ons with any explicitly passed add-ons (deduplicated)
        resolved_add_ons = list(dict.fromkeys(bundle_cfg["add_ons"] + resolved_add_ons))

    valid_tiers = _SERVICE_A_TIERS if service_type == "show_notes" else _SERVICE_B_TIERS
    if tier not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"tier must be one of: {', '.join(sorted(valid_tiers))} for service_type={service_type}",
        )

    order_id = order_id or f"podcast-{uuid.uuid4().hex[:8]}"

    # ── Handle file upload ────────────────────────────────────────────────────
    if audio is None or not audio.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A media file is required.",
        )

    suffix = Path(audio.filename or "").suffix.lower()
    is_video = suffix in _ALLOWED_VIDEO_EXTS

    if suffix not in _ALLOWED_MEDIA_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported file type '{suffix}'. "
                f"Audio: {', '.join(sorted(_ALLOWED_AUDIO_EXTS))}. "
                f"Video (Service B only): {', '.join(sorted(_ALLOWED_VIDEO_EXTS))}."
            ),
        )

    if is_video and service_type != "repurposing_pack":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Video files are only accepted for service_type=repurposing_pack.",
        )

    content = await audio.read()
    max_bytes = _MAX_VIDEO_BYTES if is_video else _MAX_AUDIO_BYTES
    if len(content) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum {limit_mb} MB for this service.",
        )

    # Always write to /tmp first
    tmp_dir = Path("/tmp") / order_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"audio{suffix}"
    tmp_path.write_bytes(content)

    # ── Duration check for audio-only Service A ───────────────────────────────
    if not is_video:
        try:
            from mutagen import File as MutagenFile
            audio_meta = MutagenFile(tmp_path)
            if audio_meta and audio_meta.info and hasattr(audio_meta.info, "length"):
                duration_mins = audio_meta.info.length / 60
                tier_limits = {"starter": 30, "standard": 60, "premium": 90}
                limit = tier_limits.get(tier, 90)
                if duration_mins > limit + 5:
                    tmp_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Duration mismatch: Selected tier '{tier}' covers up to {limit} mins. "
                            f"Your file is {int(duration_mins)} mins."
                        ),
                    )
        except ImportError:
            pass
        except HTTPException:
            raise
        except Exception:
            pass

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
            detail=f"Failed to upload media to Google Drive: {exc}",
        )

    order = {
        "order_id":              order_id,
        "service_type":          service_type,
        "tier":                  tier,
        "client_email":          client_email or None,
        "show_name":             show_name or "",
        "episode_title":         episode_title or "",
        "host_name":             host_name or "",
        "guest_name":            guest_name or "",
        "special_instructions":  special_instructions or "",
        "niche":                 niche or "general",
        "audience":              audience or "general audience",
        "show_url":              show_url or "",
        "guest_expertise":       guest_expertise or "",
        "competitor_urls":       competitor_urls or "",
        "show_concept":          show_concept or "",
        "host_background":       host_background or "",
        "launch_type":           launch_type or "new",
        "bundle_sku":            bundle_sku or "",
        "add_ons":               resolved_add_ons,
        "status":                "pending",
        "drive_audio_id":        drive_audio_id,
        "audio_filename_suffix": suffix,
        "input_type":            "video" if is_video else "audio",
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
