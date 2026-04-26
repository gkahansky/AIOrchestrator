# Venture: Podcast Show Notes + Marketing
# CLAUDE.md — Isolation boundary active

## Context
Primary service: podcast audio → complete written content package (show notes, transcript,
social captions, newsletter, SEO metadata), delivered via Google Doc within 24 hours.

Enhanced service (v2): adds 8 podcast-specific marketing add-ons that turn each episode
into a full content marketing asset — not just documentation, but growth.

## Isolation Rule
This venture may import platform skills only. No cross-venture imports.

---

## Web UI Trigger

Orders can be submitted via the management app at planBadmin.com (Ventures → Podcast Notes → New Order).
The UI posts to `POST /api/ventures/content-studio/orders` which writes the job to DB and queues a Celery task.
CLI trigger still works: `python scripts/run_content_studio.py`.

---

## Core Service Tiers (unchanged)

| Tier | Price | Delivery | Included |
|---|---|---|---|
| Starter | $49 | 24h | Show notes + timestamps + guest bio (≤60 min) |
| Standard | $79 | 24h | + Full transcript + 5 social captions (≤60 min) |
| Premium | $119 | 48h | + Newsletter excerpt + SEO metadata (≤90 min) |

Add-ons: +$20/30 min over limit · 10% off for 4+/month · $399/month retainer

---

## Marketing Add-ons (NEW — v2)

| Add-on | Price | Delivery | Skill | Description |
|---|---|---|---|---|
| Brand Voice Guide | $79 (one-time) | 48h | `generate_brand_voice.py` | Analyses 2–3 episodes, documents tone, vocabulary, sentence structure, content principles |
| 30-Day Social Calendar | $79 | 48h | `market-social/SKILL.md` | 30 ready-to-post pieces across LinkedIn/IG/X from 4 episodes |
| Listener Email Sequence | $99 | 48h | `market-emails/SKILL.md` | 5-email nurture sequence for new subscribers; drives replay listens |
| Guest Outreach Templates | $29 | 24h | `generate_guest_outreach.py` | 3 outreach email templates (cold, warm, follow-up) for pitching guests |
| Show Landing Page Audit | $49 | 24h | `market-landing/SKILL.md` | Scored audit of podcast website/episode page — copy, CRO, SEO, trust |
| Episode Promotional Copy | $39 | 24h | `generate_promo_copy.py` | Platform description + audiogram caption + newsletter teaser + LinkedIn post |
| Competitive Show Analysis | $79 | 48h | `market-competitors/SKILL.md` | Benchmark vs 3 competing shows — positioning, content gaps, growth opportunities |
| Podcast Launch Playbook | $149 | 72h | `market-launch/SKILL.md` | Full launch plan for new or relaunching shows — channels, content, timeline, copy |

### Bundle Pricing
- **Content + Brand** ($229, saves $28): Standard package + Brand Voice Guide + 30-Day Social Calendar
- **Full Growth** ($299, saves $46): Premium package + Brand Voice Guide + 30-Day Calendar + Email Sequence
- **Launch Ready** ($249, saves $18): Starter package + Launch Playbook + Guest Outreach Templates

---

## Public Sample Endpoint

Unauthenticated endpoint for lead generation: `POST /api/sample/podcast`

- Rate-limited: 1 request per email per 24 hours (enforced via DB)
- Inputs: `email`, `show_name`, `episode_title`, `host_name` (Form); `audio` (optional file upload)
- If no audio file: sets `demo: True` on order → pipeline uses canned demo transcript (skips Whisper)
- If file provided: validates extension (.mp3, .mp4, .m4a, .wav, .webm, etc.), max 200 MB, uploads to Drive
- Runs standard pipeline → emails sample (watermarked/redacted) PDF to requester

---

## Pipeline — Core

1. Order detection — UI trigger (`POST /api/ventures/content-studio/orders`), CLI, or sample endpoint
2. Transcription — OpenAI Whisper (`openai>=1.30.0`, `$0.003/min`). Demo mode: skips Whisper, uses canned transcript.
3. Content generation — Claude API, tier-aware
4. Packaging — Google Doc creation + full PDF + sample PDF
5. Human review gate (30-min window; auto-approve after 20 validated orders)
6. Delivery — view-only Google Doc link + PDF emailed to `client_email` or `sample_email`

---

## Pipeline — Marketing Add-ons (NEW)

Add-ons run as separate pipeline jobs triggered by order line-item detection.
Each add-on creates its own output document in the client's Google Drive order folder.

### Add-on pipeline flow:
```
detect_addon_items(order)
  → for each addon:
      route_to_addon_skill(addon_type, episode_context)
        → run_addon_skill(transcript, brand_context, tier)
          → package_addon_output(drive_folder_id)
            → append_to_delivery_doc(view_link)
```

### `episode_context` object (shared across all add-ons):
```json
{
  "show_name": "...",
  "episode_title": "...",
  "host_name": "...",
  "niche": "business | tech | health | marketing | ...",
  "audience": "...",
  "transcript": "...",
  "show_notes": "...",
  "existing_brand_voice": "..."
}
```

---

## New Skills To Build

### `media/generate_brand_voice.py`
- Input: 2–3 episode transcripts + show name/niche
- Extracts: tone descriptors, vocabulary patterns, sentence length, POV, topics-to-avoid, content principles
- Output: structured Brand Voice Guide (Google Doc, 4–6 pages)
- Cached as `/PodcastNotes/{client}/brand-voice.json` for reuse on future orders

### `media/generate_guest_outreach.py`
- Input: episode_context + guest tier (cold/warm/follow-up)
- Generates 3 email templates with [PERSONALISATION] placeholders
- Output: Google Doc with 3 templates + personalisation guidance

### `media/generate_promo_copy.py`
- Input: episode transcript + show_notes + episode_context
- Generates: podcast platform description (250 chars), audiogram caption, newsletter teaser (150 words), LinkedIn post
- Output: single Google Doc with all 4 pieces labelled

### `media/generate_social_calendar.py`
- Wraps `market-social/SKILL.md` from ai-marketing-claude
- Input: 4 episode transcripts + show_notes + brand_voice
- Output: Google Doc as table (Day | Platform | Hook | Post | Type) — 30 rows

### `media/generate_email_sequence.py`
- Wraps `market-emails/SKILL.md` from ai-marketing-claude
- Input: 3–5 existing episodes + brand_voice + niche
- Generates 5-email welcome/nurture sequence:
  1. Welcome + best episode to start with
  2. What the show is really about (positioning)
  3. Most-shared episode highlight
  4. Community / social proof episode
  5. Re-engagement / what's coming next
- Output: Google Doc with subject lines + preview text + body per email

### `media/generate_launch_playbook.py`
- Wraps `market-launch/SKILL.md` from ai-marketing-claude
- Input: show concept, target audience, niche, host background
- Generates: pre-launch 8-week timeline, guest outreach framework, launch-week calendar,
  episode 1–3 promo copy, directory submission checklist, email acquisition strategy
- Output: Google Doc (15–20 pages)

---

## Reused Skills (from ai-marketing-claude via platform)

| Skill | Used for add-on |
|---|---|
| `skills/market-social/SKILL.md` | 30-Day Social Calendar |
| `skills/market-emails/SKILL.md` | Listener Email Sequence |
| `skills/market-landing/SKILL.md` | Show Landing Page Audit |
| `skills/market-competitors/SKILL.md` | Competitive Show Analysis |
| `skills/market-launch/SKILL.md` | Podcast Launch Playbook |

All ai-marketing-claude skills receive a `podcast_context_prefix` injected at invocation:
show name, niche, audience, and cached brand voice guide if available.
This ensures generic marketing frameworks output podcast-specific results.

---

## Order Status State Machine (updated)

```
pending → transcribing → transcribed → generating → generated →
packaging → packaged → review_pending → approved →
delivering → delivered
         └→ addons_pending → [addon_pipeline] → addons_complete → delivering
         └→ revision_requested → re_delivering → delivered
         └→ failed
```

---

## Environment Variables (additions for v2)

```
# Existing
OPENAI_API_KEY=
UPWORK_CONSUMER_KEY=
UPWORK_ACCESS_TOKEN=
UPWORK_CONSUMER_SECRET=
UPWORK_ACCESS_TOKEN_SECRET=
GOOGLE_CREDENTIALS_PATH=
GOOGLE_DRIVE_PODCAST_NOTES_ROOT_ID=
HUMAN_REVIEW_EMAIL=
SLACK_WEBHOOK_URL=
AUTO_APPROVE=false

# New for marketing add-ons
ADDON_AUTO_REVIEW=false
BRAND_VOICE_CACHE_ENABLED=true
ADDON_MAX_PARALLEL=3
SOCIAL_CALENDAR_PLATFORMS=linkedin,instagram,twitter
EMAIL_SEQUENCE_LENGTH=5
```

---

## Sprint Roadmap — v2 Add-ons

Run these after core pipeline Sprints 1–3 are stable.

### Sprint 3b — Brand Voice + Promo Copy ✅ DONE (2026-03-25)
- [x] `generate_brand_voice.py` — analyses 2–3 transcripts, produces structured Brand Voice Guide; cached as JSON per show (`{show-slug}-brand-voice.json`) for reuse across orders
- [x] `generate_promo_copy.py` — platform description, audiogram caption, newsletter teaser, LinkedIn post; injects brand voice when cached
- [x] Add-on runner wired into `content_studio/pipeline.py` Phase 3b; `--addons brand-voice promo-copy` CLI flags
- [x] Tested end-to-end: real 60-min episode → full premium pipeline; brand voice + promo copy outputs saved alongside order
- [x] Premium truncation fix: `CLAUDE_MAX_TOKENS_PREMIUM = 16000` in `config.py`

### Sprint 3c — Public Sample Endpoint ✅ DONE (2026-04-05)
- [x] `POST /api/sample/podcast` — optional audio upload; demo mode when no file provided
- [x] Demo transcript fallback in `_run_phase1_transcribe()` — checks `demo` flag before raising ValueError
- [x] Rate limiting (1 req/email/24h via DB), Drive upload for real files, Resend email delivery
- [x] Fixed field name mismatch in echoforge-site JS (`file` → `audio`)
- [x] `openai` added to `requirements.txt`

### Sprint 3d — Admin Order Form: File Upload + Full Fields ✅ DONE (2026-04-05)
- [x] Replaced URL text input with audio file upload picker in `ContentStudio.tsx`
- [x] `content_studio.py` router rewritten to accept `multipart/form-data` with `UploadFile`
- [x] Audio uploaded to Drive synchronously in the web router (web and worker are separate Railway containers — `/tmp` not shared)
- [x] Full form fields added: Customer Email, Show Name, Episode Title, Host Name, Guest Name, Special Instructions
- [x] Fixed delivery email showing "None" for episode title — all fields now included in order payload
- [x] Google Doc sharing changed to `share_anyone_with_link=True` so clients can open links
- [x] Drive upload errors now return HTTP 503 with detail message (CORS was stripping headers from unhandled 500s)
- [x] Unified Drive auth: `create_gdoc.py` and `drive_organise.py` now use `get_drive_service()` from `_drive_auth.py` (was hardcoded to service account, causing quota errors)

### Sprint 3e — Service B: Content Repurposing Pack ✅ DONE (2026-04-26)
- [x] `extract_audio_from_video.py` platform skill — FFmpeg audio extraction from video files (.mp4/.mov/.mkv/.avi/.webm)
- [x] `generate_blog_post.py` platform skill — 800–1,800 word SEO blog post with brand voice injection
- [x] `generate_caption_pack.py` platform skill — per-platform captions (LinkedIn/Instagram/Twitter/TikTok/YouTube), N variants per platform
- [x] `generate_newsletter_draft.py` platform skill — full newsletter draft with A/B subject lines and preview text
- [x] `ffmpeg` added to `nixpacks.toml` Railway build config
- [x] `config.py` — `REPURPOSING_TIERS` (£49 Starter / £99 Standard / £149 Pro), video config, `REPURPOSING_PACK_HUMAN_REVIEW_ALWAYS` flag
- [x] `prompts.py` — Service B prompt builder (`build_repurposing_prompt`), parser (`parse_repurposing_response`), separate system prompt
- [x] `pipeline.py` — Phase 1 detects video by extension → FFmpeg → Whisper; Phase 2 routes by `service_type`; Phase 2b runs blog/captions/newsletter skills; human review gate forced ON for all Service B orders
- [x] Content Studio router — accepts `service_type` form field, video file extensions, 500 MB limit for Service B, separate tier validation per service
- [x] Frontend `ContentStudio.tsx` — service type toggle (Show Notes / Repurposing Pack), dynamic tier cards, video file picker, "human-reviewed" badge, orders table shows Service column + audio/video icon
- [x] `types.ts` + `api.ts` — `service_type` and `"pro"` tier added to `PodcastOrderRequest`

### Sprint 4b — Social Calendar + Email Sequence
- Integrate `market-social/SKILL.md` with podcast context prefix
- Build `generate_social_calendar.py` wrapper
- Integrate `market-emails/SKILL.md` with listener-nurture framing
- Build `generate_email_sequence.py` wrapper

### Sprint 5b — Guest Outreach + Landing Page Audit
- Build `generate_guest_outreach.py`
- Wire `market-landing/SKILL.md` against show website URL (optional form field)

### Sprint 6b — Competitive Analysis + Launch Playbook + Bundles
- Wire `market-competitors/SKILL.md` with 3 competing show URLs
- Build `generate_launch_playbook.py` wrapper
- Add bundle SKU detection to order intake
- Apply bundle discount logic in revenue logging

---

## Pre-Sprint Checklist (v2 additions)

- [ ] Install ai-marketing-claude: `git clone` + `./install.sh`
- [ ] Confirm skills available at `~/.claude/skills/market-*/`
- [ ] Add podcast_context_prefix template to platform prompt library
- [ ] Update Fiverr gig with add-ons section
- [ ] Update Upwork profile + add Podcast Growth Bundle to Project Catalog
- [ ] Add new env vars to .env.example
- [ ] Update order requirements form: add optional "website URL" field

---

## Key Decisions (locked)

| Decision | Choice |
|---|---|
| Add-ons run separately | Not blocking core delivery; parallel jobs |
| Brand voice | Cached as JSON per client, reused on future orders |
| Marketing skills source | ai-marketing-claude via `~/.claude/skills/` |
| Podcast context injection | Prefix at skill invocation, not hardcoded in skill files |
| Bundle pricing | Detected by SKU in order requirements form |
| Add-on delivery | Appended as additional links in same Google Doc delivery |
| Human review — Service A | Auto-approve after 20 validated orders per tier |
| Human review — Service B | ALWAYS on — never auto-approved (human review is the product differentiator) |
| Video processing | FFmpeg on Railway (nixpacks) for audio extraction; no GPU needed |
| Blog post | New platform skill (venture-agnostic); injected into Service B Phase 2b |
| Caption packs | Per-platform prompts in `generate_caption_pack.py`; N variants per platform |
| Newsletter draft | Full draft (300–600 words) in Service B; excerpt only (150–200w) in Service A |

## Pipeline Status
<!-- managed by update_task.py -->

| Roadmap ID | Task | Status | Note | Updated |
|---|---|---|---|---|
| U-01 | Core Podcast Pipeline — Sprint 1 & 2 | ✅ done | Manual trigger pipeline live | 2026-03-25 |
| H-06 | Podcast Sample Generator | ✅ done | Demo mode + pdf-only flag | 2026-03-25 |
| M-03 | Podcast Add-on: Brand Voice Guide | ✅ done | generate_brand_voice.py, cached JSON | 2026-03-25 |
| M-04 | Podcast Add-on: Episode Promotional Copy | ✅ done | generate_promo_copy.py | 2026-03-25 |
| D-21 | Admin Order Form — File Upload + Full Fields | ✅ done | multipart/form-data, Drive upload in web router, unified Drive auth | 2026-04-05 |
| NEW | Service B — Content Repurposing Pack | ✅ done | Sprint 3e: video input, blog/captions/newsletter skills, forced review gate | 2026-04-26 |
| M-05 | Podcast Add-on: 30-Day Social Calendar | 🔲 planned | Sprint 4b | — |
| M-06 | Podcast Add-on: Listener Email Sequence | 🔲 planned | Sprint 4b | — |
| M-11 | Podcast Add-on: Guest Outreach Templates | 🔲 planned | Sprint 5b | — |
| M-12 | Podcast Add-on: Show Landing Page Audit | 🔲 planned | Sprint 5b | — |
| L-02 | Podcast Add-on: Competitive Show Analysis | 🔲 idea | Sprint 6b | — |
| L-03 | Podcast Add-on: Launch Playbook | 🔲 idea | Sprint 6b | — |
