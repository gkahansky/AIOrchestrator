# AI Business Platform
## Claude Code Context File — Platform Level

**Read this entire file before writing any code or making any changes.**
**This is the authoritative platform context. It applies to every venture.**
**Also read the venture-specific CLAUDE.md in the active venture directory before touching any venture code.**

---

## What This Platform Is

**Platform:** AI-Infra (Jira project key: AII)

A reusable, multi-agent AI platform powering independent business ventures under two brands:

- **MiroPrintStudio** — Etsy digital image shop (AI-generated wall art)
- **EchoForge** (echoforge.biz) — Marketing & SEO services (Marketing Audit + Podcast Notes + Security Audit + Market Research)

The core principle is that agents, skills, memory, and integrations live in a shared infrastructure layer. Each venture is a lightweight configuration and pipeline on top of that shared layer.

- **Venture A:** MiroPrintStudio — Etsy digital image shop — see `/ventures/etsy/CLAUDE.md`
- **Venture B:** EchoForge — Podcast Show Notes (Service A) + Content Repurposing Pack (Service B: audio/video → blog + captions + newsletter, human-reviewed) — see `/ventures/content_studio/CLAUDE.md`
- **Venture C:** EchoForge — Website marketing audit — see `/ventures/marketing_audit/CLAUDE.md`
- **Venture D:** EchoForge — Web application security audit — see `/ventures/security_audit/CLAUDE.md`
- **Venture E:** Plan B AI — Market Research (multi-LLM research committee) — see `/ventures/market_research/CLAUDE.md`
- **Venture F:** EchoForge — Content Repurposing (unified clips + thumbnails + text — merged Service B+C) — see `/ventures/content_repurposing/CLAUDE.md`
- **Venture G+:** Future ventures — each gets its own directory and CLAUDE.md

### Venture B — Content Studio: Architecture Notes

The Content Studio venture runs two services on the same pipeline:

**Service A — Podcast Show Notes:** audio file → Whisper transcription → Claude content generation (show notes, timestamps, transcript, social captions, SEO metadata) → Google Doc + PDF → human review gate → delivery email.

**Service B — Content Repurposing Pack:** audio OR video file → FFmpeg audio extraction (if video) → Whisper → Claude core generation → three extended output skills run sequentially: `generate_blog_post.py`, `generate_caption_pack.py`, `generate_newsletter_draft.py` → Google Doc → **forced human review** (never auto-approved, human review is the product differentiator) → delivery email with output checklist.

Service B adds components not shared with other ventures (do not move to `/platform/skills/` unless truly venture-agnostic):
- `nixpacks.toml` `ffmpeg` package (video audio extraction)
- Service B tier config (`REPURPOSING_TIERS`) in `config.py`
- Service B prompt builder in `prompts.py`
- Phase 2b extended output orchestration in `pipeline.py`

### Venture F — Content Repurposing: Architecture Notes

Content Repurposing is the unified replacement for the original text-only Service B and the planned video Service C. The operator uploads a video file directly via planBadmin (multipart upload → Drive). The pipeline produces portrait 9:16 short clips with smart crop, word-pop burned captions, Pillow-composed thumbnails, and text artifacts (show notes, blog, newsletter, captions) gated by plan tier.

**Two-phase pipeline with chapter review gate:**
- Phase 1 (`cr.run_job`): download → transcribe (Whisper) → generate chapters (Claude) → `chapter_review` pause. If `clip_instructions` is set on the order, Claude pre-selects matching chapters automatically.
- Admin reviews chapters in planBadmin, selects which to clip from (or proceeds with full episode).
- Phase 2 (`cr.resume_job`): score virality → filter clips to selected chapters → per-clip OpenCV face detection → smart portrait transcode → word-pop captions → thumbnail → text artifacts → `review_pending`.

It adds these components not shared with other ventures (do not move to `/platform/skills/`):
- `ventures/content_repurposing/clip_selector.py` — virality threshold filter + overlap dedup + chapter-range filtering
- `ventures/content_repurposing/config.py` — unified `PLANS` dict; `CAPTION_STYLE_TYPE` env var
- `CRJob` and `CRClipAsset` SQLAlchemy models (migrations `a2b3c4d5e6f7` + `b3c4d5e6f7a8`)
- `cr.run_job` + `cr.resume_job` Celery tasks (soft_time_limit=3600 each)
- FastAPI router at `/api/ventures/content-repurposing/` (includes `/chapters/approve` endpoint)

All media processing skills (including `detect_crop_region`, `generate_chapters`, `burn_captions` word-pop style, `transcode_video` crop_x param) are venture-agnostic and live in `/aiplatform/skills/media/`.

**Key constraints:** human review is required at two gates — chapter selection (`chapter_review`) and final delivery approval (`review_pending`). Neither auto-approves.

### Venture D — Security Audit: Architecture Notes

The Security Audit venture shares the following platform components with existing ventures:
- Celery + Redis orchestration, FastAPI job API, PostgreSQL findings schema, Playwright browser automation, Claude API correlation pipeline, PDF generation, Google Drive artifact storage

It adds components not shared with any other venture (do not move these to `/platform/skills/`):
- Docker container images per scanning phase (isolated per job, destroyed on completion)
- `nuclei` template management and update pipeline
- Rate-limit proxy wrapper (prevent inadvertent DoS during active scanning phases)
- Scope validation middleware (ensures tools cannot probe out-of-scope hosts — **legally required**)
- PoC screenshot capture and evidence tagging system
- MinIO/S3 artifact storage for raw scan output (screenshots, request/response logs)

**Key constraint:** every active scanning phase (Phases 2–5) must validate target ownership before running. See Section 10 of the venture CLAUDE.md for legal/compliance requirements. Never bypass scope validation even in testing.

### Venture E — Market Research: Architecture Notes

The Market Research venture shares all platform components with existing ventures (Celery, FastAPI, PostgreSQL, Playwright PDF, Drive upload, email delivery). It adds:
- `aiplatform/skills/research/multi_llm_research.py` — parallel async LLM execution (Claude, OpenAI, Gemini, Grok); `max_tokens` param configurable per call
- `aiplatform/skills/research/rag_store.py` — Qdrant-backed RAG for pre-uploaded documents; supports PDF, DOCX, XLSX, PPTX, TXT, CSV
- `ventures/market_research/config.py` — `SECTION_LIBRARY` (8 modules + Final Synthesis), `CROSS_MODULE_SYSTEM_PROMPT`, section critic/summary prompts, legacy V1/V2 prompts
- `aiplatform/skills/media/render_markdown.py` — Markdown → styled HTML converter; alignment-aware table parsing (`<thead>/<tbody>`); visual marker injection (`[SCREENSHOT:]` / `[GENERATE IMAGE:]` → `<figure>`); citation superscripts. Venture-agnostic.
- `aiplatform/skills/media/capture_visual.py` — `screenshot_url()` (Playwright headless) + `generate_chart()` (Gemini Imagen 4:3 business charts). Resolves visual markers to base64 data URIs at PDF build time. Venture-agnostic.

**V3 Section-Based Pipeline (default for new sessions):** User selects from a fixed section library (8 research modules + Final Synthesis). Each section is researched independently by all selected LLMs in parallel, Level-1 merged, then put through a 2-round author/critic loop. The critic checks: (a) all required items present, (b) every quantitative claim has an inline citation `[Source: Name, Year]`. After 2 failed rounds a disclaimer is appended. Completed sections contribute a 2-sentence reference summary to all subsequent sections. Final assembly is Python concatenation + citations appendix. Section-level status is visible in the UI and resumes on retry.

**V2 Agentic Pipeline (backwards compat):** Topics are decomposed into 3-4 Work Packages. Each package runs all selected LLMs in parallel (8192 token budget), results are Level-1 merged, missing sections are filled via a completeness gate, and carry-forward context prevents repetition. Final report is assembled via Python concatenation + focused Executive Summary call. Package results persist after each package completes, enabling resumability on retry.

**V1 (backwards compat — rerun mode):** Pre-set per-LLM prompts → parallel research → single merge → critic. Used for Adjust & Rerun on legacy sessions.

Gig Generator also supports all four EchoForge services. All gig configs live in `scripts/run_gig_generator.py`. Voice is always "We/Our" (team/agency) — "I" only in the Fiverr title (platform requirement).

### Cold Outreach Platform — Architecture Notes

The Cold Outreach system is a **platform-level feature** (not a venture). It is available to all ventures via the Marketing tab in planBadmin. The system replaces A/B template blasting with AI-driven, persona-aware lead discovery and per-lead personalized message composition.

**Data model — key tables:**

| Table | Purpose |
|---|---|
| `outreach_campaigns` | One per venture, holds personas (JSONB), target_prompt, schedule config, platform |
| `campaign_sources` | One-to-many per campaign — each row is a search source with its own platform, keywords (JSONB), and config (JSONB) |
| `leads` | Raw qualified leads; `context` (Text) stores the original post/query for message grounding; `matched_persona` links to the campaign persona |
| `lead_drafts` | AI-written drafts per lead; status flow: `pending_review → approved / rejected → sent` |
| `outreach_sends` | Send records (Resend); linked from `lead_drafts.send_record_id` |
| `contacts` | CRM — upserted on send; tracks all contacts across ventures |

**Source handler registry** — `src/aiplatform/skills/research/sources/`:

| Handler | Platform | Method |
|---|---|---|
| `reddit.py` | Reddit | Public JSON API — no key; configurable `subreddits`, `sort`, `time_filter` |
| `google.py` | Google | SerpAPI — `SERPAPI_KEY`; shared `serpapi_search()` utility |
| `linkedin.py` | LinkedIn | Apify `linkedin-post-search-scraper` primary; Google `site:linkedin.com` fallback |
| `facebook.py` | Facebook Groups | Apify `facebook-groups-scraper` primary; Google `site:facebook.com/groups` fallback; `group_urls` config |
| `hackernews.py` | Hacker News | Algolia HN API — no key; `post_type: ask/show/story` config |
| `indiehackers.py` | IndieHackers | Google `site:indiehackers.com` via SerpAPI |
| `fiverr.py` | Fiverr | Session cookie scrape; Google fallback |
| `listennotes.py` | Listen Notes | Listen Notes REST API — `LISTENNOTES_API_KEY`; bypasses Claude qualification (already structured) |

`HANDLERS` dict in `sources/__init__.py` is the extension point — adding a new platform means adding one handler file and one entry in the dict. No changes to core logic.

**VENTURE_DEFAULT_SOURCES** in `find_leads.py` seeds source rows when a new campaign is created (via the API) and acts as fallback when no `CampaignSource` rows exist. Currently defined for `marketing_audit`, `content_studio`, and `accessibility_audit`.

**Two-stage AI pipeline:**

1. **Qualification** (`find_leads.py` → `_qualify_post`) — Claude Haiku evaluates each raw post against the campaign's `search_prompt` and `personas`. Returns `is_lead`, `confidence`, `matched_persona`, `notes`. Skipped for Listen Notes (pre-structured).
2. **Composition** (`compose_personalized.py` → `compose_for_lead`) — Claude Sonnet 4.6 writes a unique outreach message grounded in the lead's specific post (`context` field). `_PLATFORM_RULES` dict enforces platform-appropriate tone/format/length. Returns `{subject, message_body, context_used}`.

**Celery tasks in `worker.py`:**

| Task | Trigger | What it does |
|---|---|---|
| `run_find_leads(campaign_id, ...)` | Manual (UI) or Beat scheduler | Searches all active `CampaignSource` rows, qualifies via Claude Haiku, inserts Lead records |
| `run_compose_pending(campaign_id)` | Manual (UI) or chained after `run_find_leads` | Composes a `LeadDraft` for every `new` lead without an existing pending draft |
| `run_send_approved_drafts(campaign_id)` | Manual (UI) | Sends all `approved` drafts; enforces spam guard (30-day cooldown + unsubscribe check); upserts Contacts |
| `run_scheduled_searches()` | Celery Beat every 30 min | Finds campaigns with `auto_search_enabled=True` and `next_search_at ≤ now`; fires `run_find_leads` + `run_compose_pending`; advances `next_search_at` |

**Human review gate:** drafts start as `pending_review`. The operator approves (optionally editing subject/body), rejects, or bulk-approves from the Drafts tab. `run_send_approved_drafts` only processes `approved` status. No auto-send path exists.

**API router** — `src/aiplatform/webapp/routers/outreach.py`:

```
GET/POST   /api/outreach/campaigns
GET/PATCH  /api/outreach/campaigns/{id}
PATCH      /api/outreach/campaigns/{id}/schedule
POST       /api/outreach/campaigns/{id}/find-leads
POST       /api/outreach/campaigns/{id}/compose-pending
POST       /api/outreach/campaigns/{id}/compose-lead/{lead_id}
POST       /api/outreach/campaigns/{id}/send-approved
GET/POST   /api/outreach/campaigns/{id}/sources
PATCH/DEL  /api/outreach/sources/{id}
GET        /api/outreach/campaigns/{id}/drafts   ?status=pending_review|approved|rejected
PATCH      /api/outreach/drafts/{id}
GET        /api/outreach/campaigns/{id}/leads
GET        /api/outreach/campaigns/{id}/stats
GET        /api/outreach/contacts
```

Legacy A/B endpoints (`/compose`, `/send`, `/templates`, `/sends`) are preserved for backwards compatibility.

**Environment variables required:**

```
ANTHROPIC_API_KEY     — Haiku (qualification) + Sonnet (composition)
SERPAPI_KEY           — Google / LinkedIn / IndieHackers / Fiverr signal searches
APIFY_API_TOKEN       — LinkedIn Posts Scraper + Facebook Groups Scraper (optional; graceful fallback)
LISTENNOTES_API_KEY   — Listen Notes podcast discovery (optional)
FIVERR_SESSION_COOKIE — Fiverr buyer requests scrape (optional; Google fallback)
RESEND_API_KEY        — Email sending
```

Adding a new venture means writing a config, a pipeline, and a CLAUDE.md. It does not mean touching `/platform/`.

---

## ⚠️ Critical Architecture Rules — Read Before Writing Any Code

This platform is **not a monolith**. Skills are reusable and venture-agnostic. Pipelines are venture-specific and thin. Violating this creates refactoring debt that blocks every future venture.

### The two-layer model

**Skills** live in `/platform/skills/` — atomic, reusable functions that know nothing about any venture:
- They take typed inputs and return typed outputs
- They have no side effects beyond their stated purpose
- They never reference any venture name internally (no Etsy, no venture B, nothing)
- They never call other skills — composition happens in the pipeline
- They never write to Drive directly — that is the pipeline's job
- They never read from environment variables directly — credentials are injected by the caller

**Pipelines** live in `/ventures/{name}/` — thin orchestration that chains skills together:
- They import from `/platform/skills/` and their own `/ventures/{name}/config.py` only
- They handle Drive paths, status updates, and phase flow
- They contain the venture-specific business logic
- They should be short (~150 lines max) — if longer, extract to a skill

### The dependency direction is one-way

```
/ventures/{name}/pipeline.py   →   imports from   →   /platform/skills/
```

**Never the reverse.** A skill file must never import from `/ventures/`.
**Never cross-venture.** Nothing in `/ventures/etsy/` may import from `/ventures/other/`.

### The split test

Before writing any function, ask: *"Would a different venture (a content studio, a SaaS tool, a print shop) want this?"*
- **Yes** → it belongs in `/platform/skills/`
- **No, it's specific to one venture** → it belongs in `/ventures/{name}/`

### Common violations to avoid

| Wrong | Right |
|---|---|
| `def generate_and_save_image(prompt, etsy_slug)` | `generate_image(prompt)` in skill + `drive_write(path, img)` called by pipeline |
| `def research_etsy_keywords(theme)` with Etsy API logic inside a skill | `web_search(query)` skill + venture-specific query building in pipeline |
| `import ventures.etsy.config` inside a skill file | Skills never import venture config |
| One `etsy_agent.py` file that does all 7 phases | `pipeline.py` calls individual skill functions per phase |
| A function that both calls an API and writes to Drive | Two separate skills composed by the pipeline |

---

## Repository Structure

**Note:** `platform/` and `ventures/` live under `src/` to avoid shadowing Python's stdlib `platform` module.
Scripts add `src/` to `sys.path` explicitly. Pytest uses `conftest.py` for the same.

```
/src/
  platform/
    skills/
      research/
        web_search.py           # Generic web search — any venture
        trend_analysis.py       # Score and rank topics by demand — any venture
        competitor_scan.py      # Crawl competitor data — any venture
      media/
        generate_image.py       # Tool Router lives here (DALL-E / Gemini / MJ)
        resize_image.py         # Pillow wrapper — any aspect ratio
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
        generate_accessibility_report.py # Playwright HTML-to-PDF reports
    registry/
      skills.json               # Skill catalogue: capability tags, tools, costs
      tool_router.py            # Selects tool based on tier, budget, availability

  ventures/
    etsy/
      pipeline.py               # Orchestrates skills for the 7-phase Etsy flow
      config.py                 # Etsy API settings, Drive paths, price rules
      prompts.py                # Etsy-specific agent system prompts
      CLAUDE.md                 # Etsy venture context — read when working on Etsy
    {next_venture}/             # Future venture — same structure, new pipeline
      pipeline.py
      config.py
      CLAUDE.md

/scripts/                       # One-off setup and maintenance scripts
/tests/
  test_skills/                  # Unit tests for each skill in isolation
  test_pipeline/                # Integration tests per venture pipeline
```

---

## Platform Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| LLM | Claude API — Sonnet 4 | All agent intelligence |
| Orchestration | LangGraph | Added in Sprint 6 — not yet built |
| Image gen (active) | DALL-E 3 | Active primary while Gemini billing is pending |
| Image gen (next) | Gemini Imagen 3 | Pending Google billing approval — flip active=true in skills.json |
| Image processing | Pillow (Python) | Resize to any required aspect ratios |
| Storage | Google Drive API | All media, metadata, audit logs |
| Backend hosting | Railway | FastAPI backend + Celery worker |
| Frontend hosting | Cloudflare Pages | React + Vite admin app at planBadmin.com. Source: `frontend/` |
| Database | PostgreSQL (Railway plugin) | Job state, phase events, cost/revenue events. Alembic migrations |
| Job queue | Celery + Redis | Async pipeline execution; Redis Cloud as broker |
| Auth | Google OAuth + PyJWT | Google Identity Services login; 24h JWT sessions |
| Session memory | Redis Cloud | Pub/sub + short-term state |
| Long-term memory | Qdrant Cloud | Research history, brand guidelines — namespaced per venture |
| Observability | LangSmith | Agent tracing and cost tracking |
| API layer | FastAPI | HTTP wrapper around agents. Source: `src/aiplatform/webapp/` |

Venture-specific tools (Etsy API, Pinterest, Buffer, Placeit, etc.) are listed in the relevant venture CLAUDE.md.

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

**To add a new tool:** add a new entry to the tools array and set `active: true`. No other code changes required.
**To disable a tool:** set `active: false`. The Tool Router automatically routes to the next option.
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

## Web Management App

The platform has a live web admin at **planBadmin.com**.

| Layer | Details |
|---|---|
| Frontend | React + Vite, hosted on Cloudflare Pages. Source: `frontend/` |
| Backend | FastAPI, hosted on Railway. Source: `src/aiplatform/webapp/` |
| Auth | Google OAuth — only the `ALLOWED_EMAIL` account can log in |
| Domain | Frontend: `planBadmin.com` → Cloudflare Pages. API: `api.planBadmin.com` → Railway |

Key env vars required on Railway: `GOOGLE_CLIENT_ID`, `ALLOWED_EMAIL`, `JWT_SECRET`, `CORS_ORIGINS`, `DATABASE_URL`, `ANTHROPIC_API_KEY`.
Key env vars required on Cloudflare Pages: `VITE_API_URL=https://api.planBadmin.com`.

---

## Agent Design

Agents are task-based (not tool-based). Each agent owns a capability domain and decides which tools to use. Tool selection is delegated to the Tool Router.

| Agent | Capability domain | Ventures |
|---|---|---|
| Research | Web search, trend analysis, competitor scan | All |
| Executor | Image generation, Drive file ops, API calls, packaging | All |
| Comms | Email, Slack, social copy, notifications | All |
| Code gen | Script generation, PDF/ZIP assembly | All |
| QA | Compliance checks, SEO quality review | All |
| Finance | Cost/revenue tracking, ROAS review, budget alerts | All |

Venture-specific agent configuration (system prompts, tool subsets) lives in `/ventures/{name}/prompts.py`.

---

## Platform-Level Constraints

- **Never put venture-specific logic inside `/platform/skills/`** — skills must be venture-agnostic
- **Never import from `/ventures/` inside a skill file** — dependency direction is one-way
- **Never import from one venture into another** — ventures are isolated from each other
- **Never write a function that both calls an API and writes to Drive** — two separate skills composed by the pipeline
- **Never add a new agent for each new tool** — register it as a skill, let the Tool Router handle selection
- **`.env` and `google_credentials.json` must never be committed to git** — `.gitignore` blocks both

---

## Claude Code Instructions

When working on this platform, always:

1. Read this file first. Then read the venture-specific CLAUDE.md for the venture you are working on.
2. Before writing any function, apply the split test: skill or pipeline?
3. When adding a new tool integration, add it to `skills.json` and implement it as a new tool option in the existing skill file. Do not create a new skill file per tool.
4. When asked to build a feature, first ask: does this belong in a skill (reusable, venture-agnostic) or a pipeline (venture-specific orchestration)?
5. Never reference a venture name inside a skill file. If you catch yourself doing this, stop and split the function.
6. The CLAUDE.md in the repo root and in the active venture directory are the authoritative context files. Read both before making changes.

---

## DevLog

A file `DevLog.md` exists at the repo root. **After every commit, append a new row to the DevLog table:**

| Column | Content |
|---|---|
| Date & Time | ISO 8601 local time, e.g. `2026-04-05 14:32` |
| Jira Key | AII-XXX if this commit relates to a Jira issue; leave empty otherwise |
| Commit ID | First 7 chars of the commit SHA |
| Description | Why the change was needed and what it does (one sentence) |

Format (append to the table in DevLog.md):

```
| 2026-04-05 14:32 | AII-137 | f076dc4 | Fixed Drive auth — create_gdoc and drive_organise now use OAuth token instead of service account |
```

Do not rewrite existing rows. Only append.
