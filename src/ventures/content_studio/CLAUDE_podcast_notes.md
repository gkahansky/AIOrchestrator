# Venture: Podcast Show Notes + Content Repurposing Pack
# CLAUDE.md — Isolation boundary active

## Context

Two services share this venture pipeline:

**Service A — Podcast Show Notes:** podcast audio → written content package (show notes,
transcript, social captions, newsletter, SEO metadata), delivered via Google Doc in 24–48h.
Enhanced with 8 marketing add-ons (v2).

**Service B — Done-for-You Content Repurposing Pack:** audio OR video file →
full repurposing bundle (transcript, blog post, multi-platform captions, newsletter draft,
show notes), human-reviewed and delivered in 24–48h. Targets both podcasters and video
creators. Human review is the explicit differentiator over self-serve AI tools.

Both services share the same pipeline, skills, and delivery infrastructure. Service B adds
video input support and three new output types (blog post, per-platform caption packs,
full newsletter draft).

## Isolation Rule
This venture may import platform skills only. No cross-venture imports.

---

## Web UI Trigger

Orders for both services are submitted via planBadmin.com
(Ventures → Podcast Notes → New Order).
The UI posts to `POST /api/ventures/content-studio/orders` with a `service_type` field:
`show_notes` (Service A) or `repurposing_pack` (Service B).
CLI trigger: `python scripts/run_content_studio.py --service show_notes|repurposing_pack`

---

## Service A — Podcast Show Notes Tiers (unchanged)

| Tier | Price | Delivery | Included |
|---|---|---|---|
| Starter | $49 | 24h | Show notes + timestamps + guest bio (≤60 min) |
| Standard | $79 | 24h | + Full transcript + 5 social captions (≤60 min) |
| Premium | $119 | 48h | + Newsletter excerpt + SEO metadata (≤90 min) |

Add-ons: +$20/30 min over limit · 10% off for 4+/month · $399/month retainer

---

## Service B — Content Repurposing Pack Tiers (NEW)

Accepts: audio (.mp3, .mp4, .m4a, .wav, .webm) OR video (.mp4, .mov, .mkv, .avi, .webm)
Max file size: 500 MB · Max duration: 120 min

| Tier | Price | Delivery | Included |
|---|---|---|---|
| Starter | £49 | 24h | Transcript + show notes + 3 captions per platform (LinkedIn, Instagram, Twitter/X) |
| Standard | £99 | 24h | + Blog post (800–1,200 words) + full newsletter draft (300–500 words) + 5 captions per platform |
| Pro | £149 | 24h | + Brand voice injection + audiogram caption + LinkedIn long-form post + YouTube description + rush handling |

Add-ons: +£15/30 min over 90 min limit · 10% off for 4+/month · £349/month retainer (4 episodes)

### Positioning Note
Service B is explicitly marketed as "human-checked AI" — every order goes through the
human review gate before delivery. This is the differentiator over Castmagic, Podsqueeze,
and other self-serve tools. The review step is never removed for Service B.

---

## Marketing Add-ons (applies to Service A — v2)

| Add-on | Price | Delivery | Skill | Description |
|---|---|---|---|---|
| Brand Voice Guide | $79 (one-time) | 48h | `generate_brand_voice.py` | Analyses 2–3 episodes, documents tone, vocabulary, sentence structure, content principles |
| 30-Day Social Calendar | $79 | 48h | `market-social/SKILL.md` | 30 ready-to-post pieces across LinkedIn/IG/X from 4 episodes |
| Listener Email Sequence | $99 | 48h | `market-emails/SKILL.md` | 5-email nurture sequence for new subscribers |
| Guest Outreach Templates | $29 | 24h | `generate_guest_outreach.py` | 3 outreach templates (cold, warm, follow-up) |
| Show Landing Page Audit | $49 | 24h | `market-landing/SKILL.md` | Scored audit — copy, CRO, SEO, trust |
| Episode Promotional Copy | $39 | 24h | `generate_promo_copy.py` | Platform description + audiogram caption + newsletter teaser + LinkedIn post |
| Competitive Show Analysis | $79 | 48h | `market-competitors/SKILL.md` | Benchmark vs 3 competing shows |
| Podcast Launch Playbook | $149 | 72h | `market-launch/SKILL.md` | Full launch plan — 8-week timeline, guest framework, calendar, copy |

### Bundle Pricing
- **Content + Brand** ($229, saves $28): Standard + Brand Voice Guide + 30-Day Calendar
- **Full Growth** ($299, saves $46): Premium + Brand Voice + 30-Day Calendar + Email Sequence
- **Launch Ready** ($249, saves $18): Starter + Launch Playbook + Guest Outreach Templates

---

## Public Sample Endpoint

Unauthenticated endpoint for lead generation: `POST /api/sample/podcast`

- Rate-limited: 1 request per email per 24 hours (enforced via DB)
- Inputs: `email`, `show_name`, `episode_title`, `host_name`; `audio` (optional file upload)
- If no audio: sets `demo: True` → pipeline uses canned demo transcript (skips Whisper)
- If file provided: validates extension, max 200 MB, uploads to Drive
- Runs standard pipeline → emails sample (watermarked/redacted) PDF to requester

---

## Pipeline — Core (both services)

1. **Order detection** — UI trigger, CLI, or sample endpoint. `service_type` field routes to
   correct content generation prompts.
2. **Input processing** — audio files: Whisper transcription directly.
   Video files (Service B): `extract_audio_from_video.py` → FFmpeg audio strip → Whisper.
   Demo mode: skips both, uses canned transcript.
3. **Content generation** — Claude API, tier-aware and service-type-aware prompts.
   Service A: show notes, timestamps, guest bio, social captions, newsletter excerpt, SEO.
   Service B: transcript, show notes, blog post, multi-platform captions, newsletter draft,
   plus brand voice injection if cached.
4. **Packaging** — Google Doc creation + full PDF + sample PDF.
5. **Human review gate** — 30-min window (email + Slack alert). NEVER auto-approved for
   Service B. Auto-approve for Service A after 20 validated orders per tier.
6. **Delivery** — view-only Google Doc link + PDF emailed to `client_email`.

---

## Pipeline — Marketing Add-ons (Service A)

Add-ons run as separate pipeline jobs after core delivery. Each creates its own output
document in the client's Google Drive order folder.

```
detect_addon_items(order)
  → for each addon:
      route_to_addon_skill(addon_type, episode_context)
        → run_addon_skill(transcript, brand_context, tier)
          → package_addon_output(drive_folder_id)
            → append_to_delivery_doc(view_link)
```

### `episode_context` object (shared across all skills):
```json
{
  "show_name": "...",
  "episode_title": "...",
  "host_name": "...",
  "niche": "business | tech | health | marketing | ...",
  "audience": "...",
  "transcript": "...",
  "show_notes": "...",
  "existing_brand_voice": "...",
  "service_type": "show_notes | repurposing_pack",
  "input_type": "audio | video"
}
```

---

## Skills — Built ✅

### `media/generate_brand_voice.py` ✅ (Sprint 3b)
- Input: 2–3 episode transcripts + show name/niche
- Extracts: tone descriptors, vocabulary patterns, sentence length, POV, topics-to-avoid
- Output: structured Brand Voice Guide (Google Doc, 4–6 pages)
- Cached as `/PodcastNotes/{client}/brand-voice.json` for reuse across orders

### `media/generate_promo_copy.py` ✅ (Sprint 3b)
- Input: episode transcript + show_notes + episode_context
- Generates: platform description (230–250 chars), audiogram caption, newsletter teaser
  (100–150 words), LinkedIn post; injects brand voice when cached
- Output: single Google Doc with all 4 pieces labelled

---

## Skills — To Build

### `media/extract_audio_from_video.py` (Sprint 3e — NEW)
- Input: video file path (Drive URL or `/tmp/` path on Railway)
- Uses: FFmpeg subprocess (`ffmpeg -i input.mp4 -vn -acodec mp3 output.mp3`)
- Output: audio file path ready for Whisper transcription
- Handles: .mp4, .mov, .mkv, .avi, .webm
- Error handling: unsupported format → raise `UnsupportedVideoFormat`; FFmpeg not found →
  raise `FFmpegNotInstalled` with install note for Railway Nixpack config
- Platform skill — venture-agnostic. Lives in `/platform/skills/media/extract_audio_from_video.py`
- Railway note: add `ffmpeg` to `nixpacks.toml` packages or Railway build command

### `media/generate_blog_post.py` (Sprint 3e — NEW)
- Input: transcript + episode_context + brand_voice (optional)
- Generates: full blog post, 800–1,200 words (Standard) or 1,200–1,800 words (Pro)
- Structure: H1 title, intro paragraph, 3–4 H2 sections with supporting paragraphs,
  pull quote, conclusion with CTA, meta description (155 chars), 5 SEO tags
- Brand voice injected from cache if available
- Output: Google Doc with full article + meta description block at bottom
- Platform skill — venture-agnostic. Lives in `/platform/skills/media/generate_blog_post.py`

### `media/generate_caption_pack.py` (Sprint 3e — NEW)
- Input: transcript + show_notes + episode_context + platforms list + caption_count
- Generates per-platform captions — each platform has distinct tone and format constraints:
  - LinkedIn: 150–300 words, professional, hook + value + CTA, no hashtag overload
  - Instagram: 100–150 words, conversational, 5–10 hashtags, emoji-friendly
  - Twitter/X: 240–270 chars, punchy, quote-driven, 1–2 hashtags
  - TikTok: 80–100 words, hook in first 3 words, trending hashtags
  - YouTube: 100–150 words, keyword-rich, CTA to subscribe/playlist
- Output: single Google Doc, one section per platform, labelled and copyable
- Platform skill — venture-agnostic. Lives in `/platform/skills/media/generate_caption_pack.py`

### `media/generate_newsletter_draft.py` (Sprint 3e — NEW)
- Input: transcript + show_notes + episode_context + brand_voice (optional)
- Generates: full newsletter edition, 300–500 words
- Structure: subject line (A/B variant), preview text (90 chars), hook paragraph,
  3 key takeaways from episode, pull quote, listener CTA (reply / share / rate)
- Distinct from `newsletter excerpt` in Service A (which is 100–150 words only)
- Output: Google Doc with subject lines at top + full body
- Platform skill — venture-agnostic.

### `media/generate_social_calendar.py` (Sprint 4b)
- Wraps `market-social/SKILL.md` from ai-marketing-claude
- Input: 4 episode transcripts + show_notes + brand_voice
- Output: Google Doc as table (Day | Platform | Hook | Post | Type) — 30 rows

### `media/generate_email_sequence.py` (Sprint 4b)
- Wraps `market-emails/SKILL.md` from ai-marketing-claude
- Input: 3–5 episodes + brand_voice + niche
- Generates: 5-email welcome/nurture sequence
- Output: Google Doc with subject + preview text + body per email

### `media/generate_guest_outreach.py` (Sprint 5b)
- Input: episode_context + guest tier (cold/warm/follow-up)
- Generates 3 email templates with [PERSONALISATION] placeholders
- Output: Google Doc with 3 templates + personalisation guidance

### `media/generate_launch_playbook.py` (Sprint 6b)
- Wraps `market-launch/SKILL.md` from ai-marketing-claude
- Input: show concept, target audience, niche, host background
- Output: Google Doc (15–20 pages), 8-week pre-launch plan

---

## Reused Skills (from ai-marketing-claude via platform)

| Skill | Used for |
|---|---|
| `skills/market-social/SKILL.md` | 30-Day Social Calendar |
| `skills/market-emails/SKILL.md` | Listener Email Sequence |
| `skills/market-landing/SKILL.md` | Show Landing Page Audit |
| `skills/market-competitors/SKILL.md` | Competitive Show Analysis |
| `skills/market-launch/SKILL.md` | Podcast Launch Playbook |

All ai-marketing-claude skills receive a `podcast_context_prefix` at invocation:
show name, niche, audience, cached brand voice if available.

---

## Order Status State Machine

```
pending → processing_input →
  [audio path]  transcribing → transcribed
  [video path]  extracting_audio → audio_ready → transcribing → transcribed
→ generating → generated →
packaging → packaged → review_pending → approved →
delivering → delivered
         └→ addons_pending → [addon_pipeline] → addons_complete → delivering
         └→ revision_requested → re_delivering → delivered
         └→ failed
```

---

## Environment Variables

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

# Service B additions
REPURPOSING_PACK_HUMAN_REVIEW_ALWAYS=true   # Never auto-approve Service B
REPURPOSING_PACK_VIDEO_MAX_MB=500
FFMPEG_BINARY=ffmpeg                         # Path or binary name on Railway

# Add-on flags (v2)
ADDON_AUTO_REVIEW=false
BRAND_VOICE_CACHE_ENABLED=true
ADDON_MAX_PARALLEL=3
SOCIAL_CALENDAR_PLATFORMS=linkedin,instagram,twitter
EMAIL_SEQUENCE_LENGTH=5
CAPTION_PLATFORMS=linkedin,instagram,twitter,tiktok,youtube
CAPTION_COUNT_STANDARD=5
CAPTION_COUNT_STARTER=3
```

---

## Railway / Infrastructure Notes

- **FFmpeg on Railway:** Add to `nixpacks.toml`:
  ```toml
  [phases.setup]
  nixPkgs = ["ffmpeg"]
  ```
- **Video file handling:** Video files uploaded via web UI are written to Drive synchronously
  in the web router (same pattern as Sprint 3d audio uploads — web and worker containers
  do not share `/tmp`). Worker downloads from Drive before processing.
- **File size:** Service B allows up to 500 MB. Railway ephemeral storage is adequate for
  processing; files are deleted from `/tmp` after Drive upload.

---

## Sprint Roadmap

### Sprint 3b — Brand Voice + Promo Copy ✅ DONE (2026-03-25)
- [x] `generate_brand_voice.py` — analyses 2–3 transcripts, produces structured Brand Voice Guide; cached as JSON per show (`{show-slug}-brand-voice.json`) for reuse across orders
- [x] `generate_promo_copy.py` — platform description (230–250 chars), audiogram caption, newsletter teaser (100–150 words), LinkedIn post; injects brand voice when cached
- [x] Add-on runner wired into `content_studio/pipeline.py` Phase 3b; `--addons brand-voice promo-copy` CLI flags
- [x] Tested end-to-end: real 60-min episode → full premium pipeline; brand voice + promo copy outputs saved alongside order
- [x] Premium truncation fix: `CLAUDE_MAX_TOKENS_PREMIUM = 16000` in `config.py`; pipeline uses tier-aware token ceiling

### Sprint 3c — Public Sample Endpoint ✅ DONE (2026-04-05)
- [x] `POST /api/sample/podcast` — optional audio upload; demo mode when no file provided
- [x] Demo transcript fallback in `_run_phase1_transcribe()` — checks `demo` flag before raising `ValueError`
- [x] Rate limiting (1 req/email/24h via DB), Drive upload for real files, Resend email delivery
- [x] Fixed field name mismatch in echoforge-site JS (`file` → `audio`)
- [x] `openai` added to `requirements.txt`

### Sprint 3d — Admin Order Form ✅ DONE (2026-04-05)
- [x] Audio file upload picker replaces URL text input in `ContentStudio.tsx`
- [x] `content_studio.py` router rewritten to accept `multipart/form-data` with `UploadFile`
- [x] Audio uploaded to Drive synchronously in the web router (web and worker are separate Railway containers — `/tmp` not shared)
- [x] Full form fields added: Customer Email, Show Name, Episode Title, Host Name, Guest Name, Special Instructions
- [x] Fixed delivery email showing "None" for episode title — all fields now included in order payload
- [x] Google Doc sharing changed to `share_anyone_with_link=True` so clients can open links without a Google account
- [x] Drive upload errors now return HTTP 503 with detail message (CORS was stripping headers from unhandled 500s)
- [x] Unified Drive auth: `create_gdoc.py` and `drive_organise.py` now use `get_drive_service()` from `_drive_auth.py` (was hardcoded to service account, causing `storageQuotaExceeded`)

### Sprint 3e — Service B Foundation: Video Input + New Output Types
Goal: unlock the Done-for-You Content Repurposing Pack as a sellable product.

- [ ] Add `service_type` field to order model + UI + pipeline routing
- [ ] `media/extract_audio_from_video.py` — FFmpeg audio extraction from video files
- [ ] Add `ffmpeg` to `nixpacks.toml` Railway build config
- [ ] Extend web UI file picker to accept video extensions (.mp4, .mov, .mkv, .avi)
- [ ] Update pipeline `_run_phase1_transcribe()` to detect video → call
  `extract_audio_from_video` before Whisper
- [ ] `media/generate_blog_post.py` — 800–1,800 word blog article from transcript
- [ ] `media/generate_caption_pack.py` — per-platform caption sets (LinkedIn, IG, X,
  TikTok, YouTube); count driven by tier (3 Starter / 5 Standard+)
- [ ] `media/generate_newsletter_draft.py` — full newsletter with subject + preview text
- [ ] Update content generation prompt router to call new skills for `service_type = repurposing_pack`
- [ ] Service B pricing tiers (£49/£99/£149) in config + UI tier selector
- [ ] Ensure human review gate is forced `ON` for all Service B orders regardless of
  `AUTO_APPROVE` flag — add `REPURPOSING_PACK_HUMAN_REVIEW_ALWAYS=true` check
- [ ] Update delivery email template for Service B (different output list)
- [ ] Update echoforge.biz landing page: add Content Repurposing Pack service card
- [ ] Update Fiverr gig: add repurposing pack as a new gig (separate from podcast notes)
- [ ] Test end-to-end: video file → audio extraction → transcription → blog + captions +
  newsletter → Google Doc → review → delivery

### Sprint 4b — Social Calendar + Email Sequence
- [ ] `media/generate_social_calendar.py` wrapper for `market-social/SKILL.md`
- [ ] `media/generate_email_sequence.py` wrapper for `market-emails/SKILL.md`
- [ ] Both wired into add-on pipeline with `podcast_context_prefix`

### Sprint 5b — Guest Outreach + Landing Page Audit
- [ ] `media/generate_guest_outreach.py`
- [ ] Wire `market-landing/SKILL.md` with show website URL (optional form field)

### Sprint 6b — Competitive Analysis + Launch Playbook + Bundles
- [ ] Wire `market-competitors/SKILL.md` with 3 competing show URLs
- [ ] `media/generate_launch_playbook.py` wrapper
- [ ] Bundle SKU detection in order intake
- [ ] Bundle discount logic in revenue logging

---

## Pre-Sprint 3e Checklist

- [ ] Add `ffmpeg` to Railway `nixpacks.toml` and confirm build succeeds
- [ ] Test `extract_audio_from_video.py` locally with a .mp4 file
- [ ] Confirm 500 MB uploads work through the existing Drive upload path
- [ ] Add Service B pricing to Fiverr as a new gig
- [ ] Add `service_type` enum to DB order model + Alembic migration
- [ ] Add `input_type` (audio/video) to DB order model + Alembic migration

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
| Human review — Service B | ALWAYS on — never auto-approve (human review is the product) |
| Video processing | FFmpeg on Railway (nixpack) for audio extraction; no GPU needed |
| Blog post | New platform skill (venture-agnostic); injected into Service B generation phase |
| Caption packs | Per-platform prompts in `generate_caption_pack.py`; not per-platform files |
| Newsletter draft | Full draft (300–500 words) in Service B; excerpt only (100–150w) in Service A |

---

## Pipeline Status
<!-- managed by update_task.py -->

| Roadmap ID | Task | Status | Note | Updated |
|---|---|---|---|---|
| U-01 | Core Podcast Pipeline — Sprint 1 & 2 | ✅ done | Manual trigger pipeline live | 2026-03-25 |
| H-06 | Podcast Sample Generator | ✅ done | Demo mode + pdf-only flag | 2026-03-25 |
| M-03 | Podcast Add-on: Brand Voice Guide | ✅ done | generate_brand_voice.py, cached JSON | 2026-03-25 |
| M-04 | Podcast Add-on: Episode Promotional Copy | ✅ done | generate_promo_copy.py | 2026-03-25 |
| M-05 | Podcast Add-on: 30-Day Social Calendar | 🔲 planned | Sprint 4b | — |
| M-06 | Podcast Add-on: Listener Email Sequence | 🔲 planned | Sprint 4b | — |
| M-11 | Podcast Add-on: Guest Outreach Templates | 🔲 planned | Sprint 5b | — |
| M-12 | Podcast Add-on: Show Landing Page Audit | 🔲 planned | Sprint 5b | — |
| L-02 | Podcast Add-on: Competitive Show Analysis | 🔲 idea | Sprint 6b | — |
| L-03 | Podcast Add-on: Launch Playbook | 🔲 idea | Sprint 6b | — |
| NEW | Service B — Content Repurposing Pack | 🔲 planned | Sprint 3e — all items above | — |
