# Venture A — Etsy Digital Image Shop
## Claude Code Context File — Etsy Venture

**Read the root `/CLAUDE.md` first for platform architecture rules.**
**This file contains only what is specific to the Etsy venture.**

---

## Isolation Rule

You are the assistant for the Etsy venture only.
- Read and write files under `/ventures/etsy/` and `/platform/` only
- Never read, write, or reference files under any other `/ventures/` directory
- If a task requires touching another venture's files, stop and ask the user

---

## What This Venture Is

An automated Etsy shop selling AI-generated digital wall art. The pipeline takes a theme (e.g. "botanical line art"), researches demand, generates product images, packages them for sale, and gets them listed on Etsy — with two deliberate human checkpoints before anything goes live.

**This is Venture A.** It is also the proving ground for the platform — every skill written here must be venture-agnostic so Venture B can reuse it without modification.

---

## Etsy-Specific Tech

| Layer | Tool | Notes |
|---|---|---|
| Marketplace | Etsy Open API v3 | Listings, images, files, ads |
| Image generation | DALL-E 3 (active) | Primary tool; Gemini Imagen 3 pending billing |
| Mockups | DALL-E 2 outpainting | 3 room scenes per listing; artwork is preserved pixel-perfect |
| Review PDFs | fpdf2 | review-sheet.pdf per listing (WeasyPrint avoided — Windows GTK3 dep) |
| Promotion | Pinterest API v5 | Pins per listing |
| Social scheduling | Buffer API | Instagram + Facebook queue |

---

## Google Drive Folder Structure

All assets live under `/EtsyShop/` in Google Drive. The service account has Editor access.
Drive folder IDs are stored in `.env` after first run of `scripts/setup_drive_folders.py`.

```
/EtsyShop/
  01-research/          # themes-{date}.csv + themes-{date}.json
  02-subjects/
    {theme-slug}/       # subjects-{theme}.json — 20 subjects per theme
  03-images/
    {listing-slug}/
      {slug}-raw.png        # DALL-E 3 output (background-whitened)
      variants/             # 8 files: 4 sizes × PNG + JPG
      mockups/              # 3 DALL-E 2 outpainted room scenes
      metadata.json         # Single source of truth for this listing
  04-packages/
    {listing-slug}/
      delivery.zip          # Buyer download (≤ 20 MB)
      review-sheet.pdf      # Human review sheet (fpdf2)
  05-review/
    pending/            # Listings awaiting human sign-off
    approved/           # Approved — triggers Phase 6
    rejected/           # Rejected with notes for regeneration
  06-audit/
    drafts/             # Etsy draft listing IDs + all content
    published/          # Confirmed live listing URLs + IDs
  07-promo/             # Pinterest pins, social copy, ad config
```

---

## The 7-Phase Pipeline

### Phase 1 — Theme Research  ✓ Sprint 2 complete
**Script:** `scripts/run_phase1.py`
**Output:** `themes-{date}.csv` + `themes-{date}.json` in `/01-research/`
**Skills:** `research/web_search.py`, `research/trend_analysis.py`, `research/competitor_scan.py`, `storage/drive_write.py`

Scoring model (demand 40% / competition 35% / monetisation 25%). Themes ≥ 60 proceed to Phase 2.
Demand score blends avg and peak interest: `avg * 0.35 + peak * 0.65`.

---

### Phase 2 — Subject List Generation  ✓ Sprint 2 complete
**Script:** `scripts/run_phase2.py`
**Output:** `subjects-{theme}.json` in `/02-subjects/{theme-slug}/`
**Skills:** Claude API (claude-sonnet-4-6), `storage/drive_write.py`

Each subject JSON object contains:
- `subject_id` — lowercase hyphenated slug (e.g. `botanical-01`)
- `title_draft` — SEO-first Etsy title (≤ 140 chars)
- `description` — Full Etsy listing description: artwork description + WHAT YOU GET section + closing CTA
- `image_prompt` — detailed DALL-E 3 prompt (no aspect ratio flags — added by skill)
- `style_notes` — one sentence of art direction
- `etsy_tags` — array of exactly 13 tags (max 20 chars each)
- `price_usd` — 4.99 (standard) or 7.99 (premium)
- `quality_tier` — "standard" or "premium"
- `status` — state machine field (see Subject Status below)

---

### Phase 3 — Image Generation  ✓ Sprint 3 complete
**Script:** `scripts/run_phase3.py`
**Output:** raw PNG + 8 variant files + 3 mockup JPGs + `metadata.json` in `/03-images/{slug}/`
**Skills:** `media/generate_image.py`, `media/resize_image.py`, `media/create_mockup.py`, `storage/drive_write.py`

Image generation notes:
- DALL-E 3 prompt suffix enforces pure white background (#FFFFFF, no texture, no gradient)
- After download, `_whiten_background()` post-processes with numpy: pixels ≥ 230 on all channels → pure white. This is the reliable safety net since DALL-E 3 often produces cream/off-white.
- Mockups use DALL-E 2 outpainting: artwork placed on canvas with opaque mask → DALL-E 2 generates the room around it. Artwork pixels are never modified.

Variant sizes (Pillow fit-with-pad — full artwork always visible, never cropped):

| Variant | Dimensions | Format |
|---|---|---|
| Square | 3000 × 3000 px | PNG + JPG |
| Portrait | 2400 × 3600 px | PNG + JPG |
| Landscape | 3600 × 2400 px | PNG + JPG |
| 4K wide | 3840 × 2160 px | PNG + JPG |

Mockup scenes: `living_room`, `office`, `bedroom` (DALL-E 2 outpainting, $0.02/image).

`metadata.json` is written alongside the images — it is the single source of truth for that listing (title, description, tags, price, prompt, tool used, cost, paths to all files).

---

### Phase 4 — Packaging  ✓ Sprint 3 complete
**Script:** `scripts/run_phase4.py`
**Output:** `delivery.zip` + `review-sheet.pdf` in `/04-packages/{slug}/`
**Skills:** `packaging/create_zip.py`, `packaging/generate_pdf.py`, `storage/drive_write.py`

ZIP compression fallback: standard deflate → PNG 8-bit quantise → replace PNGs with JPEGs.
ZIP must be ≤ 20 MB (Etsy hard limit).

Review PDF auto-checks (must all pass before human review):
- Title ≤ 140 chars
- Tag count = 13
- ZIP ≤ 20 MB
- 3 mockups present
- Raw image on disk

---

### Phase 5 — Human Review ★ HUMAN GATE  Sprint 4
**Skills:** `packaging/send_email.py`, `storage/drive_write.py`

Gmail SMTP notification with PDF attachment. Requires `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, `REVIEW_EMAIL_TO` env vars.

Human actions: Approve / Reject / Edit+Regenerate.

---

### Phase 6 — Store Upload ★ HUMAN GATE  Sprint 4
**Constraint: agent NEVER sets state=active. Human publishes manually in Etsy dashboard.**

---

### Phase 7 — Promotion  Sprint 5
Pinterest pin + Etsy Ads ($1–2/day) + Buffer social queue.

---

## Subject Status State Machine

```
pending
  → generating      (Phase 3 starts)
  → generated       (Phase 3 complete — raw + sized + mockups + metadata.json saved)
  → packaged        (Phase 4 complete — ZIP + review PDF created)
  → review_pending  (Phase 5 notification sent)
  → approved        (human approved)
  → rejected        (human rejected — terminal for this cycle)
  → draft_live      (Phase 6 — Etsy draft created)
  → published       (human clicked Publish — Phase 7 triggered)
```

---

## Sprint Roadmap

| Sprint | Goal | Status |
|---|---|---|
| Sprint 1 — Foundations | Drive bootstrap, DALL-E 3 image gen, Pillow resize | **Complete** |
| Sprint 2 — Research + subjects | Phase 1 theme scoring (SerpAPI), Phase 2 subject gen (Claude) | **Complete** |
| Sprint 3 — Pipeline through packaging | Phase 3 (image+resize+mockups), Phase 4 (ZIP+PDF), metadata.json | **Complete** |
| Sprint 4 — Human review + Etsy drafts | Phase 5 email notify, Phase 6 Etsy draft upload (never publish), orchestrator loop | **Active** |
| Sprint 5 — Promotion | Pinterest, Etsy Ads, Buffer social | Planned |
| Sprint 6 — LangGraph | Replace scripts with graph, Tool Router budget/health, Redis, LangSmith | Planned |

---

## Current Status

**Active sprint: Sprint 4**

Sprint 3 deliverables complete:
- [x] `create_zip.py` — delivery ZIP with compression fallback
- [x] `generate_pdf.py` — review-sheet PDF via fpdf2
- [x] `send_email.py` — Gmail SMTP notification
- [x] `run_phase_3`, `run_phase_4` in pipeline.py
- [x] `scripts/run_phase3.py`, `scripts/run_phase4.py`
- [x] `metadata.json` written alongside images (single source of truth)
- [x] Background whitening post-processing (`_whiten_background`)
- [x] Description field in Phase 2 subjects (artwork + WHAT YOU GET + CTA)
- [x] Pricing: standard=4.99, premium=7.99 (no middle tier)

Sprint 4 next actions:
- [ ] `scripts/run_pipeline.py` — orchestrator loop (Phase 3 → 4 for all 20 subjects, status checkpointing, resumable)
- [ ] Phase 5 email notification implementation
- [ ] Phase 6 Etsy draft upload (state=draft only, never active)

---

## Environment Variables

Key variables (full list in `.env.example`):

```
OPENAI_API_KEY=              # DALL-E 3 + DALL-E 2 (image gen + mockups)
ANTHROPIC_API_KEY=           # Claude API (Phase 2 subject generation)
SERPAPI_API_KEY=             # Google Trends + Etsy competitor data (Phase 1)
GOOGLE_CREDENTIALS_PATH=./google_credentials.json
GOOGLE_DRIVE_ROOT_FOLDER_ID= # Set after running setup_drive_folders.py
GMAIL_SENDER=                # Phase 5 email (Sprint 4)
GMAIL_APP_PASSWORD=          # Gmail App Password (Sprint 4)
REVIEW_EMAIL_TO=             # Reviewer email address(es) (Sprint 4)
ETSY_API_KEY=                # Sprint 4
ETSY_API_SECRET=             # Sprint 4
ETSY_SHOP_ID=                # Sprint 4
```

---

## Etsy-Specific Constraints

- **Never set Etsy listing state to `active`** — agent always creates drafts. Human publishes manually.
- **delivery.zip must be ≤ 20 MB** — Etsy hard limit. Checked in Phase 4.
- **Etsy requires exactly 13 tags per listing** — auto-checked in review PDF.
- **Etsy title must be ≤ 140 characters** — auto-checked in review PDF.
- **Background must be pure white #FFFFFF** — enforced via prompt + numpy post-processing in `generate_via_dalle3()`.
- **Google Drive service account** must have Editor access to `/EtsyShop/` root.
- **DALL-E 3 is the active image generation tool** — flip `active=true` for Gemini in `skills.json` when billing is confirmed. No other code changes needed.

---

## Per-Listing Cost

| Item | Cost |
|---|---|
| DALL-E 3 raw image | $0.04 |
| DALL-E 2 mockups (3×) | $0.06 |
| **Total per listing** | **$0.10** |
| 20 listings (one theme) | $2.00 |
| Claude API (Phase 2, per theme) | ~$0.05 |
