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

## Pipeline — Core (existing, unchanged)

1. Order detection (Upwork API / Fiverr Gmail polling)
2. Transcription — GPT-4o Mini Transcribe ($0.003/min)
3. Content generation — Claude API, tier-aware
4. Packaging — Google Doc creation + PDF backup
5. Human review gate (30-min window; auto-approve after 20 validated orders)
6. Delivery — view-only Google Doc link

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

### Sprint 3b — Brand Voice + Promo Copy
- Build `generate_brand_voice.py` + caching
- Build `generate_promo_copy.py`
- Test: 2 episodes → brand voice guide → promo copy using that guide

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
| Human review | Active for all add-on types first 20 orders; then AUTO per type |
