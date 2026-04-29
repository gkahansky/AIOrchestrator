# Content Repurposing Venture — CLAUDE.md

## What This Venture Is

Unified media + text repurposing service. Operator submits a long-form video (podcast, webinar, talk) via planBadmin.com; the pipeline produces viral short clips, captioned reels, branded thumbnails, and platform-specific titles/descriptions, plus text artifacts (show notes, captions, blog post, newsletter) gated by tier.

This is a merged replacement for the original Service B (text-only) and the planned Service C (clips/thumbnails). The tier names and clip limits come from the Service C spec; text artifacts are distributed across matching tiers.

Admin: **planBadmin.com → Ventures → Content Repurposing**

## Isolation Rule

This venture may import platform skills only. No cross-venture imports.

---

## Service Plans

| Plan | Price | Monthly uploads | Max video | Clips | Text artifacts |
|---|---|---|---|---|---|
| Free | $0 | 1 | 30 min | 3 watermarked | Captions only |
| Starter | $29/mo | 10 | 60 min | 5 | + Show notes + transcript |
| Pro | $79/mo | 40 | 120 min | 10 | + Blog post + newsletter + 5 platforms |
| Studio | $199/mo | unlimited | 240 min | 20 | + LinkedIn longform + YouTube desc + brand voice + Creatomate |

---

## Architecture

The pipeline is split into two phases separated by a human chapter-review gate.

```
planBadmin.com → POST /api/ventures/content-repurposing/jobs
    → CRJob row created (status=pending)
    → cr.run_job Celery task (Phase 1):
        → drive_download (source video from Drive)
        → extract_audio_from_video (FFmpeg)
        → transcribe_audio (Whisper)
        → generate_chapters (Claude — 5-10 topical chapters with timestamps)
        → if clip_instructions set: Claude matches instructions → suggested_chapter_ids
        → CRJob status = chapter_review
        ↓ (admin selects chapters or proceeds with all — planBadmin chapter review UI)
    → cr.resume_job Celery task (Phase 2):
        → re-download video from Drive
        → score_clip_virality (Claude) → select_clips (filtered to selected chapters)
        → per clip:
              extract_video_segment (landscape raw)
              → extract_video_frames (landscape) → detect_crop_region (OpenCV faces)
              → transcode_video (9:16 portrait, crop_x from face detection)
              → burn_captions (word_pop style — 2-word TikTok chunks, yellow 90px)
              → add_watermark (free plan)
              → extract_video_frames (portrait) → score_thumbnail_frame (Claude Vision)
              → generate_thumbnail (Pillow / Creatomate)
              → generate_clip_title → generate_video_description
              → drive_write (clip + thumbnail)
              → CRClipAsset row created
        → text artifacts (gated by plan's text_outputs)
        → CRJob status = review_pending
        → Redis approval_gate:{job_id} = "pending" (planBadmin review queue)
        ↓ (admin approves)
    → status = delivered + delivery email to client
```

### Third-party dependencies

| Service | Purpose | Plan gate |
|---|---|---|
| FFmpeg | Audio extraction, transcoding, caption burn, watermark overlay | All plans |
| OpenAI Whisper | Transcription | All plans |
| Claude API | Chapter generation, virality scoring, chapter-instruction matching, clip titles, descriptions, show notes, blog, newsletter | All plans |
| Claude Vision | Thumbnail frame selection (base64 JPEG multimodal) | All plans |
| OpenCV (`opencv-python-headless`) | Face detection in landscape frames for smart portrait crop | All plans |
| Pillow | Thumbnail composition (gradient bar + title text) | Free / Starter / Pro |
| Creatomate API | Branded clip templates | Studio only |
| Buffer API | Social post scheduling | Pro + Studio (planned) |
| Google Drive | Output storage — clips, thumbnails, text docs | All plans |

---

## Directory Structure

```
src/ventures/content_repurposing/
    config.py          — PLANS dict, CLIP_MIN_S/MAX_S, VIRALITY_SCORE_THRESHOLD, CAPTION_STYLE, CAPTION_STYLE_TYPE, env var refs
    clip_selector.py   — score threshold filter, overlap dedup, top-N selection
    pipeline.py        — run_repurposing_job() Phase 1 + run_repurposing_job_phase2() Phase 2

src/aiplatform/skills/media/
    score_clip_virality.py      — Claude API virality window scoring
    generate_chapters.py        — Claude API chapter segmentation (5-10 chapters with timestamps)
    extract_video_segments.py   — FFmpeg stream-copy segment extraction
    transcode_video.py          — FFmpeg 9:16 portrait re-encode; accepts crop_x for face-aware cropping
    detect_crop_region.py       — OpenCV Haar cascade face detection → optimal portrait crop_x
    burn_captions.py            — FFmpeg ASS captions; style="word_pop" splits to 2-word TikTok chunks
    add_watermark.py            — FFmpeg drawtext overlay (free plan)
    extract_video_frames.py     — FFmpeg frame grab (n frames per clip)
    score_thumbnail_frame.py    — Claude Vision best-frame selection
    generate_thumbnail.py       — Pillow composition (portrait 1080×1920); Creatomate for Studio
    generate_clip_title.py      — Claude API platform-specific titles
    generate_video_description.py — Claude API platform-specific descriptions
    generate_show_notes.py      — Claude API structured show notes
    generate_blog_post.py       — Claude API blog (shared with content_studio)
    generate_newsletter_draft.py — Claude API newsletter (shared)
    generate_caption_pack.py    — Claude API multi-platform captions (shared)

src/aiplatform/webapp/routers/ventures/content_repurposing.py
src/aiplatform/worker.py  — cr.run_job (Phase 1) + cr.resume_job (Phase 2) Celery tasks
alembic/versions/a2b3c4d5e6f7_add_content_repurposing_tables.py
alembic/versions/b3c4d5e6f7a8_cr_jobs_add_chapters.py
```

---

## Pipeline Phases

| Phase | Status field | What happens |
|---|---|---|
| 1 | downloading | drive_download → local temp video |
| 2 | transcribing | extract_audio_from_video → transcribe_audio (Whisper) |
| 3 | chapter_review | generate_chapters (Claude) → optional chapter matching from clip_instructions → human gate (admin selects chapters) |
| — | pending | Phase 2 dispatched after chapter approval |
| 4 | downloading | re-download source video |
| 5 | scoring | score_clip_virality → select_clips (filtered to selected chapters if set) |
| 6 | processing | per-clip: landscape frames → detect_crop_region (OpenCV) → transcode (portrait, smart crop) → word-pop captions → watermark → portrait frames → thumbnail → title → description → drive_write |
| 7 | generating_text | show_notes / captions / blog / newsletter gated by plan |
| 8 | packaging | write transcript.txt + text_artifacts.md to Drive job folder |
| final | review_pending | Redis approval_gate:{job_id}=pending → planBadmin review queue |

**Chapter review gate:** after Phase 2 (transcription), the admin sees a list of AI-generated chapters with titles, timestamps, and summaries. They can check specific chapters to source clips from, or proceed with the full episode. If `clip_instructions` were set on the order form, matching chapters are pre-checked automatically.

---

## Database Models

### `cr_jobs`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| status | VARCHAR(50) | pending → downloading → transcribing → chapter_review → pending → downloading → scoring → processing → generating_text → packaging → review_pending → delivered / failed |
| plan | VARCHAR(50) | free / starter / pro / studio |
| show_name, episode_title, client_email | VARCHAR | denormalised from input_data |
| input_data | JSONB | full order payload (includes clip_instructions) |
| transcript | TEXT | Whisper output |
| segments_json | JSONB | Whisper segment list [{start, end, text}] |
| video_duration_s | FLOAT | |
| chapters_json | JSONB | [{index, title, start_s, end_s, summary}] — populated in Phase 1 |
| selected_chapter_ids | JSONB | [0, 2, 4] — null means all chapters; set from clip_instructions matching or admin selection |
| drive_folder_id | VARCHAR(255) | output Drive folder |
| clip_count | INTEGER | filled on Phase 2 completion |
| error_message | TEXT | |
| celery_task_id | VARCHAR(100) | |
| created_at, updated_at, completed_at | TIMESTAMPTZ | |

### `cr_clip_assets`

| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK autoincrement | |
| cr_job_id | UUID FK → cr_jobs | CASCADE delete |
| clip_index | INTEGER | 0-based |
| start_s, end_s | FLOAT | clip window in source video |
| virality_score | FLOAT | 0.0–1.0 |
| hook | TEXT | one-line hook from virality scorer |
| drive_clip_id | VARCHAR(255) | Drive file ID of transcoded .mp4 |
| drive_thumbnail_id | VARCHAR(255) | Drive file ID of .jpg thumbnail |
| title | VARCHAR(500) | primary platform title |
| description | TEXT | primary platform description |
| platform | VARCHAR(50) | primary platform for this clip |
| caption_text | TEXT | SRT content |
| created_at | TIMESTAMPTZ | |

---

## API Endpoints

All endpoints require planBadmin JWT (`Authorization: Bearer <token>`).

| Method | Path | Description |
|---|---|---|
| POST | `/api/ventures/content-repurposing/jobs` | Queue a job (multipart: plan, video file, show_name, episode_title, host_name, guest_name, client_email, niche, audience, brand_voice, clip_instructions) |
| GET | `/api/ventures/content-repurposing/jobs` | List jobs, newest first (limit=50) |
| GET | `/api/ventures/content-repurposing/jobs/{job_id}` | Job detail + all clip assets + chapters + suggested_chapter_ids |
| GET | `/api/ventures/content-repurposing/jobs/{job_id}/chapters` | Chapters list for the chapter review gate |
| POST | `/api/ventures/content-repurposing/jobs/{job_id}/chapters/approve` | Submit chapter selection → dispatch Phase 2. Body: `{"selected_ids": [0, 2]}` or `{}` for all |
| POST | `/api/ventures/content-repurposing/jobs/{job_id}/approve` | Approve final review → status=delivered + client email |
| POST | `/api/ventures/content-repurposing/jobs/{job_id}/retry` | Re-queue a failed job (restarts from Phase 1) |

---

## Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `DRIVE_CR_ROOT_ID` | — | Drive folder ID for `/ContentRepurposing/` root; falls back to `DRIVE_PODCAST_ORDERS_ID` if not set |
| `CR_TEMP_DIR` | `/tmp` | Temp dir for in-flight files; cleaned after each phase |
| `CR_MAX_UPLOAD_MB` | `2000` | Max video file size in MB |
| `CR_VIRALITY_THRESHOLD` | `0.55` | Min virality score for clip selection |
| `CR_CAPTION_FONT_SIZE` | `64` | Caption font size in pixels (overridden by word_pop style to 90) |
| `CR_CAPTION_FONT_COLOR` | `white` | Caption font color (overridden by word_pop to yellow) |
| `CR_CAPTION_BORDER_COLOR` | `black` | Caption border color |
| `CR_CAPTION_BORDER_WIDTH` | `3` | Caption border width in pixels |
| `CR_CAPTION_STYLE` | `word_pop` | Caption style — `word_pop` (TikTok 2-word chunks) or `standard` (phrase-level) |
| `CREATOMATE_API_KEY` | — | Studio plan — branded template rendering |
| `CREATOMATE_TEMPLATE_REEL` | — | Creatomate template ID for branded clips |
| `BUFFER_ACCESS_TOKEN` | — | Pro + Studio — social scheduling (planned) |
| `ANTHROPIC_API_KEY` | — | Required — chapter gen, virality scoring, titles, descriptions, text artifacts |
| `OPENAI_API_KEY` | — | Required — Whisper transcription |

---

## Architecture Constraints

- Pipeline is two-phase with a human chapter-review gate between transcription and processing. Phase 1 ends at `chapter_review`; Phase 2 is dispatched by the `/chapters/approve` endpoint.
- All temp files go in `{CR_TEMP_DIR}/cr_{job_id}/` (Phase 1) and `cr_{job_id}_p2/` (Phase 2); both cleaned in `finally` blocks.
- Clip output is always portrait 9:16 (1080×1920) H.264/AAC.
- Smart crop: OpenCV Haar cascade detects faces in landscape frames before transcoding. If no faces found (or OpenCV not installed), falls back to center crop silently.
- Word-pop captions: each Whisper segment is split into 2-word chunks with evenly divided timing; 90px yellow text. Revert to `CR_CAPTION_STYLE=standard` for phrase-level captions.
- Clip length: 30–90 seconds (`CLIP_MIN_S` / `CLIP_MAX_S`).
- Chapter filtering: if admin selects chapters, only virality windows overlapping selected chapter time ranges are included. If filtering yields zero clips, falls back to top overall clips.
- If `clip_instructions` is set on order, Claude runs a lightweight matching call to pre-select relevant chapters — the admin can still override before proceeding.
- Human review is mandatory — pipeline always ends at `review_pending`; the `/approve` endpoint sets `delivered` and sends the delivery email. Never auto-approves.
- Thumbnails are portrait 1080×1920, composed with Pillow `ImageOps.fit` (no distortion).
- Creatomate is Studio-only; falls back to Pillow if key absent.

---

## Pipeline Status

| Feature | Status | Notes |
|---|---|---|
| score_clip_virality skill | ✅ done | Claude API window scoring |
| extract_video_segments skill | ✅ done | FFmpeg stream copy |
| transcode_video skill | ✅ done | 9:16 portrait re-encode; crop_x param for smart crop |
| detect_crop_region skill | ✅ done | OpenCV Haar cascade face detection → portrait crop offset |
| burn_captions skill | ✅ done | FFmpeg ASS captions; word_pop style (2-word TikTok chunks) |
| add_watermark skill | ✅ done | FFmpeg drawtext (free plan) |
| extract_video_frames skill | ✅ done | FFmpeg frame grab |
| score_thumbnail_frame skill | ✅ done | Claude Vision multimodal |
| generate_thumbnail skill | ✅ done | Pillow portrait 1080×1920 + Creatomate fallback |
| generate_chapters skill | ✅ done | Claude API chapter segmentation with timestamps |
| generate_clip_title skill | ✅ done | Claude API, 3 variants per platform |
| generate_video_description skill | ✅ done | Claude API, platform caps enforced |
| generate_show_notes skill | ✅ done | Claude API, structured sections |
| clip_selector.py | ✅ done | Threshold + overlap dedup + top-N + chapter filtering |
| config.py | ✅ done | Unified PLANS dict; CAPTION_STYLE_TYPE env var |
| pipeline.py (Phase 1) | ✅ done | download → transcribe → chapters → chapter_review gate |
| pipeline.py (Phase 2) | ✅ done | score → smart crop → process → text → review_pending |
| Chapter review gate UI | ✅ done | CRJobDetail.tsx — chapter checklist, pre-selection from clip_instructions |
| clip_instructions order field | ✅ done | ContentStudio.tsx form + API + pipeline chapter pre-matching |
| DB models (CRJob, CRClipAsset) | ✅ done | Migrations a2b3c4d5e6f7 + b3c4d5e6f7a8 |
| cr.run_job Celery task (Phase 1) | ✅ done | worker.py |
| cr.resume_job Celery task (Phase 2) | ✅ done | worker.py |
| FastAPI router | ✅ done | /api/ventures/content-repurposing/jobs + /chapters/approve |
| Admin detail page (planBadmin.com) | ✅ done | CRJobDetail.tsx — phases, clips table, chapter review, approve/retry |
| Customer-facing React app (app.echoforge.biz) | 🔲 planned | Clerk + Stripe auth |
| Buffer social scheduling | 🔲 planned | Pro + Studio plan gate |
| Creatomate Studio templates | 🔲 planned | API key + template required |
