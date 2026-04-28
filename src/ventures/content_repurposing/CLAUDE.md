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

```
planBadmin.com → POST /api/ventures/content-repurposing/jobs
    → CRJob row created (status=pending)
    → cr.run_job Celery task dispatched
        → drive_download (source video from Drive)
        → extract_audio_from_video (FFmpeg)
        → transcribe_audio (Whisper)
        → score_clip_virality (Claude API)
        → select_clips (clip_selector.py — dedup + threshold)
        → per clip:
              extract_video_segment → transcode_video (9:16)
              → burn_captions → add_watermark (free plan)
              → extract_video_frames → score_thumbnail_frame (Claude Vision)
              → generate_thumbnail (Pillow / Creatomate)
              → generate_clip_title → generate_video_description
              → drive_write (clip + thumbnail)
              → CRClipAsset row created
        → text artifacts (gated by plan's text_outputs)
        → CRJob status = review_pending
        → Redis approval_gate:{job_id} = "pending" (planBadmin review queue)
```

### Third-party dependencies

| Service | Purpose | Plan gate |
|---|---|---|
| FFmpeg | Audio extraction, transcoding, caption burn, watermark overlay | All plans |
| OpenAI Whisper | Transcription | All plans |
| Claude API | Virality scoring, clip titles, descriptions, show notes, blog, newsletter | All plans |
| Claude Vision | Thumbnail frame selection (base64 JPEG multimodal) | All plans |
| Pillow | Thumbnail composition (gradient bar + title text) | Free / Starter / Pro |
| Creatomate API | Branded clip templates | Studio only |
| Buffer API | Social post scheduling | Pro + Studio (Sprint CR-2) |
| Google Drive | Output storage — clips, thumbnails, text docs | All plans |

---

## Directory Structure

```
src/ventures/content_repurposing/
    config.py          — PLANS dict, CLIP_MIN_S/MAX_S, VIRALITY_SCORE_THRESHOLD, env var refs
    clip_selector.py   — score threshold filter, overlap dedup, top-N selection
    pipeline.py        — run_repurposing_job() — 8-phase orchestration

src/aiplatform/skills/media/
    score_clip_virality.py      — Claude API virality window scoring
    extract_video_segments.py   — FFmpeg stream-copy segment extraction
    transcode_video.py          — FFmpeg 9:16 portrait re-encode
    burn_captions.py            — FFmpeg subtitles filter + SRT builder
    add_watermark.py            — FFmpeg drawtext overlay (free plan)
    extract_video_frames.py     — FFmpeg frame grab (n frames per clip)
    score_thumbnail_frame.py    — Claude Vision best-frame selection
    generate_thumbnail.py       — Pillow composition; Creatomate for Studio
    generate_clip_title.py      — Claude API platform-specific titles
    generate_video_description.py — Claude API platform-specific descriptions
    generate_show_notes.py      — Claude API structured show notes
    generate_blog_post.py       — Claude API blog (shared with content_studio)
    generate_newsletter_draft.py — Claude API newsletter (shared)
    generate_caption_pack.py    — Claude API multi-platform captions (shared)

src/aiplatform/webapp/routers/ventures/content_repurposing.py
src/aiplatform/worker.py  — cr.run_job Celery task
alembic/versions/a2b3c4d5e6f7_add_content_repurposing_tables.py
```

---

## Pipeline Phases

| Phase | Status field | What happens |
|---|---|---|
| 1 | downloading | drive_download → local temp video |
| 2 | transcribing | extract_audio_from_video → transcribe_audio (Whisper) |
| 3 | scoring | score_clip_virality → select_clips → create Drive job folder + Clips/ + Thumbnails/ subfolders |
| 4–6 | processing | per-clip: extract → transcode → captions → watermark → frames → thumbnail → title → description → drive_write to Clips/ or Thumbnails/ |
| 7 | generating_text | show_notes / captions / blog / newsletter gated by plan |
| 8 | packaging | write transcript.txt + text_artifacts.md to Drive job folder |
| final | review_pending | Redis approval_gate:{job_id}=pending → planBadmin review queue |

---

## Database Models

### `cr_jobs`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| status | VARCHAR(50) | pending → downloading → transcribing → scoring → processing → generating_text → packaging → review_pending → delivered / failed |
| plan | VARCHAR(50) | free / starter / pro / studio |
| show_name, episode_title, client_email | VARCHAR | denormalised from input_data |
| input_data | JSONB | full order payload |
| transcript | TEXT | Whisper output |
| segments_json | JSONB | Whisper word-level segments |
| video_duration_s | FLOAT | |
| drive_folder_id | VARCHAR(255) | output Drive folder |
| clip_count | INTEGER | filled on completion |
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
| POST | `/api/ventures/content-repurposing/jobs` | Queue a job (JSON body: plan, drive_video_id, …) |
| GET | `/api/ventures/content-repurposing/jobs` | List jobs, newest first (limit=50) |
| GET | `/api/ventures/content-repurposing/jobs/{job_id}` | Job detail + all clip assets |
| POST | `/api/ventures/content-repurposing/jobs/{job_id}/approve` | Approve review → status=delivered + client email |

---

## Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `DRIVE_CR_ROOT_ID` | — | Drive folder ID for `/ContentRepurposing/` root; falls back to `DRIVE_PODCAST_ORDERS_ID` if not set |
| `CR_TEMP_DIR` | `/tmp` | Temp dir for in-flight files; cleaned after each job |
| `CR_MAX_UPLOAD_MB` | `2000` | Max video file size in MB |
| `CR_VIRALITY_THRESHOLD` | `0.55` | Min virality score for clip selection |
| `CR_CAPTION_FONT_SIZE` | `48` | Burned-in caption font size |
| `CR_CAPTION_FONT_COLOR` | `white` | Caption font color |
| `CR_CAPTION_BORDER_COLOR` | `black` | Caption border color |
| `CR_CAPTION_BORDER_WIDTH` | `2` | Caption border width in pixels |
| `CREATOMATE_API_KEY` | — | Studio plan — branded template rendering |
| `CREATOMATE_TEMPLATE_REEL` | — | Creatomate template ID for branded clips |
| `BUFFER_ACCESS_TOKEN` | — | Pro + Studio — social scheduling (Sprint CR-2) |
| `ANTHROPIC_API_KEY` | — | Required — virality scoring, titles, descriptions, text artifacts |
| `OPENAI_API_KEY` | — | Required — Whisper transcription |

---

## Architecture Constraints

- All temp files go in `{CR_TEMP_DIR}/cr_{job_id}/` and are deleted in the `finally` block, even on failure.
- Clip output format is always portrait 9:16 (1080×1920) H.264/AAC — universal reel format.
- Clip length: 30–90 seconds (`CLIP_MIN_S` / `CLIP_MAX_S`).
- Overlap deduplication: windows with >50% overlap keep the higher-scored segment.
- Human review is mandatory — pipeline always ends at `review_pending` with a Redis approval gate; the `/approve` endpoint sets `delivered` and sends the delivery email. Never auto-approves.
- Creatomate is Studio-only and has a Pillow fallback if the API key is absent or returns an error.
- `score_thumbnail_frame` encodes up to 8 frames as base64 JPEG in a single Claude Vision call.

---

## Pipeline Status

| Feature | Status | Notes |
|---|---|---|
| score_clip_virality skill | ✅ done | Claude API window scoring |
| extract_video_segments skill | ✅ done | FFmpeg stream copy |
| transcode_video skill | ✅ done | 9:16 portrait re-encode |
| burn_captions skill | ✅ done | FFmpeg subtitles filter + SRT builder |
| add_watermark skill | ✅ done | FFmpeg drawtext (free plan) |
| extract_video_frames skill | ✅ done | FFmpeg frame grab |
| score_thumbnail_frame skill | ✅ done | Claude Vision multimodal |
| generate_thumbnail skill | ✅ done | Pillow + Creatomate fallback |
| generate_clip_title skill | ✅ done | Claude API, 3 variants per platform |
| generate_video_description skill | ✅ done | Claude API, platform caps enforced |
| generate_show_notes skill | ✅ done | Claude API, structured sections |
| clip_selector.py | ✅ done | Threshold + overlap dedup + top-N |
| config.py | ✅ done | Unified PLANS dict with text_outputs per tier |
| pipeline.py | ✅ done | 8-phase orchestration |
| DB models (CRJob, CRClipAsset) | ✅ done | Alembic migration a2b3c4d5e6f7 |
| cr.run_job Celery task | ✅ done | worker.py |
| FastAPI router | ✅ done | /api/ventures/content-repurposing/jobs |
| drive_download alias | ✅ done | drive_read.py |
| Customer-facing React app (app.echoforge.biz) | 🔲 Sprint CR-2 | Clerk + Stripe auth |
| Buffer social scheduling | 🔲 Sprint CR-2 | Pro + Studio plan gate |
| Creatomate Studio templates | 🔲 Sprint CR-3 | API key + template required |
| Admin view in planBadmin.com (list/detail UI) | 🔲 Sprint CR-2 | |
