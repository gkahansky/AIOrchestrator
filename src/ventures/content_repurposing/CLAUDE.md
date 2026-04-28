# Venture: Content Repurposing SaaS
# CLAUDE.md — Isolation boundary active

## Context

Self-serve multi-tenant SaaS platform. Customers upload a long-form video (podcast, webinar,
talk) and receive a ready-to-publish media package: viral short clips, captioned reels,
branded thumbnails, and platform-specific titles/descriptions.

Customer-facing UI: **app.echoforge.biz**
Internal admin: **planBadmin.com → Ventures → Content Repurposing**

This is a standalone venture, not an add-on to content_studio. It has its own auth (Clerk),
billing (Stripe), DB tables, React frontend, and Celery pipeline.

## Isolation Rule

This venture may import platform skills only. No cross-venture imports.

---

## Service Plans

| Plan | Price | Monthly uploads | Max video length | Clips per video | Features |
|---|---|---|---|---|---|
| Free | $0 | 1 | 30 min | 3 | Watermarked, no social schedule |
| Starter | $29/mo | 10 | 60 min | 5 | No watermark, download only |
| Pro | $79/mo | 40 | 120 min | 10 | + Buffer social scheduling |
| Studio | $199/mo | unlimited | 240 min | 20 | + Creatomate branded templates |

---

## Architecture

```
app.echoforge.biz (React + Clerk auth)
    ↓  POST /api/cr/upload
Railway FastAPI + Celery worker
    ↓  Celery task: run_repurposing_pipeline(job_id)
PostgreSQL (4 new tables)          Redis (job state, rate limits)
Google Drive (output storage)
```

### Third-party dependencies

| Service | Purpose | Plan gate |
|---|---|---|
| Clerk | Customer auth + session management | All plans |
| Stripe | Subscription billing, usage metering | All plans |
| FFmpeg | Video transcoding, audio extraction, caption burn | All plans |
| OpenAI Whisper | Transcription for caption generation | All plans |
| Pillow | Thumbnail frame composition | All plans |
| Creatomate API | Branded clip templates | Studio only |
| Buffer API | Social post scheduling | Pro + Studio |

---

## Database Tables

### `saas_customers`
```sql
id              SERIAL PRIMARY KEY
clerk_user_id   TEXT UNIQUE NOT NULL
email           TEXT NOT NULL
stripe_customer_id  TEXT
plan            TEXT NOT NULL DEFAULT 'free'  -- free|starter|pro|studio
monthly_upload_count  INTEGER DEFAULT 0
billing_period_start  TIMESTAMP
created_at      TIMESTAMP DEFAULT NOW()
```

### `saas_upload_jobs`
```sql
id              SERIAL PRIMARY KEY
customer_id     INTEGER REFERENCES saas_customers(id)
status          TEXT NOT NULL DEFAULT 'pending'
  -- pending|uploading|transcribing|scoring|extracting|processing|packaging|done|failed
original_filename  TEXT
drive_file_id   TEXT
drive_folder_id TEXT
video_duration_s  FLOAT
clip_count      INTEGER
plan_at_submission  TEXT
error_message   TEXT
created_at      TIMESTAMP DEFAULT NOW()
completed_at    TIMESTAMP
```

### `saas_clip_assets`
```sql
id              SERIAL PRIMARY KEY
job_id          INTEGER REFERENCES saas_upload_jobs(id)
clip_index      INTEGER  -- 0-based
start_s         FLOAT
end_s           FLOAT
virality_score  FLOAT
drive_file_id   TEXT     -- transcoded clip .mp4
thumbnail_drive_id  TEXT
caption_text    TEXT
title           TEXT
description     TEXT
platform        TEXT     -- tiktok|instagram|youtube_shorts|linkedin
created_at      TIMESTAMP DEFAULT NOW()
```

### `saas_usage_events`
```sql
id              SERIAL PRIMARY KEY
customer_id     INTEGER REFERENCES saas_customers(id)
job_id          INTEGER REFERENCES saas_upload_jobs(id)
event_type      TEXT     -- upload|clip_generated|scheduled|downloaded
created_at      TIMESTAMP DEFAULT NOW()
```

---

## Pipeline — 5 Phases

### Phase 1 — Ingest & Transcribe
```
upload to Drive (temp folder)
  → validate: duration, size, extension (.mp4/.mov/.mkv/.avi/.webm)
  → extract_audio_from_video(drive_path)          # existing skill
  → transcribe_audio(audio_path)                  # existing skill (Whisper)
  → store transcript + timeline on saas_upload_jobs
```

### Phase 2 — Virality Scoring
```
score_clip_virality(transcript, timeline)          # NEW skill
  → returns: List[{start_s, end_s, score, reason}]
  → top N clips selected (N = plan clips limit)
  → scores stored on saas_clip_assets
```

### Phase 3 — Segment Extraction & Processing
```
for each scored clip:
  extract_video_segments(video_path, start_s, end_s)  # NEW skill → raw clip .mp4
    → transcode_video(clip_path, target_format)       # NEW skill → 9:16 portrait crop
      → burn_captions(clip_path, caption_srt)         # NEW skill → hardcoded subs
        → add_watermark(clip_path, plan)              # NEW skill → watermark if Free plan
```

### Phase 4 — Thumbnail Generation
```
for each clip:
  extract_video_frames(clip_path, n=10)              # NEW skill → frame list
    → score_thumbnail_frame(frames, transcript_chunk) # NEW skill → best frame
      → generate_thumbnail(frame, show_name, title)   # NEW skill (Pillow) → .jpg
        → upload thumbnail to Drive
```

### Phase 5 — Metadata Generation & Packaging
```
for each clip:
  generate_clip_title(transcript_chunk, platform)     # NEW skill
  generate_video_description(transcript_chunk, platform, brand_voice)  # NEW skill
  package_clip_output(clip_path, thumbnail, title, description, captions)
    → Drive folder: /ContentRepurposing/{customer_id}/{job_id}/clip_{n}/

final delivery:
  create_job_summary_doc(clips)  → JSON manifest on Drive
  notify customer via email + webhook
  update saas_upload_jobs.status = 'done'
```

---

## New Platform Skills To Build

All skills go in `/aiplatform/skills/` under the appropriate subdirectory.

### `media/score_clip_virality.py`
- **Input**: full transcript (with word-level timestamps), video duration
- **Logic**: Claude API — identify hook moments, emotional peaks, quotable statements,
  topic transitions; score each 30–90s window 0.0–1.0
- **Output**: `List[{"start_s": float, "end_s": float, "score": float, "hook": str, "reason": str}]`
- **Notes**: Prompt should emphasise platform-agnostic virality signals; caller filters by N

### `media/extract_video_segments.py`
- **Input**: local video path (or Drive path), start_s, end_s
- **Logic**: FFmpeg `ffmpeg -i input -ss {start} -to {end} -c copy output.mp4`
- **Output**: path to extracted segment file
- **Error handling**: validate start < end, end ≤ duration; raise ValueError on out-of-range

### `media/transcode_video.py`
- **Input**: clip path, target_format (`"portrait_9_16"` | `"landscape_16_9"` | `"square_1_1"`)
- **Logic**: FFmpeg crop + scale + re-encode to H.264/AAC; portrait = 1080×1920 with smart crop
- **Output**: path to transcoded file
- **Notes**: Use `scale=1080:1920,crop=1080:1920` with `setpts` for speed normalisation

### `media/burn_captions.py`
- **Input**: clip path, SRT string (generated from Whisper word timestamps for this clip window)
- **Logic**: FFmpeg `subtitles` filter with hardcoded styling (white text, black outline, bottom-center)
- **Output**: path to captioned clip
- **Config**: font size, position, and colour pulled from `CAPTION_STYLE` env vars (with defaults)

### `media/add_watermark.py`
- **Input**: clip path, plan (`"free"` | other)
- **Logic**: If plan == "free": FFmpeg overlay with `ECHOFORGE` text in top-right corner
- **Output**: path to watermarked clip (or original path if plan != "free")

### `media/extract_video_frames.py`
- **Input**: clip path, n (number of frames, default 10)
- **Logic**: FFmpeg `fps=1/{clip_duration/n}` extraction → list of .jpg paths
- **Output**: `List[str]` of frame file paths

### `media/score_thumbnail_frame.py`
- **Input**: frame paths, transcript_chunk (text for this clip)
- **Logic**: Claude Vision — evaluate each frame for: face visibility, emotional expression,
  scene clarity, text overlay potential; return best frame path + score
- **Output**: `{"best_frame": str, "score": float, "reason": str}`

### `media/generate_thumbnail.py`
- **Input**: frame path, title text, show_name, plan (Studio gets Creatomate template)
- **Logic**:
  - Free/Starter/Pro: Pillow — paste frame, overlay gradient bar, add title text
  - Studio: Creatomate API — `POST /renders` with branded template + frame + title
- **Output**: path to .jpg thumbnail
- **Pillow spec**: 1280×720, gradient bar at bottom 30%, Inter Bold font, 2px shadow

### `media/generate_clip_title.py`
- **Input**: transcript_chunk, platform (`tiktok`|`instagram`|`youtube_shorts`|`linkedin`)
- **Logic**: Claude API — generate 3 title variants per platform; return highest-rated
- **Output**: `{"title": str, "variants": List[str]}`
- **Platform rules**: TikTok ≤100 chars with hook word; LinkedIn ≤120 chars professional tone;
  Instagram ≤80 chars with emoji; YouTube Shorts ≤70 chars with keyword

### `media/generate_video_description.py`
- **Input**: transcript_chunk, platform, brand_voice (optional JSON from content_studio cache)
- **Logic**: Claude API — platform-appropriate description + hashtags + CTA
- **Output**: `{"description": str, "hashtags": List[str], "cta": str}`
- **Platform caps**: TikTok 2200 chars; Instagram 2200 chars; YouTube 5000 chars; LinkedIn 3000 chars

### `comms/schedule_social.py` (upgrade existing stub)
- **Current state**: stub that raises NotImplementedError
- **To implement**: Buffer API `POST /1/updates/create.json`
- **Input**: `profile_id`, `text`, `image_path` (optional), `scheduled_at` (optional ISO 8601)
- **Plan gate**: Pro and Studio only — raise `PlanError` for Free/Starter callers
- **Returns**: `{"update_id": str, "profile_id": str, "scheduled_at": str}`
- **Error handling**: Buffer rate limit (10 req/min), retry with exponential backoff

---

## Venture Files

### `ventures/content_repurposing/config.py`
```python
PLANS = {
    "free":    {"uploads": 1,         "max_min": 30,  "clips": 3,  "watermark": True,  "social": False, "templates": False},
    "starter": {"uploads": 10,        "max_min": 60,  "clips": 5,  "watermark": False, "social": False, "templates": False},
    "pro":     {"uploads": 40,        "max_min": 120, "clips": 10, "watermark": False, "social": True,  "templates": False},
    "studio":  {"uploads": 99999,     "max_min": 240, "clips": 20, "watermark": False, "social": True,  "templates": True},
}

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
MAX_UPLOAD_SIZE_GB = 5

CLIP_MIN_S = 30
CLIP_MAX_S = 90
VIRALITY_SCORE_THRESHOLD = 0.55  # clips below this score are dropped before N-clip limit

CAPTION_STYLE = {
    "fontsize": 48,
    "fontcolor": "white",
    "bordercolor": "black",
    "borderwidth": 2,
    "position": "bottom_center",
}

CREATOMATE_TEMPLATE_ID = ""  # set in env
BUFFER_RATE_LIMIT_PER_MIN = 10
```

### `ventures/content_repurposing/clip_selector.py`
- Receives raw virality scores from `score_clip_virality`
- Applies `VIRALITY_SCORE_THRESHOLD` filter
- Deduplicates overlapping windows (>50% overlap → keep higher score)
- Sorts by score descending, returns top N per plan
- Exported function: `select_clips(scored_windows, plan) -> List[ClipWindow]`

### `ventures/content_repurposing/pipeline.py`
- Entry point: `run_repurposing_pipeline(job_id: int)`
- Loads `saas_upload_jobs` record + `saas_customers` record for plan
- Runs Phases 1–5 in sequence, updating job status at each phase boundary
- On any phase failure: sets `status = "failed"`, writes `error_message`, sends alert email
- All temp files written to `/tmp/cr_{job_id}/`, cleaned up on pipeline exit

---

## API Endpoints

All endpoints require Clerk JWT in `Authorization: Bearer <token>` header.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/cr/upload` | Multipart upload; validates plan limits; queues Celery task |
| `GET` | `/api/cr/jobs` | List customer's upload jobs (paginated) |
| `GET` | `/api/cr/jobs/{job_id}` | Job status + clip assets (polling endpoint) |
| `GET` | `/api/cr/jobs/{job_id}/clips` | Clip assets with download URLs |
| `POST` | `/api/cr/jobs/{job_id}/clips/{clip_id}/schedule` | Schedule clip via Buffer (Pro+) |
| `GET` | `/api/cr/billing/portal` | Stripe customer portal redirect |
| `POST` | `/api/cr/webhooks/stripe` | Stripe webhook — updates plan on subscription events |
| `POST` | `/api/cr/webhooks/clerk` | Clerk webhook — creates `saas_customers` row on signup |

---

## Environment Variables

```bash
# Clerk
CLERK_SECRET_KEY=
CLERK_PUBLISHABLE_KEY=
CLERK_WEBHOOK_SECRET=

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_STARTER=price_xxx
STRIPE_PRICE_PRO=price_xxx
STRIPE_PRICE_STUDIO=price_xxx

# Creatomate (Studio plan)
CREATOMATE_API_KEY=
CREATOMATE_TEMPLATE_REEL=  # Creatomate template ID for branded reels

# Buffer (Pro + Studio)
BUFFER_ACCESS_TOKEN=
BUFFER_PROFILE_TIKTOK=
BUFFER_PROFILE_INSTAGRAM=
BUFFER_PROFILE_LINKEDIN=

# Processing
CR_TEMP_DIR=/tmp
CR_MAX_PARALLEL_CLIPS=3       # Celery concurrency for clip processing
CR_VIRALITY_THRESHOLD=0.55
CR_CAPTION_FONT_SIZE=48
```

---

## Frontend — app.echoforge.biz

Customer-facing React app (separate from planBadmin.com).

### Pages
| Route | Description |
|---|---|
| `/` | Marketing landing page |
| `/login` | Clerk `<SignIn />` component |
| `/signup` | Clerk `<SignUp />` component |
| `/dashboard` | Upload history, job status, plan info |
| `/upload` | Drag-and-drop uploader, platform selector, submit |
| `/jobs/:id` | Job detail — clip previews, download buttons, schedule buttons |
| `/billing` | Stripe portal link + plan comparison card |

### Key components
- `UploadZone.tsx` — drag-and-drop with progress bar; polls `/api/cr/jobs/{id}` every 5s
- `ClipCard.tsx` — preview player, thumbnail, title/description, schedule button (Pro+)
- `PlanBadge.tsx` — shows current plan + upgrade CTA
- `JobStatusBadge.tsx` — status pill with colour coding

---

## Sprint Roadmap

### Pre-Sprint Checklist
- [ ] Provision Clerk app for echoforge.biz, set redirect URLs
- [ ] Create Stripe products + prices for all 3 paid plans; note price IDs in `.env`
- [ ] Provision Creatomate account; create branded reel template; note template ID
- [ ] Create Buffer app; generate access token; note profile IDs per platform
- [ ] Add 4 DB migration files for new tables (use Alembic)
- [ ] Register `app.echoforge.biz` domain / configure Railway custom domain
- [ ] Add all new env vars to Railway + `.env.example`
- [ ] Add `ffmpeg` to `nixpacks.toml` if not already present (done in Sprint 3e)
- [ ] Install Python deps: `pillow`, `creatomate`, `stripe`, `clerk-sdk-python`

### Sprint CR-1 — Backend Foundation (2 weeks)

#### Week 1 — DB, Auth, Upload
- [ ] Alembic migrations for `saas_customers`, `saas_upload_jobs`, `saas_clip_assets`, `saas_usage_events`
- [ ] Clerk webhook handler → `saas_customers` row creation
- [ ] Stripe webhook handler → plan updates on `subscription.created/updated/deleted`
- [ ] `POST /api/cr/upload` — Clerk JWT validation, plan limit checks, Drive upload, Celery dispatch
- [ ] `GET /api/cr/jobs`, `GET /api/cr/jobs/{id}` — status polling endpoints
- [ ] Stripe billing portal redirect endpoint

#### Week 2 — Pipeline
- [ ] `media/score_clip_virality.py` — Claude API virality scoring
- [ ] `media/extract_video_segments.py` — FFmpeg segment extraction
- [ ] `media/transcode_video.py` — portrait 9:16 re-encode
- [ ] `media/burn_captions.py` — FFmpeg subtitle filter
- [ ] `media/add_watermark.py` — Free plan overlay
- [ ] `media/extract_video_frames.py` — thumbnail frame candidates
- [ ] `media/score_thumbnail_frame.py` — Claude Vision best frame selection
- [ ] `media/generate_thumbnail.py` — Pillow composition (Studio: Creatomate)
- [ ] `media/generate_clip_title.py` — platform-specific titles
- [ ] `media/generate_video_description.py` — platform-specific descriptions
- [ ] `ventures/content_repurposing/clip_selector.py` — dedup + threshold filtering
- [ ] `ventures/content_repurposing/pipeline.py` — full 5-phase orchestration
- [ ] `ventures/content_repurposing/config.py` — plan constants, FFmpeg config

### Sprint CR-2 — Operator Dashboard (1 week)

- [ ] Customer-facing React app scaffold at `app.echoforge.biz`
- [ ] Clerk `<SignIn>` / `<SignUp>` integration
- [ ] `UploadZone.tsx` — drag-and-drop, platform selector, job submit
- [ ] `Dashboard.tsx` — job history table with status badges
- [ ] `JobDetail.tsx` — clip grid with `ClipCard.tsx` (preview, download, schedule)
- [ ] `PlanBadge.tsx` + Stripe portal link
- [ ] `comms/schedule_social.py` — implement Buffer API stub
- [ ] `POST /api/cr/jobs/{job_id}/clips/{clip_id}/schedule` endpoint (Pro+ gate)
- [ ] Free plan watermark visible in `ClipCard.tsx` with upgrade nudge
- [ ] End-to-end test: upload → polling → clip download

### Sprint CR-3 — Polish & Growth (planned)

- [ ] Creatomate branded template rendering (Studio plan)
- [ ] Bulk schedule modal — schedule all clips in one action
- [ ] Usage dashboard — monthly upload count vs plan limit, clips generated
- [ ] Referral / invite flow
- [ ] Admin view in planBadmin.com: all customers, job queue, revenue metrics
- [ ] Stripe metered billing for overage (uploads beyond plan limit)

---

## Key Decisions (locked)

| Decision | Choice |
|---|---|
| Auth | Clerk — handles OAuth, magic links, JWT; no custom auth code |
| Billing | Stripe subscriptions; plan stored on `saas_customers.plan` updated via webhook |
| Video storage | Google Drive — same infra as other ventures; no S3 required |
| Clip format | H.264/AAC, portrait 9:16 (1080×1920) — universal reel format |
| Caption style | Hardcoded FFmpeg subtitles filter; style configurable via env, not per-customer |
| Virality scoring | Claude API (not heuristics) — qualitative hook + emotional signal detection |
| Thumbnail | Pillow for Free/Starter/Pro; Creatomate for Studio (brand templates) |
| Free plan | Watermarked output only — conversion lever to paid plans |
| Social scheduling | Buffer API — Pro + Studio only; schedule_social.py stub → implement in CR-2 |
| Temp files | `/tmp/cr_{job_id}/` — cleaned on pipeline exit; never stored permanently |
| Clip length | 30–90 seconds — platform-optimised short-form range |
| Deduplication | Overlapping windows >50% → keep higher-scored segment |

---

## Pipeline Status

| Roadmap ID | Task | Status | Sprint |
|---|---|---|---|
| CR-01 | DB migrations (4 tables) | 🔲 planned | CR-1 Week 1 |
| CR-02 | Clerk + Stripe webhook handlers | 🔲 planned | CR-1 Week 1 |
| CR-03 | Upload + polling API endpoints | 🔲 planned | CR-1 Week 1 |
| CR-04 | score_clip_virality.py | 🔲 planned | CR-1 Week 2 |
| CR-05 | extract_video_segments.py | 🔲 planned | CR-1 Week 2 |
| CR-06 | transcode_video.py | 🔲 planned | CR-1 Week 2 |
| CR-07 | burn_captions.py | 🔲 planned | CR-1 Week 2 |
| CR-08 | add_watermark.py | 🔲 planned | CR-1 Week 2 |
| CR-09 | extract_video_frames.py | 🔲 planned | CR-1 Week 2 |
| CR-10 | score_thumbnail_frame.py (Claude Vision) | 🔲 planned | CR-1 Week 2 |
| CR-11 | generate_thumbnail.py (Pillow + Creatomate) | 🔲 planned | CR-1 Week 2 |
| CR-12 | generate_clip_title.py | 🔲 planned | CR-1 Week 2 |
| CR-13 | generate_video_description.py | 🔲 planned | CR-1 Week 2 |
| CR-14 | clip_selector.py | 🔲 planned | CR-1 Week 2 |
| CR-15 | ventures/content_repurposing/pipeline.py | 🔲 planned | CR-1 Week 2 |
| CR-16 | app.echoforge.biz React app | 🔲 planned | CR-2 |
| CR-17 | schedule_social.py Buffer implementation | 🔲 planned | CR-2 |
| CR-18 | Clip scheduling endpoint + UI | 🔲 planned | CR-2 |
| CR-19 | Creatomate Studio templates | 🔲 planned | CR-3 |
| CR-20 | Admin view in planBadmin.com | 🔲 planned | CR-3 |
