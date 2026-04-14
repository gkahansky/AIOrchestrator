# Cloud Migration & Management App — Plan of Action

**Date:** 2026-03-29
**Delivers:** (1) Migration Plan — Local CLI → Cloud Platform, (2) UI/UX Functional Requirements

---

## Context

The AI-Infra platform (MiroPrintStudio + EchoForge) currently runs entirely as CLI scripts on a local Windows machine. Every pipeline run requires opening a terminal, typing a command, and staying connected. Human review gates require editing JSON files directly. There is no visibility across ventures, no financial dashboard, and no way to hand off a task and come back to it.

This plan covers migrating the full platform to the cloud, adding a web management app, and designing the UI/UX functional requirements for all three active ventures plus the platform layer.

---

---

# DOCUMENT 1 — Migration Plan: Local CLI → Cloud Platform

---

## Architecture Decision: Modular Monolith

**Recommendation: Single FastAPI app with strict venture module boundaries.**

The codebase is already structured this way — a shared skills layer and isolated venture pipelines. The API mirrors that: one FastAPI app, one router per venture, one shared platform router. Venture routers import only from their own pipeline and config (the existing one-way dependency rule is preserved).

**Why not microservices:** One developer, shared credentials (same Anthropic key, same Drive account, same Slack), shared skill library, no independent scaling needs. Three Railway services, three credential stores, and three CI/CD pipelines are not justified yet.

**Future extraction path:** When you have 10+ ventures or one venture needs different scaling, each venture router + pipeline file is already isolated enough to lift into its own service without touching the skills layer.

---

## Target Infrastructure Stack

| Layer | Tool | Notes |
|---|---|---|
| Backend | FastAPI + Uvicorn | Already planned; uncomment in requirements.txt |
| Job queue | Celery + Redis | Replaces blocking CLI scripts with async background tasks |
| Database | PostgreSQL (Railway plugin) | Replaces local JSON files for order/job state |
| Asset storage | Google Drive | No change — stays as the asset layer |
| Cloud compute | Railway | Two environments (production, staging) |
| Frontend | React + Vite | Hosted on Vercel (free tier, zero-config) |
| Auth (V1) | Static bearer token | Personal dashboard — no user table needed yet |
| Auth (V2) | Auth0 or Clerk | When multi-user access is needed |
| Long-term memory | Qdrant Cloud | Already planned; provision when research memory features are built |

---

## Long-Term Architecture Consideration

The current two-layer model (skills = reusable, ventures = thin orchestration) is the right foundation for long-term growth. It remains valid for SaaS. The only thing that needs to change as the platform grows is the **execution model** (sync CLI → async jobs) and **state persistence** (JSON files → database). The skill and pipeline architecture does not need to change.

For future multi-tenant SaaS (multiple clients running their own instances): the `jobs` database table already supports a `tenant_id` column addition. The skills layer is stateless and tenant-agnostic. The only addition needed is an auth layer in front of the API. This is a V3 concern — do not design for it now.

---

## Database Schema

Four tables replace all local JSON file state.

### `jobs` table
The top-level record for every pipeline run (replaces every `order.json` file).

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | Replaces string order IDs |
| venture | ENUM | `etsy`, `marketing_audit`, `content_studio` |
| status | VARCHAR(50) | Mirrors each pipeline's state machine |
| phase_current | SMALLINT | 1–7 depending on venture |
| phase_total | SMALLINT | Total phases for this venture |
| input_data | JSONB | Order fields at creation (url, tier, audio_path, etc.) |
| output_data | JSONB | Accumulated outputs (Drive links, pdf_path, listing_id, etc.) |
| error_message | TEXT | Last failure message |
| created_at / updated_at / completed_at | TIMESTAMPTZ | Lifecycle timestamps |
| celery_task_id | VARCHAR | For polling Celery task status |
| environment | ENUM | `production`, `staging` |

### `phase_events` table
Append-only audit log of every state transition per job.

| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| job_id | UUID FK → jobs | |
| phase | SMALLINT | |
| event_type | ENUM | `started`, `completed`, `failed`, `paused`, `resumed` |
| details | JSONB | Phase-specific: cost_usd, drive_link, file_count, etc. |
| created_at | TIMESTAMPTZ | |

### `cost_events` table
Replaces the current stub `log_cost()` function (which returns `{"logged": False}`).

| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| job_id | UUID FK → jobs | Nullable (some costs are platform-level) |
| venture / capability / tool_id | VARCHAR | e.g. `etsy`, `image-generation`, `gemini-imagen` |
| cost_usd | NUMERIC(10,6) | |
| tokens_in / tokens_out | INTEGER | For LLM calls |
| created_at | TIMESTAMPTZ | |

### `revenue_events` table
Replaces the current stub `log_revenue()` function.

| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| job_id | UUID FK → jobs | |
| venture / source | VARCHAR | Source: `fiverr`, `etsy`, `direct` |
| amount_usd / fee_usd / net_usd | NUMERIC(10,2) | |
| created_at | TIMESTAMPTZ | |

---

## New Files to Create

**Backend files** (to be created during implementation):

```
src/aiplatform/webapp/
  main.py                         # FastAPI app factory, startup events, auth middleware
  auth.py                         # Bearer token dependency
  schemas.py                      # Pydantic request/response models
  routers/
    platform/
      jobs.py                     # GET/POST /jobs, POST /jobs/{id}/approve|reject
      dashboard.py                # GET /dashboard (aggregated stats)
      finance.py                  # GET /finance (cost + revenue summary)
      settings.py                 # GET/PUT /settings (API keys, venture configs)
    ventures/
      etsy.py                     # POST /ventures/etsy/trigger, GET /ventures/etsy/listings
      marketing_audit.py          # POST /ventures/marketing-audit/trigger
      content_studio.py           # POST /ventures/content-studio/trigger

src/aiplatform/
  worker.py                       # Celery app + one task per venture pipeline
  database/
    models.py                     # SQLAlchemy ORM: Job, PhaseEvent, CostEvent, RevenueEvent
    session.py                    # Engine + session factory
    migrations/ (Alembic)

Dockerfile                        # Railway deployment
railway.toml                      # Service config (web + worker start commands)
```

**Frontend files** — implementation deferred.
User will supply a UI design MD file + Google Stitch design project.
Frontend implementation begins after design assets are received.

```
frontend/                         # React + Vite — DO NOT CREATE until design is provided
```

---

## Refactoring Required

### Changes to existing pipeline code (surgical, not rewrites)

| What | Change | Effort |
|---|---|---|
| Output directory | Replace `./output/` hardcoded paths with `os.getenv("OUTPUT_DIR", "./output")` in venture configs | 3 lines per venture |
| State persistence | Add DB write alongside existing JSON write in each `_save_order()` call | ~20 lines per pipeline |
| Human review gate | Replace "edit order.json and re-run" with Celery task pause + `/approve` endpoint resume | ~30 lines per pipeline |
| `log_cost()` | Implement the stub to insert a `cost_events` row | 15 lines |
| Google Drive auth | Add startup block in `main.py` to materialize service account JSON from env var | 10 lines |
| `ai-marketing-claude` sibling repo | Add as git submodule OR copy `generate_pdf_report.py` into `src/ventures/marketing_audit/` | 1 command |

### What does NOT change

- All skill files in `src/aiplatform/skills/` — zero changes
- `skills.json` and `tool_router.py` — zero changes
- All venture `config.py`, `prompts.py` files — zero changes
- Google Drive as the asset storage layer — zero changes
- The hard constraint: Etsy listings are NEVER set to `active` — stays in `etsy_upload.py`
- Jira integration — zero changes

---

## Prod / Staging Environment Design

### Railway project structure

```
Railway Project: AIOrchestrator
  Environment: production    → deploys from main branch
    Service: web-prod          uvicorn src.aiplatform.webapp.main:app ...
    Service: worker-prod       celery -A src.aiplatform.worker worker
    Plugin: PostgreSQL

  Environment: staging       → deploys from develop branch
    Service: web-staging
    Service: worker-staging
    Plugin: PostgreSQL (free tier)
```

Redis Cloud (free tier) is shared across environments using different database indices.

### Test environment cost isolation

Environment variables active in **staging only**:

| Var | Value | Effect |
|---|---|---|
| `IMAGE_GEN_MOCK=true` | true | `generate_image` returns a pre-baked test PNG — no Gemini/DALL-E call |
| `TRANSCRIPTION_MOCK=true` | true | `transcribe_audio` returns a canned transcript — no Whisper call |
| `NOTIFICATIONS_ENABLED=false` | false | `send_email` + `send_slack` log only — no actual sends |
| `DRIVE_*` | Staging folder IDs | All assets go to `/AIOrchestrator-Staging/` in Drive |
| `ETSY_*` | Etsy sandbox credentials | Sandbox API, no real listings |
| `CLAUDE_MAX_TOKENS=512` | 512 | Cap LLM cost per call in staging |

### Code promotion workflow

```
feature branch → PR → pytest via GitHub Actions → merge to develop → auto-deploy to staging
                                                 → QA in staging UI
                                                 → PR develop→main → auto-deploy to production
```

---

## Migration Steps (Phased)

### Phase 0 — Foundation (local only, no breakage)
1. Add SQLAlchemy models + Alembic migrations (connect to local Postgres, not yet used by pipelines)
2. Implement `log_cost()` stub → actual DB insert
3. Add `OUTPUT_DIR` env var to all venture configs; default to `./output` (no behaviour change)
4. Add `ai-marketing-claude` as git submodule
5. Fix `pipeline.py` sibling-repo path resolution

### Phase 1 — Database-backed state (local only)
6. Add DB write to each pipeline's `_save_order()` alongside existing JSON write
7. Write `scripts/migrate_json_to_db.py` — import all existing `output/*/order.json` files
8. Verify local workflows are identical (JSON files still written, DB also written)

### Phase 2 — FastAPI + Celery (deploy to Railway staging)
9. Build `webapp/main.py`, all routers, `auth.py`, `schemas.py`
10. Build `worker.py` — one Celery task per venture pipeline
11. Implement review approval endpoint (`POST /jobs/{id}/approve`)
12. Deploy to Railway staging; test each venture end-to-end via HTTP

### Phase 3 — React frontend MVP
13. Build React app: job list, trigger forms, approve/reject buttons
14. Connect to staging Railway URL; test full UI loop

### Phase 4 — Production cutover
15. Set up Railway production environment; migrate all env vars with real keys
16. Run `migrate_json_to_db.py` against production DB
17. Set up DNS (`api.echoforge.biz` → Railway production domain)
18. Cut over — local CLI still works as a fallback

---

## Human Tasks Required

### Accounts to create
- [ ] **Railway account** — railway.app, connect GitHub repo, create "AIOrchestrator" project
- [ ] **Vercel account** — vercel.com, connect GitHub repo for React frontend
- [ ] **Redis Cloud account** — redis.io free tier, create staging + prod databases
- [ ] **Local PostgreSQL** — for Phase 0/1 development (`docker run -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres:16`)

### Google Cloud setup
- [ ] Create a **service account** in Google Cloud Console specifically for cloud deployment (separate from local OAuth account)
- [ ] Grant it **Google Drive API** access
- [ ] Download the service account JSON key file
- [ ] Base64-encode it: `base64 -i service-account.json` → store result as `GOOGLE_SERVICE_ACCOUNT_JSON` env var in Railway
- [ ] Share all production Drive folders with the service account email (Editor access)
- [ ] Create `/AIOrchestrator-Staging/` folder structure in Drive; share with same service account

### Etsy sandbox
- [ ] Request Etsy sandbox credentials from the developer console (for staging environment)

### Railway setup
- [ ] Create "AIOrchestrator" project in Railway
- [ ] Create `production` and `staging` environments
- [ ] Add PostgreSQL plugin to each environment
- [ ] Add all env vars from `.env` file (staging: use mock values per table above)
- [ ] Set start commands: `web` → uvicorn, `worker` → celery

### DNS
- [ ] Add CNAME: `api.echoforge.biz` → Railway production web service domain
- [ ] (Optional) Add frontend domain on Vercel

---

---

# DOCUMENT 2 — UI/UX Functional Requirements

**Scope:** Functionality only. Visual design to be provided separately via Google Stitch.
**Architecture:** Single-page React app — sidebar navigation between sections.

---

## Global Layout

**Navigation sidebar** (always visible):
- Platform logo + "AI-Infra" label
- **Dashboard** (platform-wide overview)
- **Ventures:** Etsy / MiroPrintStudio · Marketing Audit / EchoForge · Podcast Notes / EchoForge
- **Finance**
- **Settings**
- Environment badge: `PRODUCTION` or `STAGING` (prominent, colour-coded)

**Top bar:**
- Page title
- Global alerts badge (failed jobs, jobs needing review)
- "New Order ▾" quick-trigger dropdown

---

## 1. Dashboard (Platform-Wide)

### KPI Cards (top row)
- Active jobs count
- Jobs awaiting review count
- Revenue this month (all ventures)
- API spend this month (all ventures)
- Net this month (revenue − costs, colour-coded)

### Jobs in Flight
Table: Venture | Job ID | Summary | Status | Phase | Started | Last Updated | Actions (View / Approve / Cancel)
Filter bar: By venture | By status | Date range

### Review Queue
All jobs paused at a human review gate, across all ventures.
Per item: venture icon | job summary | phase name | time waiting
Actions: **Approve** | **Reject** | **View**

### Recent Completions
Last 10 completed jobs: Venture | Summary | Completed At | Cost | Revenue

### Failed Jobs (hidden if empty)
Error snippet + **Retry** | **View details** | **Dismiss**

### System Health
- Celery worker: Online / Offline
- Database, Redis, Google Drive: Connected / Error
- API key status per service: last successful call or "untested"

---

## 2. Etsy Venture — MiroPrintStudio

### Overview Tab
- Subjects by status (generating / packaging / review / draft / published)
- Published listings count + total Etsy revenue
- Phase 7 queue (Etsy Ads ROAS)
- Quick actions: Run Phase 1 | View all listings

### Pipeline Control Tab
One card per phase, triggerable from the UI.

| Phase | Input | Output shown |
|---|---|---|
| 1 — Theme Research | Trigger button | Theme table with scores, Drive CSV link |
| 2 — Subject Generation | Select theme | 20 subjects table, edit title/tags/price per row |
| 3 — Image Generation | Select subject(s) | Per-subject gallery: raw + 3 mockups; cost per subject |
| 4 — Packaging | Select generated subjects | ZIP size check, auto-checks (resolution, 13 tags, title ≤140, 3 mockups) |
| 5 — Send for Review | Select packaged subjects | Email/Slack sent confirmation, Drive links list |
| 6 — Etsy Draft Upload | Approved subjects (auto-populated) | Listing ID, draft URL, images 3/3, ZIP attached; "NEVER auto-publishes" label |
| 7 — Promotion | — | "Coming Soon — Sprint 5" |

### Listings Tab
All listings (draft + published).
Columns: Thumbnail | Title | Status | Images | ZIP | Etsy Link | Drive Link | Created
Filter: All / Draft / Published / Pending Review / Rejected
Bulk: Send for review | Upload to Etsy

### Review Queue Tab
Per item: mockup 1 thumbnail | title | 13 tags | price | PDF link | Drive link
Actions: **Approve** | **Approve with Edit** (inline title/description/tags form) | **Reject** | **Regenerate** (back to Phase 3)

### Settings Tab
- Shop ID (display only), OAuth token status + Refresh button
- Drive folder IDs with links
- Default prices, theme min score, review email — editable
- Auto-approve toggle + threshold
- Etsy Ads daily budget range
- Buffer account Connect / Disconnect

---

## 3. Marketing Audit Venture — EchoForge

### Overview Tab
Active orders by status | Delivered this month + revenue | Average audit score | New Audit Order button

### New Order Form
- Target URL (required)
- Tier: Snapshot $49 / Full Audit $149 / Audit + Strategy $249 (radio, with description)
- Brand name
- Competitor URLs (0–3 rows, tier-dependent)
- Client context: audience, weak spots, budget (optional)
- Client email
- Report type: Full + Sample / Full only / Sample only
- Submit → creates job, redirects to job detail

### Orders List
Columns: Order ID | URL | Tier | Status | Phase | Score | Cost | Created | Client Email | Actions
Actions: View | Approve | Download PDF | Resend delivery
Filter: By status | By tier | Date range

### Job Detail
1. Order summary + phase progress bar
2. Scrape results: page count, competitor count, warnings
3. Audit report: overall score (large), grade letter, 6-dimension score bars, findings by severity, quick wins / medium-term / strategic
4. Reports: Full PDF | Sample PDF | Full MD | Sample MD — with file size and Drive links
5. Review gate: **Approve & Deliver** | **Request Revision** (with notes textarea)
6. Delivery: timestamp, email confirmation

### Settings Tab
- Tier prices and turnaround times — editable
- Scoring dimension weights (validated, must sum to 1.0)
- Review email, auto-approve toggle
- Drive folder IDs

---

## 4. Podcast Notes Venture — EchoForge

### Overview Tab
Active orders | Delivered this month + revenue | Add-on attach rate | New Podcast Order button

### New Order Form
- Audio file upload (MP3/WAV, max 500 MB) OR Demo mode toggle
- Tier: Starter $49 / Standard $79 / Premium $119 (radio, with section list per tier)
- Show name, episode title, host name, episode number (optional)
- Niche dropdown, target audience text
- Client email
- Add-ons: Brand Voice Guide +$79 | Promotional Copy Pack +$39
- Submit → upload progress, redirect to job detail

### Orders List
Columns: Order ID | Show | Episode | Tier | Status | Add-ons | Cost | Created | Actions

### Job Detail
1. Order summary + phase progress bar
2. Transcript: full text (collapsible), duration, cost
3. Generated content: tabs per section (Show Notes / Timestamps / Guest Bio / Social Captions / Newsletter / SEO) — shown per tier
4. Packages: Google Doc link | Full PDF | Sample PDF — with Drive links
5. Add-ons (if enabled): Brand Voice (tone/vocabulary/style) | Promo Copy (4 pieces)
6. Review gate: **Approve & Deliver** | **Request Revision**
7. Delivery: timestamp, email confirmation

### Settings Tab
- Tier prices and section config — editable
- Add-on prices, review email, auto-approve, brand voice cache toggle
- Drive folder IDs

---

## 5. Finance

### Revenue Summary
- Monthly revenue chart (12 months, per-venture)
- Revenue by venture (pie/stacked bar)
- Revenue by tier per venture
- Revenue by source (Fiverr / Etsy / direct)

### Cost Summary
- Monthly API spend chart (12 months, per-tool)
- Cost by tool table: tool | capability | calls this month | total cost | avg cost per call
- Top 5 most expensive jobs this month
- Projected monthly cost

### P&L View
Per-venture: Revenue | Costs | Net | Margin %
Platform total row
Time range: This month / Last 3 months / Last 12 months / Custom

### ROAS (Etsy-only)
Per listing: title | ad spend | revenue | ROAS | recommendation (pause / maintain / increase)
30-day rolling ROAS chart per listing
Bulk: Apply ROAS recommendations

---

## 6. Settings

### API Keys
Table: Service | Key (masked, last 6 chars) | Status | Last used | Test | Edit
Services: Anthropic, OpenAI, Google AI, SerpAPI, Etsy, Gmail, Slack, Pinterest, Buffer, Jira, LangSmith
Warning banner if any key unset or last test failed.

### Notification Settings
- Review email (platform default, per-venture override)
- Slack token + channel (test connection button)
- Notification trigger checkboxes: job started / phase complete / review needed / job failed / job delivered

### Tool Router Settings
Table matching `skills.json`: Capability | Tool ID | Tier | Cost per call | Active toggle | Notes
Toggle active/inactive without redeployment (writes to DB; tool router reads from DB at runtime).

### Drive Folder Management
Per venture: folder name | ID | Drive link | Re-verify button
Re-scan button: lists all folders under venture root and flags any missing from config.

### Environment
- Environment label (PRODUCTION / STAGING)
- Output directory path
- Mock flags status: IMAGE_GEN_MOCK, TRANSCRIPTION_MOCK, NOTIFICATIONS_ENABLED (display only)
- Railway service health: web URL, worker status

---

## 7. Job Detail (Generic — Cross-Venture)

Accessible from anywhere via `/jobs/{id}`.

**Top section:** Venture badge | Job ID | Status badge | Phase N of M | Created / Updated / Duration
**Error message** (if failed) with Retry button

**Phase timeline** (vertical):
Each phase: name | status icon | timestamps | cost | Drive outputs (links)
Active phase has a spinner.

**Actions bar (context-sensitive):**
- `review_pending` → **Approve** | **Reject** (prominent)
- `failed` → **Retry from checkpoint** | **Retry from start** | **Cancel**
- `completed` → **Download outputs** | **Duplicate job**
- Always: **View raw JSON** | **Cancel job**

---

## 8. API Endpoints Reference

| UI Action | Method | Endpoint |
|---|---|---|
| List all jobs | GET | `/api/jobs` |
| Get job detail | GET | `/api/jobs/{id}` |
| Approve job | POST | `/api/jobs/{id}/approve` |
| Reject job | POST | `/api/jobs/{id}/reject` |
| Retry job | POST | `/api/jobs/{id}/retry` |
| Cancel job | POST | `/api/jobs/{id}/cancel` |
| Trigger Etsy phase | POST | `/api/ventures/etsy/phase/{n}` |
| New audit order | POST | `/api/ventures/marketing-audit/orders` |
| New podcast order | POST | `/api/ventures/content-studio/orders` |
| Get Etsy listings | GET | `/api/ventures/etsy/listings` |
| Dashboard stats | GET | `/api/platform/dashboard` |
| Finance summary | GET | `/api/platform/finance` |
| Update API key | PUT | `/api/platform/settings/keys/{service}` |
| Test API key | POST | `/api/platform/settings/keys/{service}/test` |
| Toggle tool active | PUT | `/api/platform/settings/tools/{capability}/{tool_id}` |
| Health check | GET | `/api/health` |

---

## Critical Files (Migration Reference)

| File | Change Required |
|---|---|
| `src/aiplatform/webapp/` | Empty — needs main.py, routers, auth, schemas |
| `src/ventures/etsy/pipeline.py` | State persistence + Celery wrapping + approval gate refactor |
| `src/ventures/marketing_audit/pipeline.py` | Same + fix ai-marketing-claude sibling repo path |
| `src/ventures/content_studio/pipeline.py` | Same state + Celery + approval refactor |
| `src/aiplatform/skills/storage/_drive_auth.py` | Add service account materialization from env var on startup |
| `src/aiplatform/skills/finance/log_cost.py` | Implement stub → DB insert (15 lines) |
| `requirements.txt` | Uncomment: fastapi, uvicorn, celery, sqlalchemy, alembic, psycopg2, redis |
| `.ENV` | Reference only — contents migrate to Railway environment variables |
