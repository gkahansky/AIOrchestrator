# EtsyShop — AI Automation Platform
## Claude Code Context File

**Read this entire file before writing any code or making any changes.**
**This is the authoritative context file. It overrides any assumptions from prior context.**

---

## What This Project Is

An automated Etsy digital image shop built on a multi-agent AI platform. The platform is designed to eventually power multiple business ventures — the Etsy shop is Venture A, the first build.

The pipeline takes a theme (e.g. "minimalist botanical line art"), researches demand, generates product images, packages them for sale, and gets them listed on Etsy — with two deliberate human checkpoints before anything goes live.

---

## ⚠️ Critical Architecture Rules — Read Before Writing Any Code

This project is **not a monolith**. The code must be structured so that skills (reusable capabilities) are completely separate from pipeline logic (Etsy-specific orchestration). Violating this creates refactoring debt that blocks every future venture.

### The two-layer model

**Skills** live in `/platform/skills/` — atomic, reusable functions that know nothing about Etsy:
- They take typed inputs and return typed outputs
- They have no side effects beyond their stated purpose
- They never reference Etsy, or any venture name, internally
- They never call other skills — composition happens in the pipeline
- They never write to Drive directly — that is the pipeline's job

**Pipelines** live in `/ventures/etsy/` — thin orchestration that chains skills together:
- They import from `/platform/skills/` only
- They handle Drive paths, status updates, and phase flow
- They contain the Etsy-specific business logic
- They should be short (~150 lines max) — if longer, extract to a skill

### The dependency direction is one-way

```
/ventures/etsy/pipeline.py   →   imports from   →   /platform/skills/
```

**Never the reverse.** A skill file must never import from `/ventures/`.

### The split test

Before writing any function, ask: *"Would a future Content Studio or Analytics venture want this?"*
- **Yes** → it belongs in `/platform/skills/`
- **No, it's Etsy-specific** → it belongs in `/ventures/etsy/`

### Common violations to avoid

| Wrong | Right |
|---|---|
| `def generate_and_save_image(prompt, etsy_slug)` | `generate_image(prompt)` in skill + `drive_write(path, img)` called by pipeline |
| `def research_etsy_keywords(theme)` with Etsy API logic inside a skill | `web_search(query)` skill + Etsy-specific query building in pipeline |
| `import ventures.etsy.config` inside a skill file | Skills never import venture config |
| One `etsy_agent.py` file that does all 7 phases | `pipeline.py` calls individual skill functions per phase |

---

## Repository Structure

**Note:** `platform/` and `ventures/` live under `src/` to avoid shadowing Python's stdlib `platform` module.
Scripts add `src/` to `sys.path` explicitly. Pytest uses `conftest.py` for the same.

```
/src/
/platform/
  skills/
    research/
      web_search.py           # Generic web search — any venture
      trend_analysis.py       # Score and rank topics by demand — any venture
      competitor_scan.py      # Crawl competitor data — any venture
    media/
      generate_image.py       # Tool Router lives here (MJ / Gemini / DALL-E)
      resize_image.py         # Pillow wrapper — 4 aspect ratios
      create_mockup.py        # Placeit / custom templates — any image product
    storage/
      drive_read.py           # Read from Google Drive — every venture
      drive_write.py          # Write to Google Drive — every venture
      drive_organise.py       # Folder creation, moves — every venture
    comms/
      send_email.py           # Gmail via MCP — every venture
      send_slack.py           # Slack via MCP — every venture
      create_pin.py           # Pinterest API — any visual product venture
      schedule_social.py      # Buffer API — any venture with social presence
    finance/
      log_cost.py             # Record API/tool spend — every venture
      log_revenue.py          # Record sales — every venture
      calculate_roas.py       # ROAS calculation — any venture with paid ads
    packaging/
      create_zip.py           # Assemble delivery ZIP — any digital product
      generate_pdf.py         # WeasyPrint PDF generation — any venture
  registry/
    skills.json               # Skill catalogue: capability tags, tools, costs
    tool_router.py            # Selects tool based on tier, budget, availability

/src/ventures/
  etsy/
    pipeline.py               # Orchestrates skills for the 7-phase Etsy flow
    config.py                 # Etsy API settings, Drive paths, price rules
    prompts.py                # Etsy-specific agent system prompts
  content_studio/             # Future Venture B — new pipeline, same skills
    pipeline.py
    config.py

/scripts/                     # One-off setup and maintenance scripts
  setup_drive_folders.py      # Bootstrap Drive folder structure
  generate_image.py           # Sprint 1 standalone test script
  resize_image.py             # Sprint 1 standalone test script

/tests/
  test_skills/                # Unit tests for each skill in isolation
  test_pipeline/              # Integration tests for the Etsy pipeline
```

---

## Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| LLM | Claude API — Sonnet 4 | All agent intelligence |
| Orchestration | LangGraph | Added in Sprint 6 — not yet built |
| Image gen (active) | DALL-E 3 | Active primary while Gemini billing is pending |
| Image gen (next) | Gemini Imagen 3 | Pending Google billing approval — flip active=true in skills.json when ready |
| Image processing | Pillow (Python) | Resize to 4 aspect ratios |
| Mockups | Placeit by Envato | 3 mockups per listing |
| Storage | Google Drive API | All media, metadata, audit logs |
| Review PDFs | WeasyPrint (Python) | review-sheet.pdf per listing |
| Compute | Railway | Cloud hosting for agents/scripts |
| Session memory | Redis Cloud | Pub/sub + short-term state |
| Long-term memory | Qdrant Cloud | Research history, brand guidelines |
| Observability | LangSmith | Agent tracing and cost tracking |
| API layer | FastAPI | HTTP wrapper around agents |
| Etsy integration | Etsy Open API v3 | Listings, images, files, ads |
| Promotion | Pinterest API v5 + Buffer API | Pins + social scheduling |

---

## Skill Registry — skills.json Contract

Every skill must be registered here. Agents query this file at runtime.

```json
{
  "image-generation": {
    "capability": "image-generation",
    "tools": [
      {
        "id": "dalle3",
        "tier": "standard",
        "cost_per_call": 0.04,
        "module": "platform.skills.media.generate_image",
        "active": true,
        "note": "Active primary tool while Gemini billing is pending"
      },
      {
        "id": "gemini-imagen",
        "tier": "premium",
        "cost_per_call": 0.03,
        "module": "platform.skills.media.generate_image",
        "active": false,
        "note": "Pending Google billing approval — flip active to true when ready, then promote to standard tier"
      }
    ]
  }
}
```

**To add a new tool:** add a new entry to the tools array and set active: true. No other code changes required.
**To disable a tool:** set active: false. The Tool Router automatically routes to the next option.
**To add a new capability:** add a new top-level key with the same structure.

---

## Tool Router — Selection Logic

The Tool Router is implemented in `/platform/registry/tool_router.py`. It is the **only** place tool selection logic lives. No if/else tool selection anywhere else in the codebase.

Selection order (first matching rule wins):
1. **Explicit override** — caller passes `tool_id='midjourney'` → use that tool
2. **Tier match** — match requested tier (premium/standard) to best active tool
3. **Budget cap** — if monthly spend for a tool is over its cap, skip it
4. **Availability** — if tool health-check fails, skip it
5. **Fallback** — use the tool marked `tier='fallback'`; if that also fails, raise and alert Slack

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
      raw/              # Original full-res Midjourney output
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
- `image_prompt` — full Midjourney prompt string including `--ar`, `--v`, `--style`
- `style_notes` — art direction for mockups and sizing
- `target_keywords` — top 5 SEO keywords
- `price_usd` — recommended listing price
- `quality_tier` — Standard or Premium (controls Tool Router in Phase 3)
- `status` — state machine: `pending → generating → generated → packaged → review_pending → approved/rejected → draft_live → published`

---

### Phase 3 — Image Generation
**Agent:** Executor + Tool Router
**Human gate:** No
**Output:** Raw images + 4 sized variants + 3 mockups per subject
**Storage:** `/03-images/{listing-slug}/`
**Skills used:** `media/generate_image.py`, `media/resize_image.py`, `media/create_mockup.py`, `storage/drive_write.py`

Tool Router config (Phase 1):
- Standard tier → DALL-E 3 (active — primary until Gemini billing confirmed)
- Next standard → Gemini Imagen 3 (active: false, pending Google billing approval)

Required image sizes (Pillow resizes from MJ native output):

| Variant | Dimensions | Aspect ratio | Format |
|---|---|---|---|
| Square | 3000 × 3000 px | 1:1 | PNG + JPG |
| Portrait | 2400 × 3600 px | 2:3 | PNG + JPG |
| Landscape | 3600 × 2400 px | 3:2 | PNG + JPG |
| 4K wide | 3840 × 2160 px | 16:9 | PNG + JPG |

Etsy minimum: 2000px on shortest side. All variants meet this.

Mockups (3 per listing — via Placeit API or custom Pillow templates):
1. Framed print — white wall, thin black/wood frame (main listing image, slot 1)
2. Canvas wrap — lifestyle living room scene (slot 2)
3. Poster flat lay — overhead desk scene (slot 3)

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

## Sprint Roadmap

| Sprint | Duration | Goal | Status |
|---|---|---|---|
| **Sprint 1 — Foundations** | 1–2 weeks | Scripts only: Drive folder bootstrap + Midjourney image gen via useapi.net + Pillow resize. No agents. Manual trigger. | **Active** |
| **Sprint 2 — Research + subject list** | 2 weeks | Research agent: Etsy API trend queries + SerpAPI Google Trends. Output themes CSV + subjects.json. | Planned |
| **Sprint 3 — Full pipeline through packaging** | 2–3 weeks | Executor processes subjects.json: MJ generation → Pillow resize → Placeit mockups → delivery.zip → review-sheet.pdf. Comms agent Gmail notification. | Planned |
| **Sprint 4 — Human review gate + Etsy drafts** | 1–2 weeks | Phase 5 review form. Phase 6 Etsy upload (draft only, stops before publish). | Planned |
| **Sprint 5 — Promotion** | 1–2 weeks | Pinterest API pins. Etsy Ads auto-enrol. Buffer for Instagram/Facebook. Finance agent 30-day ROAS review. | Planned |
| **Sprint 6 — LangGraph + Tool Router** | 2 weeks | Replace scripts with LangGraph graph. Add Tool Router. Add Gemini Imagen. Redis pub/sub. LangSmith observability. | Planned |

---

## Current Status

**Active sprint: Sprint 1**

- [x] Repo initialised with `.gitignore` and `.env.example`
- [x] Python environment set up with required packages
- [x] Drive folder bootstrap script written: `scripts/setup_drive_folders.py`
- [ ] Drive bootstrap script tested and confirmed
- [ ] Image generation script (DALL-E 3): `scripts/generate_image.py`
- [ ] Pillow resize script: `scripts/resize_image.py`
- [ ] End-to-end test: one prompt → raw image → 4 sized variants → saved to Drive

**Next action:** Test `scripts/setup_drive_folders.py` and confirm all 7 top-level folders + subfolders exist in Drive with correct permissions.

---

## Environment Variables

See `.env.example` for the full list. Key variables for Sprint 1:

```
USEAPI_TOKEN=                    # useapi.net API token
USEAPI_DISCORD_CHANNEL=          # Discord channel ID from useapi.net dashboard
GOOGLE_CREDENTIALS_PATH=./google_credentials.json
GOOGLE_DRIVE_ROOT_FOLDER_ID=     # Set after running setup_drive_folders.py
```

Drive folder IDs are generated by `setup_drive_folders.py` and saved to `drive_folder_ids.txt` — copy them into `.env` after first run.

For later sprints, additional variables will be added for Etsy OAuth tokens, SerpAPI, Pinterest, Buffer, etc. Full list in `.env.example`.

---

## Key Constraints

- **Never put Etsy-specific logic inside `/platform/skills/`** — skills must be venture-agnostic
- **Never import from `/ventures/` inside a skill file** — dependency direction is one-way
- **Never set Etsy listing state to `active`** — the agent always creates drafts. Human publishes manually.
- **Never write a function that both calls an API and writes to Drive** — these are two separate skills composed by the pipeline
- **delivery.zip must be ≤ 20MB** — Etsy hard limit. Pillow script checks before Phase 4 completes.
- **Etsy requires 13 tags per listing** — auto-check in review-sheet must validate this
- **Google Drive service account** must have Editor access to `/EtsyShop/` root — shared manually in Drive UI
- **Pinterest API review takes 1–2 weeks** — apply during Sprint 1 so it's ready by Sprint 5
- **`.env` and `google_credentials.json` must never be committed to git** — `.gitignore` blocks both
- **DALL-E 3 is the active image generation tool** — Gemini Imagen 3 replaces it once Google billing is approved (flip `active=true` in `skills.json`, no other changes needed)

---

## Agent Roles (for later sprints)

| Agent | Capability | First used in sprint |
|---|---|---|
| Research | Etsy API trend queries, SerpAPI Google Trends, competitor analysis | Sprint 2 |
| Executor | Image generation, Drive file ops, Etsy API calls, packaging | Sprint 1 (as scripts), Sprint 3 (as agent) |
| Code gen | Pillow resize scripts, WeasyPrint PDF generation | Sprint 3 |
| Comms | Gmail notifications, Slack updates, social copy drafting | Sprint 3 |
| QA | Review listing compliance, SEO quality checks | Sprint 4 |
| Finance | Cost/revenue tracking, ROAS review, budget alerts | Sprint 5 |
| UI/UX | Shop branding, listing image layouts | Sprint 6+ |
| SW Architect | Platform evolution planning | Sprint 6+ |

---

## Monthly Cost Estimate (Phase 1)

| Item | Cost |
|---|---|
| DALL-E 3 (per image ~$0.04) | Variable |
| Placeit mockups | $14.95 |
| Railway compute | $5–$20 |
| Claude API | $20–$80 |
| Etsy Ads (optional) | $30–$60 |
| Google Drive, Redis, Qdrant | $0 (free tiers) |
| **Total range** | **$125–$355/mo** |

Dominant costs drop when Gemini Imagen replaces DALL-E 3 as the standard-tier tool (~$0.03/image vs ~$0.04/image, plus no subscription fee).
