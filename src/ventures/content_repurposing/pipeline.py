"""
Content Repurposing pipeline.

Unified Service B+C: video → short clips + thumbnails + text artifacts.
Phases:
  1. Ingest & validate
  2. Audio extraction + Whisper transcription
  3. Virality scoring + clip selection
  4. Per-clip media processing (extract → transcode → captions → watermark)
  5. Per-clip thumbnail (frames → score → compose)
  6. Per-clip metadata (title + description)
  7. Text artifacts (show notes, blog, newsletter, captions pack)
  8. Package + deliver
"""

import os
import shutil
import tempfile
from pathlib import Path

from ventures.content_repurposing.config import (
    ANTHROPIC_API_KEY,
    CAPTION_STYLE,
    CLIP_TARGET_FORMAT,
    CLAUDE_MODEL,
    CR_TEMP_DIR,
    DRIVE_CR_ROOT_ID,
    HUMAN_REVIEW_EMAIL,
    OPENAI_API_KEY,
    PLANS,
)
from ventures.content_repurposing.clip_selector import select_clips

from aiplatform.skills.media.extract_audio_from_video import extract_audio_from_video
from aiplatform.skills.media.transcribe_audio import transcribe_audio
from aiplatform.skills.media.score_clip_virality import score_clip_virality
from aiplatform.skills.media.extract_video_segments import extract_video_segment
from aiplatform.skills.media.transcode_video import transcode_video
from aiplatform.skills.media.burn_captions import burn_captions, build_srt_for_clip
from aiplatform.skills.media.add_watermark import add_watermark
from aiplatform.skills.media.extract_video_frames import extract_video_frames
from aiplatform.skills.media.score_thumbnail_frame import score_thumbnail_frame
from aiplatform.skills.media.generate_thumbnail import generate_thumbnail
from aiplatform.skills.media.generate_clip_title import generate_clip_title
from aiplatform.skills.media.generate_video_description import generate_video_description
from aiplatform.skills.media.generate_show_notes import generate_show_notes
from aiplatform.skills.media.generate_blog_post import generate_blog_post
from aiplatform.skills.media.generate_newsletter_draft import generate_newsletter_draft
from aiplatform.skills.media.generate_caption_pack import generate_caption_pack
from aiplatform.skills.storage.drive_write import drive_write
from aiplatform.skills.storage.drive_organise import create_folder
from aiplatform.skills.storage.drive_read import drive_download
from aiplatform.skills.comms.send_email import send_email


def run_repurposing_job(job_id: str, order: dict) -> dict:
    """
    Run the full content repurposing pipeline for one job.

    Args:
        job_id: The CRJob UUID (string).
        order:  Dict with at minimum:
                  plan, drive_video_id, show_name, episode_title,
                  host_name, guest_name, client_email, niche, audience.

    Returns:
        {"status": "review_pending", "clip_count": int, "drive_folder_id": str}
    """
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import CRJob, CRClipAsset

    plan = order.get("plan", "starter")
    plan_cfg = PLANS.get(plan, PLANS["starter"])
    api_key = ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")

    tmp_dir = Path(CR_TEMP_DIR) / f"cr_{job_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        _set_status(job_id, "downloading")

        # ── Phase 1: Download source video from Drive ──────────────────────────
        drive_video_id = order["drive_video_id"]
        suffix = order.get("video_suffix", ".mp4")
        local_video = tmp_dir / f"source{suffix}"
        drive_download(drive_video_id, str(local_video))

        _set_status(job_id, "transcribing")

        # ── Phase 2: Audio extraction + Whisper transcription ─────────────────
        audio_result = extract_audio_from_video(
            str(local_video),
            output_path=str(tmp_dir / "audio.mp3"),
        )
        audio_path = audio_result["audio_path"]
        duration_s = audio_result.get("duration_seconds") or 0.0

        transcript_result = transcribe_audio(audio_path)
        transcript = transcript_result["transcript"]
        segments = transcript_result["segments"]
        duration_s = transcript_result.get("duration_seconds") or duration_s

        _update_transcript(job_id, transcript, segments, duration_s)

        # ── Phase 3: Virality scoring + clip selection ─────────────────────────
        _set_status(job_id, "scoring")

        max_candidates = plan_cfg["clips"] * 3   # score more, select best
        virality_result = score_clip_virality(
            transcript=transcript,
            segments=segments,
            duration_s=duration_s,
            max_clips=max_candidates,
            anthropic_api_key=api_key,
            model=CLAUDE_MODEL,
        )
        selected_clips = select_clips(virality_result["clips"], plan, PLANS)

        # Create Drive output folder
        drive_folder_id = _ensure_drive_folder(job_id, order)
        _update_folder(job_id, drive_folder_id)

        # ── Phase 4-6: Per-clip media processing ──────────────────────────────
        _set_status(job_id, "processing")

        clip_assets = []
        primary_platform = plan_cfg["caption_platforms"][0] if plan_cfg["caption_platforms"] else "tiktok"

        for i, clip_window in enumerate(selected_clips):
            clip_dir = tmp_dir / f"clip_{i}"
            clip_dir.mkdir(exist_ok=True)

            start_s = clip_window["start_s"]
            end_s = clip_window["end_s"]
            hook = clip_window.get("hook", "")
            chunk = clip_window.get("transcript_chunk", "")

            # Phase 4: Extract → transcode → captions → watermark
            seg_result = extract_video_segment(
                str(local_video), start_s, end_s,
                output_path=str(clip_dir / "raw.mp4"),
            )
            tc_result = transcode_video(
                seg_result["clip_path"],
                target_format=CLIP_TARGET_FORMAT,
                output_path=str(clip_dir / "transcoded.mp4"),
            )
            srt = build_srt_for_clip(segments, start_s, end_s)
            cap_result = burn_captions(
                tc_result["transcoded_path"],
                srt_content=srt,
                output_path=str(clip_dir / "captioned.mp4"),
                **CAPTION_STYLE,
            )
            wm_result = add_watermark(
                cap_result["captioned_path"],
                plan=plan,
                output_path=str(clip_dir / "final.mp4"),
            )
            final_clip_path = wm_result["final_path"]

            # Phase 5: Thumbnail
            frames_result = extract_video_frames(
                tc_result["transcoded_path"],   # use transcoded (pre-caption) for clean frames
                n=10,
                output_dir=str(clip_dir / "frames"),
            )
            frame_score = score_thumbnail_frame(
                frames_result["frame_paths"],
                transcript_chunk=chunk,
                anthropic_api_key=api_key,
            )
            thumb_result = generate_thumbnail(
                frame_score["best_frame"],
                title=hook[:80] or f"Clip {i+1}",
                show_name=order.get("show_name", ""),
                plan=plan,
                output_path=str(clip_dir / "thumbnail.jpg"),
            )

            # Phase 6: Title + description (primary platform only; full metadata in text artifacts)
            title_result = generate_clip_title(
                transcript_chunk=chunk,
                hook=hook,
                platform=primary_platform,
                anthropic_api_key=api_key,
                model=CLAUDE_MODEL,
            )
            desc_result = generate_video_description(
                transcript_chunk=chunk,
                title=title_result["title"],
                platform=primary_platform,
                anthropic_api_key=api_key,
                model=CLAUDE_MODEL,
            )

            # Upload clip + thumbnail to Drive
            clip_subfolder = _create_clip_folder(drive_folder_id, i)
            clip_drive = drive_write(
                final_clip_path,
                clip_subfolder,
                filename=f"clip_{i+1:02d}.mp4",
            )
            thumb_drive = drive_write(
                thumb_result["thumbnail_path"],
                clip_subfolder,
                filename=f"thumbnail_{i+1:02d}.jpg",
            )

            asset = {
                "clip_index": i,
                "start_s": start_s,
                "end_s": end_s,
                "virality_score": clip_window.get("score", 0.0),
                "hook": hook,
                "drive_clip_id": clip_drive["file_id"],
                "drive_thumbnail_id": thumb_drive["file_id"],
                "title": title_result["title"],
                "description": desc_result["description"],
                "platform": primary_platform,
                "caption_text": srt,
                "transcript_chunk": chunk,
            }
            clip_assets.append(asset)
            _save_clip_asset(job_id, asset)

        # ── Phase 7: Text artifacts ────────────────────────────────────────────
        _set_status(job_id, "generating_text")

        text_outputs = plan_cfg.get("text_outputs", [])
        context = {
            "show_name":     order.get("show_name", ""),
            "episode_title": order.get("episode_title", ""),
            "host_name":     order.get("host_name", ""),
            "guest_name":    order.get("guest_name", ""),
            "niche":         order.get("niche", "general"),
            "audience":      order.get("audience", "general audience"),
        }
        brand_voice = order.get("brand_voice", "") if plan_cfg.get("brand_voice_injection") else ""

        text_doc_parts = []

        if "show_notes" in text_outputs:
            sn = generate_show_notes(
                transcript=transcript,
                context=context,
                segments=segments,
                brand_voice_injection=brand_voice,
                anthropic_api_key=api_key,
                model=CLAUDE_MODEL,
            )
            text_doc_parts.append(("show_notes", sn["full_show_notes"]))

        if "captions" in text_outputs:
            caps = generate_caption_pack(
                transcript=transcript,
                context=context,
                platforms=plan_cfg["caption_platforms"],
                captions_per_platform=plan_cfg.get("captions_per_platform", 3),
                brand_voice_injection=brand_voice,
                anthropic_api_key=api_key,
                model=CLAUDE_MODEL,
            )
            cap_text = "\n\n".join(
                f"## {p.upper()} CAPTIONS\n" + "\n\n".join(f"- {c}" for c in captions)
                for p, captions in caps.get("captions", {}).items()
            )
            text_doc_parts.append(("captions", cap_text))

        if "blog_post" in text_outputs:
            blog = generate_blog_post(
                transcript=transcript,
                context=context,
                word_count_range=plan_cfg.get("blog_word_range", (800, 1200)),
                brand_voice_injection=brand_voice,
                anthropic_api_key=api_key,
                model=CLAUDE_MODEL,
            )
            text_doc_parts.append(("blog_post", blog.get("blog_post", "")))

        if "newsletter" in text_outputs:
            news = generate_newsletter_draft(
                transcript=transcript,
                context=context,
                word_count_range=plan_cfg.get("newsletter_word_range", (300, 500)),
                brand_voice_injection=brand_voice,
                anthropic_api_key=api_key,
                model=CLAUDE_MODEL,
            )
            text_doc_parts.append(("newsletter", news.get("newsletter", "")))

        if "linkedin_longform" in text_outputs:
            li = generate_blog_post(
                transcript=transcript,
                context=context,
                word_count_range=(600, 1000),
                brand_voice_injection=brand_voice,
                anthropic_api_key=api_key,
                model=CLAUDE_MODEL,
                max_tokens=3000,
            )
            text_doc_parts.append(("linkedin_longform", li.get("blog_post", "")))

        if "youtube_description" in text_outputs:
            yt_desc = generate_video_description(
                transcript_chunk=transcript[:1000],
                title=order.get("episode_title", ""),
                platform="youtube_shorts",
                brand_voice=brand_voice,
                anthropic_api_key=api_key,
                model=CLAUDE_MODEL,
            )
            yt_text = (
                yt_desc.get("description", "") + "\n\n"
                + " ".join(yt_desc.get("hashtags", []))
            )
            text_doc_parts.append(("youtube_description", yt_text))

        # ── Phase 8: Package text docs + notify ───────────────────────────────
        _set_status(job_id, "packaging")

        if "transcript" in text_outputs:
            txt_path = tmp_dir / "transcript.txt"
            txt_path.write_text(transcript, encoding="utf-8")
            drive_write(str(txt_path), drive_folder_id, filename="transcript.txt")

        if text_doc_parts:
            doc_path = tmp_dir / "text_artifacts.md"
            sections = [f"# Content Package — {order.get('episode_title', 'Episode')}\n"]
            for name, content in text_doc_parts:
                sections.append(f"\n---\n\n## {name.replace('_', ' ').title()}\n\n{content}")
            doc_path.write_text("\n".join(sections), encoding="utf-8")
            drive_write(str(doc_path), drive_folder_id, filename="text_artifacts.md")

        _set_status(job_id, "review_pending")

        if HUMAN_REVIEW_EMAIL:
            _send_review_notification(job_id, order, len(clip_assets), drive_folder_id)

        return {
            "status": "review_pending",
            "clip_count": len(clip_assets),
            "drive_folder_id": drive_folder_id,
        }

    except Exception as exc:
        _set_status(job_id, "failed", error=str(exc))
        raise

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _set_status(job_id: str, status: str, error: str | None = None) -> None:
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import CRJob
    with SessionLocal() as db:
        job = db.query(CRJob).filter(CRJob.id == job_id).first()
        if job:
            job.status = status
            if error:
                job.error_message = error
            db.commit()


def _update_transcript(job_id: str, transcript: str, segments: list, duration_s: float) -> None:
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import CRJob
    import json
    with SessionLocal() as db:
        job = db.query(CRJob).filter(CRJob.id == job_id).first()
        if job:
            job.transcript = transcript
            job.segments_json = segments
            job.video_duration_s = duration_s
            db.commit()


def _update_folder(job_id: str, folder_id: str) -> None:
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import CRJob
    with SessionLocal() as db:
        job = db.query(CRJob).filter(CRJob.id == job_id).first()
        if job:
            job.drive_folder_id = folder_id
            db.commit()


def _save_clip_asset(job_id: str, asset: dict) -> None:
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import CRClipAsset
    with SessionLocal() as db:
        row = CRClipAsset(
            cr_job_id=job_id,
            clip_index=asset["clip_index"],
            start_s=asset["start_s"],
            end_s=asset["end_s"],
            virality_score=asset["virality_score"],
            hook=asset.get("hook", ""),
            drive_clip_id=asset.get("drive_clip_id", ""),
            drive_thumbnail_id=asset.get("drive_thumbnail_id", ""),
            title=asset.get("title", ""),
            description=asset.get("description", ""),
            platform=asset.get("platform", ""),
            caption_text=asset.get("caption_text", ""),
        )
        db.add(row)
        db.commit()


def _ensure_drive_folder(job_id: str, order: dict) -> str:
    if not DRIVE_CR_ROOT_ID:
        raise RuntimeError("DRIVE_CR_ROOT_ID is not configured.")
    folder_name = f"{order.get('episode_title', 'Episode')} — {job_id[:8]}"
    result = create_folder(folder_name, parent_id=DRIVE_CR_ROOT_ID)
    return result["folder_id"]


def _create_clip_folder(parent_id: str, clip_index: int) -> str:
    result = create_folder(f"clip_{clip_index+1:02d}", parent_id=parent_id)
    return result["folder_id"]


def _send_review_notification(job_id: str, order: dict, clip_count: int, folder_id: str) -> None:
    drive_link = f"https://drive.google.com/drive/folders/{folder_id}"
    send_email(
        to=HUMAN_REVIEW_EMAIL,
        subject=f"[Review] Content Repurposing — {order.get('episode_title', job_id)}",
        body=(
            f"Job {job_id} is ready for review.\n\n"
            f"Plan: {order.get('plan', 'starter')}\n"
            f"Clips generated: {clip_count}\n"
            f"Episode: {order.get('episode_title', '')}\n\n"
            f"Drive folder: {drive_link}\n\n"
            f"Approve or reject at planBadmin.com."
        ),
    )
