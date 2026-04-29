"""
Content Repurposing pipeline.

Unified Service B+C: video → short clips + thumbnails + text artifacts.

Split into two phases to support the chapter-review human gate:

  Phase 1 — run_repurposing_job():
    1. Download source video from Drive
    2. Extract audio + Whisper transcription
    3. Generate episode chapters (Claude)
    4. Persist chapters → set status = chapter_review

  Phase 2 — run_repurposing_job_phase2():
    5. Re-download video + read transcript/segments from DB
    6. Virality scoring + clip selection (filtered by selected chapters)
    7. Per-clip: extract → smart crop detection → transcode → word-pop captions
       → watermark → thumbnail → title/description → Drive upload
    8. Text artifacts (show notes, blog, newsletter, captions pack)
    9. Package → review_pending
"""

import os
import shutil
import tempfile
from pathlib import Path

from ventures.content_repurposing.config import (
    ANTHROPIC_API_KEY,
    CAPTION_STYLE,
    CAPTION_STYLE_TYPE,
    CLIP_TARGET_FORMAT,
    CLAUDE_MODEL,
    CR_TEMP_DIR,
    DRIVE_CR_ROOT_ID,
    OPENAI_API_KEY,
    PLANS,
)
from ventures.content_repurposing.clip_selector import select_clips

from aiplatform.skills.media.extract_audio_from_video import extract_audio_from_video
from aiplatform.skills.media.transcribe_audio import transcribe_audio
from aiplatform.skills.media.generate_chapters import generate_chapters
from aiplatform.skills.media.score_clip_virality import score_clip_virality
from aiplatform.skills.media.extract_video_segments import extract_video_segment
from aiplatform.skills.media.transcode_video import transcode_video
from aiplatform.skills.media.detect_crop_region import detect_crop_timeline
from aiplatform.skills.media.burn_captions import burn_captions, build_srt_for_clip
from aiplatform.skills.media.add_watermark import add_watermark
from aiplatform.skills.media.extract_video_frames import extract_video_frames
from aiplatform.skills.media.score_thumbnail_frame import score_thumbnail_frame
from aiplatform.skills.media.generate_thumbnail import generate_thumbnail
from aiplatform.skills.media.generate_thumbnail_headline import generate_thumbnail_headline
from aiplatform.skills.media.generate_clip_title import generate_clip_title
from aiplatform.skills.media.generate_video_description import generate_video_description
from aiplatform.skills.media.generate_show_notes import generate_show_notes
from aiplatform.skills.media.generate_blog_post import generate_blog_post
from aiplatform.skills.media.generate_newsletter_draft import generate_newsletter_draft
from aiplatform.skills.media.generate_caption_pack import generate_caption_pack
from aiplatform.skills.storage.drive_write import drive_write
from aiplatform.skills.storage.drive_organise import create_folder
from aiplatform.skills.storage.drive_read import drive_download


# ── Phase 1 ───────────────────────────────────────────────────────────────────

def run_repurposing_job(job_id: str, order: dict) -> dict:
    """
    Phase 1: download → transcribe → generate chapters → chapter_review gate.

    Returns when the job reaches chapter_review, waiting for the admin to select
    which chapters to include before Phase 2 continues.

    Returns:
        {"status": "chapter_review", "chapter_count": int}
    """
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import CRJob

    api_key = ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    tmp_dir = Path(CR_TEMP_DIR) / f"cr_{job_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        _set_status(job_id, "downloading")

        drive_video_id = order["drive_video_id"]
        suffix = order.get("video_suffix", ".mp4")
        local_video = tmp_dir / f"source{suffix}"
        drive_download(drive_video_id, str(local_video))

        _set_status(job_id, "transcribing")

        audio_result = extract_audio_from_video(
            str(local_video),
            output_path=str(tmp_dir / "audio.mp3"),
        )
        audio_path = audio_result["audio_path"]
        duration_s = audio_result.get("duration_seconds") or 0.0

        transcript_result = transcribe_audio(audio_path)
        transcript = transcript_result["transcript"]
        segments   = transcript_result["segments"]
        duration_s = transcript_result.get("duration_seconds") or duration_s

        _update_transcript(job_id, transcript, segments, duration_s)

        # Generate episode chapters for the admin review gate
        chapter_result = generate_chapters(
            transcript=transcript,
            duration_s=duration_s,
            anthropic_api_key=api_key,
            model=CLAUDE_MODEL,
        )
        chapters = chapter_result.get("chapters", [])
        _update_chapters(job_id, chapters)

        # If the order includes clip instructions, pre-select matching chapters
        clip_instructions = order.get("clip_instructions", "")
        if clip_instructions and chapters:
            suggested_ids = _match_chapters_to_instructions(
                chapters, clip_instructions, api_key, CLAUDE_MODEL
            )
            if suggested_ids:
                _update_selected_chapters(job_id, suggested_ids)

        _set_status(job_id, "chapter_review")

        return {"status": "chapter_review", "chapter_count": len(chapters)}

    except Exception as exc:
        _set_status(job_id, "failed", error=str(exc))
        raise

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Phase 2 ───────────────────────────────────────────────────────────────────

def run_repurposing_job_phase2(
    job_id: str,
    order: dict,
    selected_chapter_ids: list[int] | None,
) -> dict:
    """
    Phase 2: score clips → process media → text artifacts → review_pending.

    Called after the admin selects chapters (or approves all) via the chapter
    review gate.  Re-downloads the source video; reads transcript + segments
    from the DB (no re-transcription cost).

    Args:
        job_id:               CRJob UUID string.
        order:                Original order dict (same as passed to Phase 1).
        selected_chapter_ids: List of chapter indexes to source clips from.
                              None or [] means use the full episode.

    Returns:
        {"status": "review_pending", "clip_count": int, "drive_folder_id": str}
    """
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import CRJob, CRClipAsset

    plan     = order.get("plan", "starter")
    plan_cfg = PLANS.get(plan, PLANS["starter"])
    api_key  = ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")

    tmp_dir = Path(CR_TEMP_DIR) / f"cr_{job_id}_p2"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Read transcript + segments + chapters from DB (saved in Phase 1)
        with SessionLocal() as db:
            job = db.query(CRJob).filter(CRJob.id == job_id).first()
            if not job:
                raise RuntimeError(f"CRJob {job_id} not found")
            transcript   = job.transcript or ""
            segments     = list(job.segments_json or [])
            duration_s   = float(job.video_duration_s or 0)
            chapters     = list(job.chapters_json or [])

        # Re-download source video
        _set_status(job_id, "downloading")
        suffix = order.get("video_suffix", ".mp4")
        local_video = tmp_dir / f"source{suffix}"
        drive_download(order["drive_video_id"], str(local_video))

        # Score virality
        _set_status(job_id, "scoring")
        max_candidates = plan_cfg["clips"] * 3
        virality_result = score_clip_virality(
            transcript=transcript,
            segments=segments,
            duration_s=duration_s,
            max_clips=max_candidates,
            anthropic_api_key=api_key,
            model=CLAUDE_MODEL,
        )
        all_clips = select_clips(virality_result["clips"], plan, PLANS)

        # Filter clips to selected chapters (if any selected)
        if selected_chapter_ids and chapters:
            selected_clips = _filter_clips_by_chapters(all_clips, chapters, selected_chapter_ids)
            if not selected_clips:
                selected_clips = all_clips   # fallback: chapter had no viral moments — use best overall
        else:
            selected_clips = all_clips

        # Create Drive output folder
        drive_folder_id = _ensure_drive_folder(job_id, order)
        _update_folder(job_id, drive_folder_id)
        clips_folder_id = _create_subfolder(drive_folder_id, "Clips")
        thumbs_folder_id = _create_subfolder(drive_folder_id, "Thumbnails")

        # Per-clip media processing
        _set_status(job_id, "processing")
        clip_assets = []
        primary_platform = (
            plan_cfg["caption_platforms"][0] if plan_cfg["caption_platforms"] else "tiktok"
        )

        for i, clip_window in enumerate(selected_clips):
            clip_dir = tmp_dir / f"clip_{i}"
            clip_dir.mkdir(exist_ok=True)

            start_s = clip_window["start_s"]
            end_s   = clip_window["end_s"]
            hook    = clip_window.get("hook", "")
            chunk   = clip_window.get("transcript_chunk", "")

            # Extract raw landscape segment
            seg_result = extract_video_segment(
                str(local_video), start_s, end_s,
                output_path=str(clip_dir / "raw.mp4"),
            )

            # Smart crop: build per-2s face timeline to track active speaker
            crop_info = detect_crop_timeline(seg_result["clip_path"])

            # Transcode to portrait with dynamic crop timeline
            tc_result = transcode_video(
                seg_result["clip_path"],
                target_format=CLIP_TARGET_FORMAT,
                output_path=str(clip_dir / "transcoded.mp4"),
                crop_timeline=crop_info["timeline"] or None,
            )

            # Burn captions (word_pop by default — configured via CR_CAPTION_STYLE)
            srt = build_srt_for_clip(segments, start_s, end_s)
            cap_result = burn_captions(
                tc_result["transcoded_path"],
                srt_content=srt,
                output_path=str(clip_dir / "captioned.mp4"),
                style=CAPTION_STYLE_TYPE,
                **CAPTION_STYLE,
            )

            wm_result = add_watermark(
                cap_result["captioned_path"],
                plan=plan,
                output_path=str(clip_dir / "final.mp4"),
            )
            final_clip_path = wm_result["final_path"]

            # Thumbnail from portrait (transcoded) frames for clean composition
            frames_result = extract_video_frames(
                tc_result["transcoded_path"],
                n=10,
                output_dir=str(clip_dir / "frames"),
            )
            frame_score = score_thumbnail_frame(
                frames_result["frame_paths"],
                transcript_chunk=chunk,
                anthropic_api_key=api_key,
            )
            headline_result = generate_thumbnail_headline(
                hook=hook or f"Clip {i+1}",
                transcript_chunk=chunk,
                show_name=order.get("show_name", ""),
                guest_name=order.get("guest_name", ""),
                host_name=order.get("host_name", ""),
                anthropic_api_key=api_key,
                model=CLAUDE_MODEL,
                platform=primary_platform,
            )
            thumb_result = generate_thumbnail(
                frame_score["best_frame"],
                title=headline_result["headline"],
                show_name=order.get("show_name", ""),
                plan=plan,
                output_path=str(clip_dir / "thumbnail.jpg"),
                highlight_word=headline_result["highlight_word"],
                platform=primary_platform,
            )

            # Title + description
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

            # Upload to Drive
            clip_drive = drive_write(
                final_clip_path, clips_folder_id, filename=f"clip_{i+1:02d}.mp4",
            )
            thumb_drive = drive_write(
                thumb_result["thumbnail_path"], thumbs_folder_id, filename=f"thumbnail_{i+1:02d}.jpg",
            )

            asset = {
                "clip_index":      i,
                "start_s":         start_s,
                "end_s":           end_s,
                "virality_score":  clip_window.get("score", 0.0),
                "hook":            hook,
                "drive_clip_id":   clip_drive["file_id"],
                "drive_thumbnail_id": thumb_drive["file_id"],
                "title":           title_result["title"],
                "description":     desc_result["description"],
                "platform":        primary_platform,
                "caption_text":    srt,
                "transcript_chunk": chunk,
            }
            clip_assets.append(asset)
            _save_clip_asset(job_id, asset)

        # Text artifacts
        _set_status(job_id, "generating_text")
        context = {
            "show_name":     order.get("show_name", ""),
            "episode_title": order.get("episode_title", ""),
            "host_name":     order.get("host_name", ""),
            "guest_name":    order.get("guest_name", ""),
            "niche":         order.get("niche", "general"),
            "audience":      order.get("audience", "general audience"),
        }
        brand_voice  = order.get("brand_voice", "") if plan_cfg.get("brand_voice_injection") else ""
        text_outputs = plan_cfg.get("text_outputs", [])
        text_doc_parts: list[tuple[str, str]] = []

        if "show_notes" in text_outputs:
            sn = generate_show_notes(
                transcript=transcript, context=context, segments=segments,
                brand_voice_injection=brand_voice, anthropic_api_key=api_key, model=CLAUDE_MODEL,
            )
            text_doc_parts.append(("show_notes", sn["full_show_notes"]))

        if "captions" in text_outputs:
            caps = generate_caption_pack(
                transcript=transcript, context=context,
                platforms=plan_cfg["caption_platforms"],
                captions_per_platform=plan_cfg.get("captions_per_platform", 3),
                brand_voice_injection=brand_voice, anthropic_api_key=api_key, model=CLAUDE_MODEL,
            )
            cap_text = "\n\n".join(
                f"## {p.upper()} CAPTIONS\n" + "\n\n".join(f"- {c}" for c in captions)
                for p, captions in caps.get("captions", {}).items()
            )
            text_doc_parts.append(("captions", cap_text))

        if "blog_post" in text_outputs:
            blog = generate_blog_post(
                transcript=transcript, context=context,
                word_count_range=plan_cfg.get("blog_word_range", (800, 1200)),
                brand_voice_injection=brand_voice, anthropic_api_key=api_key, model=CLAUDE_MODEL,
            )
            text_doc_parts.append(("blog_post", blog.get("blog_post", "")))

        if "newsletter" in text_outputs:
            news = generate_newsletter_draft(
                transcript=transcript, context=context,
                word_count_range=plan_cfg.get("newsletter_word_range", (300, 500)),
                brand_voice_injection=brand_voice, anthropic_api_key=api_key, model=CLAUDE_MODEL,
            )
            text_doc_parts.append(("newsletter", news.get("newsletter", "")))

        if "linkedin_longform" in text_outputs:
            li = generate_blog_post(
                transcript=transcript, context=context, word_count_range=(600, 1000),
                brand_voice_injection=brand_voice, anthropic_api_key=api_key, model=CLAUDE_MODEL,
                max_tokens=3000,
            )
            text_doc_parts.append(("linkedin_longform", li.get("blog_post", "")))

        if "youtube_description" in text_outputs:
            yt = generate_video_description(
                transcript_chunk=transcript[:1000],
                title=order.get("episode_title", ""),
                platform="youtube_shorts",
                brand_voice=brand_voice,
                anthropic_api_key=api_key, model=CLAUDE_MODEL,
            )
            yt_text = yt.get("description", "") + "\n\n" + " ".join(yt.get("hashtags", []))
            text_doc_parts.append(("youtube_description", yt_text))

        # Package + upload
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
        _set_approval_gate(job_id, "pending")

        return {
            "status":          "review_pending",
            "clip_count":      len(clip_assets),
            "drive_folder_id": drive_folder_id,
        }

    except Exception as exc:
        _set_status(job_id, "failed", error=str(exc))
        raise

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _filter_clips_by_chapters(
    clips: list[dict],
    chapters: list[dict],
    selected_ids: list[int],
) -> list[dict]:
    """Return clips whose window overlaps any selected chapter."""
    selected = [chapters[i] for i in selected_ids if i < len(chapters)]
    if not selected:
        return clips
    return [
        c for c in clips
        if any(
            c["start_s"] < ch["end_s"] and c["end_s"] > ch["start_s"]
            for ch in selected
        )
    ]


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
    with SessionLocal() as db:
        job = db.query(CRJob).filter(CRJob.id == job_id).first()
        if job:
            job.transcript       = transcript
            job.segments_json    = segments
            job.video_duration_s = duration_s
            db.commit()


def _match_chapters_to_instructions(
    chapters: list[dict], instructions: str, api_key: str, model: str
) -> list[int]:
    """
    Ask Claude which chapter indexes best match the user's clip_instructions.
    Returns a list of matching chapter indexes (may be empty).
    """
    import json as _json
    import re as _re
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    chapter_list = "\n".join(
        f"{ch['index']}. {ch['title']} "
        f"({int(ch['start_s'] // 60)}:{int(ch['start_s'] % 60):02d}–"
        f"{int(ch['end_s'] // 60)}:{int(ch['end_s'] % 60):02d}): {ch.get('summary', '')}"
        for ch in chapters
    )
    prompt = (
        f'The user wants clips from these parts of the episode:\n"{instructions}"\n\n'
        f"Available chapters:\n{chapter_list}\n\n"
        "Which chapter indexes best match the user's request? "
        "Respond with ONLY a JSON array of integers, e.g. [0, 2]. "
        "If nothing matches, respond with []."
    )
    try:
        response = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        m = _re.search(r"\[.*?\]", raw, _re.DOTALL)
        if m:
            return [int(x) for x in _json.loads(m.group())]
    except Exception:
        pass
    return []


def _update_selected_chapters(job_id: str, selected_ids: list[int]) -> None:
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import CRJob
    with SessionLocal() as db:
        job = db.query(CRJob).filter(CRJob.id == job_id).first()
        if job:
            job.selected_chapter_ids = selected_ids
            db.commit()


def _update_chapters(job_id: str, chapters: list) -> None:
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import CRJob
    with SessionLocal() as db:
        job = db.query(CRJob).filter(CRJob.id == job_id).first()
        if job:
            job.chapters_json = chapters
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
        raise RuntimeError(
            "Drive root folder not configured. Set DRIVE_PODCAST_ORDERS_ID (or DRIVE_CR_ROOT_ID) in env."
        )
    folder_name = f"{order.get('episode_title', 'Episode')} — {job_id[:8]}"
    result = create_folder(folder_name, parent_id=DRIVE_CR_ROOT_ID)
    return result["folder_id"]


def _create_subfolder(parent_id: str, name: str) -> str:
    result = create_folder(name, parent_id=parent_id)
    return result["folder_id"]


def _set_approval_gate(job_id: str, signal: str = "pending") -> None:
    """Write an approval signal to Redis so planBadmin can poll it."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        r.set(f"approval_gate:{job_id}", signal, ex=86400)
    except Exception:
        pass
