# Venture A — Etsy Digital Image Shop
## Claude Code Context File — Etsy Venture

> ⏸️ **STATUS: ON HOLD**
> Blocked on one external approval:
> - **Etsy API key** — application submitted, awaiting approval
>
> Gemini Imagen 4 is live and tested. Resume Sprint 1 once Etsy API key is confirmed.

**Read the root `/CLAUDE_root.md` first for platform architecture rules.**
**This file contains only what is specific to the Etsy venture.**

---

## Isolation Rule

You are the assistant for the Etsy venture only.
- Read and write files under `/ventures/etsy/` and `/platform/` only
- Never read, write, or reference files under any other `/ventures/` directory
- If a task requires touching another venture's files, stop and ask the user

---

## What This Venture Is

An automated Etsy shop selling AI-generated digital wall art. The pipeline takes a theme (e.g. "minimalist botanical line art"), researches demand, generates product images, packages them for sale, and gets them listed on Etsy — with two deliberate human checkpoints before anything goes live.

**This is Venture A.** It is also the proving ground for the platform — every skill written here must be venture-agnostic so Venture B can reuse it without modification.

---

## Etsy-Specific Tech

| Layer | Tool | Notes |
|---|---|---|
| Marketplace | Etsy Open API v3 | Listings, images, files, ads |
| Mockups | `gemini-2.5-flash-image` (primary) / Pillow composite (fallback) | Image-in, image-out: actual artwork PNG passed as input — mockups are visually consistent with the real artwork |
| Review PDFs | WeasyPrint (Python) | review-sheet.pdf per listing |
| Promotion | Pinterest API v5 | Pins per listing |
| Social scheduling | Buffer API | Instagram + Facebook queue |

---

## Google Drive Folder Structure

All assets live under `/EtsyShop/` in Google Drive. The service account has Editor access.
Drive folder IDs are stored in `.env` after first run of `scripts/setup_drive_folders.py`.

```
/EtsyShop/
  01-research/          # trend-report-{date}.json, themes-{date}.csv
  02-subjects/
    {theme-slug}/       # subjects-{theme}.json — 20 subjects per theme
  03-images/
    {listing-slug}/
      raw/              # Original full-res image output
      sized/            # Resized exports: square, portrait, landscape, 4K
      mockups/          # Framed print, canvas wrap, poster flat lay
      metadata.json     # Title, description, tags, price, prompts, SEO
  04-packages/
    {listing-slug}/
      delivery.zip      # Buyer download file — all sized variants
      review-sheet.pdf  # Human review sheet with thumbnails + checklist
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

### Phase 1 — Idea & Theme Generation
**Agent:** Research
**Human gate:** No
**Output:** Ranked list of 20–50 themes with demand score, competition level, price benchmark
**Storage:** `/01-research/` — `themes-{date}.csv` + `themes-{date}.json`
**Skills used:** `research/web_search.py`, `research/trend_analysis.py`, `research/competitor_scan.py`, `storage/drive_write.py`

Scoring model:
- Demand (40%): Google Trends 90-day growth + Etsy monthly search count
- Competition (35%): Inverse of listing count and top-seller review density
- Monetisation (25%): Average sale price × estimated conversion rate

Themes scoring ≥ 60 proceed to Phase 2.

---

### Phase 2 — Subject List Generation
**Agent:** Research + Comms
**Human gate:** No
**Output:** 20 image subjects per theme — the work queue for Phase 3
**Storage:** `/02-subjects/{theme-slug}/subjects-{theme}.json`
**Skills used:** `research/trend_analysis.py`, `comms/send_email.py`, `storage/drive_write.py`

Each subject contains:
- `subject_id` — unique slug (e.g. `botanical-monstera-01`)
- `title_draft` — SEO-first Etsy title (140 char max)
- `image_prompt` — full image generation prompt string including aspect ratio and style flags
- `style_notes` — art direction for mockups and sizing
- `target_keywords` — top 5 SEO keywords
- `price_usd` — recommended listing price
- `quality_tier` — Standard or Premium (controls Tool Router in Phase 3)
- `status` — state machine field (see Subject Status below)

---

### Phase 3 — Image Generation
**Agent:** Executor + Tool Router
**Human gate:** No
**Output:** Raw images + 4 sized variants + 3 mockups per subject
**Storage:** `/03-images/{listing-slug}/`
**Skills used:** `media/generate_image.py`, `media/resize_image.py`, `media/create_mockup.py`, `storage/drive_write.py`

Tool Router config (current):
- Standard tier → Gemini Imagen 4 (`imagen-4.0-generate-001`, active — primary)
- Fallback → DALL-E 3 (active — used if Gemini unavailable)

Required image sizes (Pillow resizes from raw output):

| Variant | Dimensions | Aspect ratio | Format |
|---|---|---|---|
| Square | 3000 × 3000 px | 1:1 | PNG + JPG |
| Portrait | 2400 × 3600 px | 2:3 | PNG + JPG |
| Landscape | 3600 × 2400 px | 3:2 | PNG + JPG |
| 4K wide | 3840 × 2160 px | 16:9 | PNG + JPG |

Etsy minimum: 2000px on shortest side. All variants meet this.

Mockups (3 per listing — `gemini-2.5-flash-image`, image-in, image-out):
1. Product shot — framed print on clean neutral wall (main listing image, slot 1)
2. Living room — Scandinavian lifestyle scene with sofa, natural light (slot 2)
3. Flat lay — overhead desk scene with minimal props (slot 3)

The actual artwork PNG is passed as image input to Gemini — the model renders the
real artwork into each scene, ensuring visual consistency.
Skill: `media/create_mockup.py` → `create_mockup_gemini()`.
Pillow composite fallback active if Gemini is unavailable.

---

### Phase 4 — Packaging
**Agent:** Executor + Code gen
**Human gate:** No
**Output:** `delivery.zip` (buyer download) + `review-sheet.pdf` (human review)
**Storage:** `/04-packages/{listing-slug}/`
**Skills used:** `packaging/create_zip.py`, `packaging/generate_pdf.py`, `storage/drive_write.py`

delivery.zip structure:
```
README.txt
square/image-3000x3000.png + .jpg
portrait/image-2400x3600.png + .jpg
landscape/image-3600x2400.png + .jpg
4k/image-3840x2160.png + .jpg
```

ZIP must be ≤ 20MB (Etsy hard limit). Compression fallback order: PNG 16-bit → PNG 8-bit → JPEG 92%.

review-sheet.pdf sections: header, 3 mockup thumbnails + 1 raw, metadata block, auto-checks (resolution, tag count = 13, title ≤ 140 chars, ZIP ≤ 20MB, 3 mockups), Drive links, decision field (Approve / Reject / Edit / Regenerate).

---

### Phase 5 — Human Review ★ HUMAN GATE
**Agent:** Comms (sends notification only — takes no other action)
**Human gate:** YES — approve / reject / edit / regenerate
**Output:** Approved listing queue
**Storage:** `/05-review/pending/` → `/05-review/approved/` or `/05-review/rejected/`
**Skills used:** `comms/send_email.py`, `comms/send_slack.py`, `storage/drive_write.py`

Comms agent sends:
- Email: "Etsy review batch ready — {N} listings pending your approval"
- Direct Drive links to each review-sheet.pdf
- Optional Slack notification to `#etsy-review`

Human actions:
- **Approve** → listing moves to `/05-review/approved/`, Phase 6 begins
- **Approve with edit** → Comms applies edits to metadata.json, re-packages, Phase 6 begins
- **Reject** → moved to `/05-review/rejected/`, logged for next cycle
- **Regenerate** → Executor re-runs Phase 3 with amended prompt, loops back through 4 and 5

Executor polls `/05-review/` every 30 minutes for status changes.

---

### Phase 6 — Store Upload & Final Publish ★ HUMAN GATE
**Agent:** Executor (creates Etsy drafts only — NEVER sets state=active)
**Human gate:** YES — human clicks Publish in Etsy dashboard
**Output:** Etsy draft listings (human publishes manually)
**Storage:** `/06-audit/drafts/` → `/06-audit/published/`
**Skills used:** `storage/drive_read.py`, `comms/send_email.py`, `finance/log_cost.py`

Executor API sequence (agent stops before publish):
1. `POST /v3/application/shops/{shop_id}/listings` — draft (state=draft)
2. `POST /v3/application/listings/{listing_id}/images` ×3 — attach mockups
3. `POST /v3/application/listings/{listing_id}/files` — attach delivery.zip
4. `PUT /v3/application/listings/{listing_id}/taxonomy_node` — set category
5. **AGENT STOPS HERE** — writes draft URL to `/06-audit/drafts/{slug}.json`, emails human

**The agent must never call the publish endpoint. This is a hard constraint.**

After human publishes: Executor polls Etsy GET listings every 15 min, detects newly active listings, writes to `/06-audit/published/listing-ids.csv`, triggers Phase 7.

---

### Phase 7 — Promotion
**Agent:** Comms + Executor
**Human gate:** No
**Output:** Pinterest pins, Etsy Ads activated, social posts queued
**Storage:** `/07-promo/`
**Skills used:** `comms/create_pin.py`, `comms/schedule_social.py`, `finance/log_cost.py`

| Channel | Action | Tool | Cost |
|---|---|---|---|
| Pinterest | Pin per listing: mockup 1 (portrait), title, 150-char description, 5 hashtags, Etsy link | Pinterest API v5 | $0 |
| Etsy Ads | Auto-bid at $1–$2/day for 30 days | Etsy Ads API | $30–$60/listing/mo |
| Instagram | Caption + 30 hashtags + Etsy link, queued in Buffer | Buffer API | $0 |
| Facebook | Reused Instagram caption, shortened hashtags | Buffer API | $0 |

Etsy Ads 30-day ROAS review (Finance agent):
- ROAS < 2×: pause ads
- ROAS 2–4×: maintain budget
- ROAS > 4×: increase to $3–$5/day

---

## Subject Status State Machine

The `status` field in `subjects.json` is the lightweight state machine that tracks each subject through the pipeline. The pipeline reads and writes this field — it never assumes phase completion without checking status.

```
pending
  → generating      (Phase 3 starts)
  → generated       (Phase 3 complete — raw + sized + mockups saved)
  → packaged        (Phase 4 complete — ZIP + review sheet created)
  → review_pending  (Phase 5 notification sent)
  → approved        (human approved)
  → rejected        (human rejected — terminal state for this cycle)
  → draft_live      (Phase 6 — Etsy draft created)
  → published       (human clicked Publish — Phase 7 triggered)
```

---

## Pipeline Phase Status

| Phase | Description | Status | Notes |
|---|---|---|---|
| **Phase 1** | Theme research — SerpAPI + Google Trends, score & rank themes, save CSV/JSON to Drive | ✅ Done | Requires SERPAPI_KEY |
| **Phase 2** | Subject list — Claude generates 20 subjects per theme (titles, prompts, tags, price) | ✅ Done | Requires ANTHROPIC_API_KEY |
| **Phase 3** | Image gen → resize → mockups → metadata.json + Drive upload | ✅ Done | Gemini artwork + Gemini multimodal mockups (artwork as input) |
| **Phase 4** | Packaging — delivery.zip (≤ 20 MB enforced) + review-sheet.pdf (auto-checks) | ✅ Done | — |
| **Phase 5** | Human review notification — email + Slack alert, approval gate | 🔴 Not started | `send_email` + `send_slack` stubs; Etsy API key needed |
| **Phase 6** | Etsy draft upload — creates listing, attaches images + ZIP. Never auto-publishes. | 🔴 Not started | Etsy API key + OAuth skill not written |
| **Phase 7** | Promotion — Pinterest pin, Etsy Ads enrol, Buffer social queue, ROAS review | 🔴 Not started | Pinterest, Buffer, Etsy Ads API skills not written |

---

## Sprint Roadmap

| Sprint | Goal | Status |
|---|---|---|
| **Sprint 1 — Foundations** | Drive folder bootstrap, image gen, Pillow resize | ✅ Done |
| **Sprint 2 — Research + subject list** | SerpAPI trends, Claude subject generation | ✅ Done |
| **Sprint 3 — Full pipeline through packaging** | Gemini image gen → consistent mockups → ZIP → review PDF | ✅ Done |
| **Sprint 4 — Human review gate + Etsy drafts** | Phase 5 email/Slack notification, Phase 6 Etsy draft API upload | 🔴 Blocked — Etsy API key pending |
| **Sprint 5 — Promotion** | Pinterest pins, Etsy Ads, Buffer social queue, 30-day ROAS review | 🔴 Not started |
| **Sprint 6 — LangGraph + observability** | Replace scripts with LangGraph graph, Redis pub/sub, LangSmith tracing | 🔴 Not started |

---

## Current Status

**Status: ON HOLD — waiting for Etsy API key (Sprint 4 blocker)**

Phases 1–4 fully implemented and tested end-to-end:
- [x] Drive folder structure bootstrap: `scripts/setup_drive_folders.py`
- [x] Phase 1 — theme research: `scripts/run_phase1.py`
- [x] Phase 2 — subject list generation: `scripts/run_phase2.py`
- [x] Phase 3 — Gemini artwork + Gemini multimodal mockups (artwork as input): `scripts/run_phase3.py`
- [x] Phase 4 — delivery ZIP + review PDF: `scripts/run_phase4.py`
- [x] Full Phase 3 tested: eucalyptus botanical-03, $0.10/listing total

**Blocked on Etsy API key:** Sprint 4 (phases 5 + 6) cannot proceed without it.

---

## Build Plan — What Remains

### Sprint 4 — unblocks when Etsy API key arrives

1. `aiplatform/skills/comms/send_email.py` — implement Gmail send (currently a stub)
2. `aiplatform/skills/comms/send_slack.py` — implement Slack webhook send (currently a stub)
3. **Phase 5** — review gate: email + Slack alert with Drive links, poll for approval, auto-approve after 20 validated orders
4. `aiplatform/skills/marketplace/etsy_upload.py` — Etsy OAuth2 client, create draft listing, attach images (3 mockups), attach delivery.zip
5. **Phase 6** pipeline function — full Etsy draft flow; agent stops before publish; polls for human publish confirmation

### Sprint 5 — after first listings go live

6. `aiplatform/skills/comms/create_pin.py` — Pinterest API v5: pin per listing (mockup 1, title, Etsy link)
7. Etsy Ads auto-enrol at $1–2/day via Etsy Ads API
8. `aiplatform/skills/comms/schedule_social.py` — Buffer API: queue Instagram + Facebook posts
9. **Phase 7** pipeline function — orchestrates steps 6–8 on publish confirmation
10. Finance agent 30-day ROAS review: ROAS < 2× pause, 2–4× maintain, > 4× increase to $3–5/day

### Sprint 6 — scale optimisation

11. Replace sequential script calls with LangGraph stateful graph (only when pipeline has > 5 branching phases)
12. LangSmith tracing for all agent calls
13. Redis pub/sub for parallel multi-listing runs (event: `phase3_complete` → triggers phase 4 without tight coupling)

---

## Environment Variables

See `.env.example` for the full list.

```
# Active — required for Phases 1–4
GOOGLE_AI_API_KEY=               # Gemini Imagen 4 (artwork) + gemini-2.5-flash-image (mockups)
OPENAI_API_KEY=                  # DALL-E 3 fallback only
ANTHROPIC_API_KEY=               # Claude subject generation (Phase 2)
SERPAPI_KEY=                     # Google Trends + Etsy listing research (Phase 1)
GOOGLE_CREDENTIALS_PATH=./google_credentials.json
GOOGLE_DRIVE_ROOT_FOLDER_ID=     # Set after running scripts/setup_drive_folders.py
DRIVE_01_RESEARCH=
DRIVE_02_SUBJECTS=
DRIVE_03_IMAGES=
DRIVE_04_PACKAGES=
DRIVE_05_REVIEW=
DRIVE_06_AUDIT=
DRIVE_07_PROMO=

# Sprint 4 — needed when Etsy API key arrives
ETSY_API_KEY=
ETSY_API_SECRET=
ETSY_SHOP_ID=
HUMAN_REVIEW_EMAIL=
SLACK_WEBHOOK_URL=

# Sprint 5
PINTEREST_ACCESS_TOKEN=
BUFFER_ACCESS_TOKEN=
```

---

## Etsy-Specific Constraints

- **Never set Etsy listing state to `active`** — the agent always creates drafts. Human publishes manually.
- **delivery.zip must be ≤ 20MB** — Etsy hard limit. Pillow script checks before Phase 4 completes.
- **Etsy requires exactly 13 tags per listing** — auto-check in review-sheet must validate this
- **Etsy title must be ≤ 140 characters** — auto-check in review-sheet must validate this
- **Google Drive service account** must have Editor access to `/EtsyShop/` root — shared manually in Drive UI
- **Pinterest API review takes 1–2 weeks** — apply during Sprint 1 so it's ready by Sprint 5
- **Gemini Imagen 4 is the active image generation tool** — `active=true` in `skills.json`. DALL-E 3 remains as fallback.

---

## Monthly Cost Estimate (Phase 1)

| Item | Cost |
|---|---|
| Gemini Imagen 4 artwork (~$0.04/image) | Variable |
| Gemini Imagen 4 Fast mockups (~$0.02/image × 3 = $0.06/listing) | Variable |
| Railway compute | $5–$20/mo |
| Claude API | $20–$80/mo |
| Etsy Ads (optional) | $30–$60/listing/mo |
| Google Drive, Redis, Qdrant | $0 (free tiers) |
| **Total range** | **$55–$160/mo** |
