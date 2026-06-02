# Content Engine — Multi-Channel Social Content
## Venture-level CLAUDE.md

**Read `/CLAUDE.md` at repo root first.** This file is the venture-specific layer.

---

## What this venture does

Drafts an editorial calendar per brand, generates per-channel content (blog,
post, carousel, reel, short, long video), runs an AI-tell critic + brand-voice
fidelity check, gates on human review, schedules approved items, and dispatches
them through channel publishers (native API where available, assisted-send
fallback otherwise).

EchoForge Accessibility is brand #1. The system is brand-agnostic — adding a
new brand is a row in `content_brands` plus an optional config entry.

## Pipeline (state machine)

```
strategy: draft → approved → archived
item:     brief → generating → review_pending → revising → approved →
          scheduled → publishing → published | failed | cancelled
publish:  pending → success | awaiting_manual | failed
```

Three human gates: strategy approval, item review, pre-publish unschedule
(allowed up to 15 min before `scheduled_for`).

## Channels

| Channel              | Method                         | Notes |
|----------------------|--------------------------------|-------|
| `linkedin_page`      | LinkedIn Marketing API         | Company Page OAuth (`w_organization_social`) |
| `facebook_page`      | Meta Graph API                 | Page access token |
| `instagram_business` | Meta Graph API (2-step media)  | IG Business account linked to FB Page |
| `youtube_channel`    | YouTube Data API v3 resumable  | Channel OAuth (`youtube.upload`) |

All four use the publishers/ registry (`src/aiplatform/skills/comms/publishers/`)
and fall back to assisted-send (deep link + manual confirm) when no
`SocialAccount` row exists for `(brand × channel)`.

## Skills used (all reusable / venture-agnostic)

- `aiplatform.skills.media.generate_blog_post` — blog body
- `aiplatform.skills.media.generate_caption_pack` — per-channel post text
- `aiplatform.skills.media.generate_newsletter_draft` — newsletter
- `aiplatform.skills.media.generate_social_calendar` — calendar seed
- `aiplatform.skills.media.generate_brand_voice` — voice profile build
- `aiplatform.skills.media.generate_image` — static images / carousel slides
- `aiplatform.skills.media.generate_thumbnail` — video thumbnails
- `aiplatform.skills.media.burn_captions` — word-pop captions for reels/shorts
- `aiplatform.skills.research.web_search` — topic trends (SerpAPI)

## Quality bar

Output must not read AI-generated. Enforced by:

1. **Brand-voice injection.** Every text-generation call receives the cached
   `voice_profile_json` for the brand.
2. **AI-tell critic** (`quality_gate.py`). Scores generations against a checklist
   of clichés, generic verbs, em-dash overuse, monotonous parallelism. Flagged
   spans surface in the review UI for in-place edit.
3. **Banned phrases.** Per-brand list filters out forbidden openers.
4. **Specificity grounding.** Briefs require ≥2 cited sources from
   `topic_trends`; generators must reference them.

## Theme rule (EchoForge Accessibility)

70%+ of content must be accessibility-themed. Enforced at calendar generation
via `theme_weights` in `content_brands.theme_weights` (defaults
`{"accessibility": 0.7, "adjacent": 0.3}`).

## File map

| File                | Purpose |
|---------------------|---------|
| `config.py`         | Brand registry, per-channel cadence defaults, banned-phrase seeds |
| `prompts.py`        | System prompts (strategy, brief, critic) |
| `strategy.py`       | Calendar generation logic |
| `briefs.py`         | Calendar slot → item brief |
| `quality_gate.py`   | AI-tell critic + length/banned-phrase checks |
| `pipeline.py`       | Celery task entrypoints (called from worker.py) |

## API Endpoints

Mounted at `/api/ventures/content-engine`.

| Method | Path | Purpose |
|---|---|---|
| GET/POST/PATCH/DELETE | `/brands` | Brand CRUD (and `/brands/seed-echoforge` one-shot seed helper) |
| GET/POST/PATCH | `/strategies` | Editorial-calendar CRUD; POST drafts a new calendar via `strategy.generate_calendar()` |
| POST | `/strategies/{id}/approve` | Strategy human gate (draft → approved) |
| GET/POST/PATCH/DELETE | `/items` | Item CRUD |
| POST | `/items/{id}/generate` | Kick off Celery `content.run_item_gen` |
| POST | `/items/{id}/review` | `action` ∈ {approve, revise, reject} — second human gate |
| POST | `/items/{id}/schedule` | `scheduled_for` ISO8601 — moves item to `scheduled` |
| POST | `/items/{id}/unschedule` | Third human gate — back to `approved` |
| POST | `/items/{id}/publish-now` | Force-publish (bypass scheduler beat) |
| GET | `/publish-jobs` | Per-channel publish attempt log |
| POST | `/publish-jobs/{id}/confirm-sent` | Operator confirm for assisted-send |
| GET/POST/DELETE | `/social-accounts` | OAuth-managed token rows per (brand × channel) |
| POST | `/oauth/{platform}/start` | Returns signed auth URL (`linkedin`, `meta`, `youtube`) |
| GET | `/oauth/{platform}/callback` | Public — exchanges code → token, upserts SocialAccount, redirects |
| GET | `/assets/{id}/file` | **Public, no auth** — serves a generated asset so IG / FB Graph can fetch it |
| GET | `/assets/{id}/public-url` | Authenticated helper — returns the URL above |

## Environment Variables

| Name | Used by | Notes |
|---|---|---|
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | OAuth + LinkedIn publisher | LinkedIn Developer app with Marketing Developer Platform product |
| `META_APP_ID` / `META_APP_SECRET` | OAuth + FB Page + IG publishers | One Meta app covers both channels |
| `YOUTUBE_OAUTH_CLIENT_ID` / `YOUTUBE_OAUTH_CLIENT_SECRET` | OAuth + YouTube publisher | Google Cloud OAuth Web client; enable YouTube Data API v3 |
| `OAUTH_REDIRECT_BASE_URL` | OAuth callbacks + IG public URLs | Default `https://api.planbadmin.com` |
| `FRONTEND_BASE_URL` | Post-callback redirect | Default `https://planbadmin.com` |
| `JWT_SECRET` | OAuth state signing | Already used by platform auth — reused for HS256 state |
| `LINKEDIN_ACCESS_TOKEN` / `META_PAGE_ACCESS_TOKEN` / `META_IG_ACCESS_TOKEN` / `YOUTUBE_ACCESS_TOKEN` | Publishers | Optional env fallback when no SocialAccount row exists |
| `ANTHROPIC_API_KEY` | Strategy enrichment, AI-tell critic, caption generation | Required for non-degraded operation |
| `SERPAPI_KEY` | Live source pulls in `briefs.py` | Optional — degrades to empty sources |
| `GOOGLE_AI_API_KEY` | Gemini Imagen for static images | Falls back to DALL-E 3 |
| `ELEVENLABS_API_KEY` | M3 scripted explainer (TTS narration) | Not yet wired |
| `PEXELS_API_KEY` | M3 scripted explainer (stock b-roll) | Not yet wired |

## Pipeline Status

| Roadmap ID | Feature | Status | Notes | Updated |
|---|---|---|---|---|
| CE-01 | Database schema + venture scaffold | ✅ done | 6 tables, Alembic `m8n9o0p1q2r3`, `venture_enum` extended | 2026-05-31 |
| CE-02 | Publishers registry (LI / FB / IG / YT) with assisted-send fallback | ✅ done | Mirrors `senders/` pattern | 2026-05-31 |
| CE-03 | AI-tell critic + banned-phrase + length quality gate | ✅ done | Claude Sonnet critic + deterministic checks | 2026-05-31 |
| CE-04 | Strategy generation + 30-day calendar | ✅ done | Deterministic skeleton + Claude enrichment | 2026-05-31 |
| CE-05 | FastAPI router + planBadmin Content Engine tab | ✅ done | 5 tabs: Items / Strategies / Brands / Accounts / Publishes | 2026-05-31 |
| CE-06 | Celery beat — 5-min scheduled-publish scanner | ✅ done | `content.run_scheduled_publishes` | 2026-05-31 |
| CE-07 | OAuth flows (LinkedIn / Meta / YouTube) with CSRF-signed state | ✅ done | HS256, 10-min TTL, Page+IG auto-discovery on Meta | 2026-05-31 |
| CE-08 | Native image upload (LI assets, FB multipart, IG container 2/3-step, REELS) | ✅ done | Carousel supported on LI / FB / IG | 2026-05-31 |
| CE-09 | Public asset endpoint for IG Graph fetch | ✅ done | Bigserial IDs, no listing endpoint | 2026-05-31 |
| CE-10 | EchoForge Accessibility brand seed | ✅ done | Voice profile, 13 banned phrases, 3 personas, 70/30 theme | 2026-05-31 |
| CE-11 | ElevenLabs TTS skill + tool-router slot | ✅ done | `media/tts.py` — ElevenLabs primary + OpenAI TTS fallback; degrades silently without keys | 2026-05-31 |
| CE-12 | Pexels stock-media skill | ✅ done | `research/stock_media.py` — photo + video search, attribution surfaced; ffprobe duration probe | 2026-05-31 |
| CE-13 | Scripted explainer video assembly (`generate_video_explainer`) | ✅ done | TTS narration + Imagen / Pexels visuals + FFmpeg slideshow (Ken Burns motion on stills, loop-trim on video) + word-pop captions. Wired in pipeline for reel / short / long_video formats. | 2026-05-31 |
| CE-14 | Carousel-aware image-gen prompt builder per slide | 📋 planned | M4 |  |
| CE-15 | Brand-voice regeneration from echoforge.biz copy | 📋 planned | M4 |  |
| CE-16 | Auto-approve thresholds per channel (AI-tell ≥ 90) | 📋 planned | M4 |  |
| CE-17 | Cost-per-published-post weekly digest email | 📋 planned | M4 |  |
