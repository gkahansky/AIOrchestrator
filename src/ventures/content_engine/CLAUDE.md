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
