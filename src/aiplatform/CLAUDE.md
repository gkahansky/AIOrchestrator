# Platform System — Project Management Integration
## Claude Code Context File — ClickUp Integration

**Read `/CLAUDE_root.md` first for platform architecture rules.**
**This file governs the ClickUp integration that spans all ventures.**

---

## Purpose & Scope

ClickUp tracks **development and infrastructure work only**.

This means: sprint tasks, feature builds, system capabilities, venture setup, and testing.

**Not in scope (revisit later):** day-to-day venture operations (listing pipelines, order queues, content publishing). Those remain in Google Drive metadata and the venture state machines.

---

## Tool Selection: ClickUp (Free Forever)

### Why ClickUp

| Criterion | ClickUp Free | Jira Free | Asana Free | Monday Free |
|---|---|---|---|---|
| User limit | Unlimited | 10 | 10 | 2 |
| Projects | Unlimited | Unlimited | Unlimited | Unlimited |
| REST API | ✅ 100 req/min | ✅ | ✅ rate-limited | ✅ |
| Custom statuses | ✅ | ✅ | ❌ | ❌ |
| Storage cap | 100MB* | 2GB | 100MB | 500MB |
| Built-in automations | 100/month | 300/month | limited | limited |

*Irrelevant — we store no files in ClickUp. All assets live in Google Drive.

**Deciding factors:** Unlimited users and projects on the free tier (Asana and Jira cap at 10 users); custom statuses available without paying; REST API fully accessible on free; 100 automations/month limit doesn't matter because our automation routes through the skill API, not ClickUp's built-in automations.

---

## Workspace Structure

```
Workspace: AI Infra
├── Space: 🔧 Platform         # Shared infrastructure + Management Console tasks (see note)
├── Space: 🛍️ Etsy             # Venture A dev & testing
├── Space: 🔍 Marketing Audit  # Venture dev & testing
├── Space: 🎙️ Podcast Notes    # Venture dev & testing
└── Space: 📹 Content Channels # Venture dev & testing
```

> **Note — 5-space free-tier limit:** ClickUp Free is capped at 5 spaces. The planned
> Management Console space could not be created. Items H-09 and M-09 (Management App,
> Dashboard Endpoint) are assigned to the **Platform** space with `venture=Management Console`
> in their custom field. If the workspace is upgraded, create the 6th space and migrate those tasks.

Each Space has one List named `Tasks`. All work items live in that list, differentiated by status and custom fields. No sub-lists needed until volume justifies it.

---

## Status Set (Shared Across All Spaces)

All Spaces use the same status set. Development tasks have a single lifecycle.

| Status | Colour | Meaning |
|---|---|---|
| `Backlog` | Grey | Captured idea — not yet scoped or scheduled |
| `Planned` | Light Blue | Scoped, scheduled for an upcoming sprint |
| `In Progress` | Yellow | Actively being built |
| `Review` | Blue | In human review / testing |
| `Ready For Deployment` | Blue | Ready to be depoloyed to production |
| `Done` | Green | Shipped and verified |
| `On Hold` | Orange | Blocked on external dependency (API key, approval, etc.) |
| `Blocked` | Red | Blocked on internal dependency — note blocker in task |

### Mapping to ROADMAP.md

| ROADMAP.md status | ClickUp status |
|---|---|
| `idea` | `Backlog` |
| `planned` | `Planned` |
| `in-progress` | `In Progress` |
| `done` | `Done` |
| `on-hold` | `On Hold` |

---

## Custom Fields (Applied to All Tasks)

| Field | Type | Values |
|---|---|---|
| `roadmap_id` | Text | e.g. `U-03`, `H-02`, `L-06` — links task to ROADMAP.md row |
| `type` | Dropdown | `Venture` / `System` |
| `priority` | Dropdown | `Urgent` / `High` / `Medium` / `Low` |
| `venture` | Dropdown | `Platform` / `Etsy` / `Marketing Audit` / `Podcast Notes` / `Content Channels` / `Management Console` |
| `blocked_by` | Text | External dependency description (e.g. "Awaiting Etsy API key") |

---

## Project Backlog

This is the seed data for `scripts/seed_clickup_from_roadmap.py`. Every item below becomes a ClickUp task on first run. Items already marked `done` are created in Done status for historical context.

### Space: 🔧 Platform

| Roadmap ID | Task Name | Priority | Status | Notes |
|---|---|---|---|---|
| U-03 | Project Management Integration | Urgent | In Progress | This item — ClickUp setup + skill build |
| H-03 | Upwork Order Listener — Podcast | High | Planned | `marketplace/upwork_listener.py` |
| H-04 | Upwork Order Listener — Marketing Audit | High | Planned | `marketplace/audit_order_listener.py` |
| H-05 | Human Review Gate | High | Planned | FastAPI `/orders/{id}/approve`, email + Slack alert |
| H-08 | Gig Generator — Fiverr | High | Planned | `marketplace/generate_fiverr_gig.py` |
| H-10 | Promotion Agent | High | Planned | `comms/promote_venture.py` |
| M-07 | Fiverr Order Listener — Podcast | Medium | Planned | `marketplace/fiverr_listener.py` |
| M-08 | Fiverr Order Listener — Marketing Audit | Medium | Planned | `marketplace/audit_fiverr_listener.py` |
| M-13 | Financial Tracker | Medium | Planned | `/finances` FastAPI endpoint, P&L per venture |
| M-14 | Content Creation Agent | Medium | Planned | `media/generate_svg_asset.py`, brand collateral |
| M-16 | Lead Generation System | Medium | Planned | `research/find_leads.py`, `media/generate_offer_sheet.py` |
| L-07 | Auto-Approve System | Low | Planned | Per-venture AUTO_APPROVE flag after 20 validated orders |
| L-08 | LangGraph Orchestration | Low | Backlog | Only when pipeline complexity justifies (>5 phases) |
| L-09 | Redis Pub/Sub for Inter-Agent Events | Low | Backlog | Event-driven architecture at scale |
| L-10 | Qdrant Long-Term Memory | Low | Backlog | Cross-session context, per-venture namespacing |
| L-11 | AI Sales Team Integration | Low | Backlog | Evaluate `zubair-trabzada/ai-sales-team-claude` |
| L-12 | Outreach Automation | Low | Backlog | Upwork InMail / LinkedIn DM pipeline |
| H-07 | Gemini Imagen 4 Integration | High | Done | Standard-tier image tool live, DALL-E 3 fallback |
| D-01 | EchoForge Landing Page | — | Done | echoforge.biz live on Cloudflare Pages |
| D-02 | Brand Identity & Logo System | — | Done | Terracotta palette, wordmark, favicon |
| D-03 | Platform CLAUDE.md Hierarchy | — | Done | Root + venture-level context files |
| D-11 | Gemini Mockups — Consistent Artwork | — | Done | `gemini-2.5-flash-image` mockup pipeline |

### Space: 🛍️ Etsy

| Roadmap ID | Task Name | Priority | Status | Notes |
|---|---|---|---|---|
| L-06 | Etsy Shop — Sprint 1: Foundations | Low | On Hold | Blocked: Etsy API key pending approval |

### Space: 🔍 Marketing Audit

| Roadmap ID | Task Name | Priority | Status | Notes |
|---|---|---|---|---|
| U-02 | Marketing Audit Pipeline — Sprint 1 | Urgent | Done | Manual trigger live-tested against echoforge.biz |
| H-02 | Marketing Audit — Sprint 2: PDF Polish | High | In Progress | Branding, score gauges, `audit_deliver.py` |
| M-02 | Marketing Audit — Sprint 3: Upwork Integration | Medium | Planned | Order detection + automated delivery |
| M-10 | Marketing Audit — Sample Cold Outreach | Medium | Planned | 3 sample audits + personalised prospect snippets |

### Space: 🎙️ Podcast Notes

| Roadmap ID | Task Name | Priority | Status | Notes |
|---|---|---|---|---|
| U-01 | Core Podcast Pipeline — Sprint 1 & 2 | Urgent | Done | Audio → transcript → content → PDF |
| H-06 | Podcast Sample Generator | High | Done | `--demo` mode + `--pdf-only` flag |
| H-01 | Podcast Pipeline — Sprint 3: Upwork Delivery | High | Planned | OAuth2 token, polling, contract message delivery |
| M-03 | Podcast Add-on: Brand Voice Guide | Medium | Done | `generate_brand_voice.py`, cached JSON per client |
| M-04 | Podcast Add-on: Episode Promotional Copy | Medium | Done | `generate_promo_copy.py` |
| M-05 | Podcast Add-on: 30-Day Social Calendar | Medium | Planned | `generate_social_calendar.py` |
| M-06 | Podcast Add-on: Listener Email Sequence | Medium | Planned | `generate_email_sequence.py` |
| M-11 | Podcast Add-on: Guest Outreach Templates | Medium | Planned | `generate_guest_outreach.py` |
| M-12 | Podcast Add-on: Show Landing Page Audit | Medium | Planned | `market-landing/SKILL.md` with podcast prefix |
| L-01 | Podcast Pipeline — Sprint 5: Freelancer.com | Low | Planned | `freelancersdk`, webhook on `project.awarded` |
| L-02 | Podcast Add-on: Competitive Show Analysis | Low | Backlog | `market-competitors/SKILL.md` |
| L-03 | Podcast Add-on: Launch Playbook | Low | Backlog | `market-launch/SKILL.md`, 8-week plan |
| D-10 | Podcast Pipeline Sprints 1 & 2 | — | Done | Manual trigger, demo mode, watermarked sample PDF |

### Space: 📹 Content Channels

| Roadmap ID | Task Name | Priority | Status | Notes |
|---|---|---|---|---|
| L-05 | Content Channels — Venture B Setup | Low | Backlog | First channel: Project Post-Mortem. Needs Veo/Runway, ElevenLabs, TikTok + Instagram API approvals |

### Space: 🖥️ Management Console

| Roadmap ID | Task Name | Priority | Status | Notes |
|---|---|---|---|---|
| H-09 | Management App | High | Done | FastAPI + React webapp live at planBadmin.com. Railway + Vercel. Google OAuth. PostgreSQL job state. |
| M-09 | Dashboard Endpoint | Medium | Done | GET /api/platform/dashboard live. Covered by H-09 Management App. |

---

## The Skill: `comms/update_project_board.py`

This is the **only** file that calls the ClickUp API. All pipeline and script code routes through this skill.

```python
def create_task(
    list_id: str,
    name: str,
    status: str,
    description: str | None,
    custom_fields: dict | None,  # {roadmap_id, type, priority, venture, blocked_by}
    api_key: str
) -> dict:
    """
    Capability: project-board-write
    Creates a new task in the specified ClickUp list.
    Returns {task_id, url, status}
    """

def update_task_status(
    task_id: str,
    status: str,
    api_key: str,
    comment: str | None = None
) -> dict:
    """
    Capability: project-board-write
    Updates task status. Optionally posts a comment on the change.
    Returns {task_id, status, updated_at}
    """

def add_task_comment(
    task_id: str,
    comment: str,
    api_key: str
) -> dict:
    """
    Capability: project-board-write
    Posts a comment on a task (e.g. blocker detail, PR link, test result).
    Returns {comment_id}
    """

def get_tasks_by_status(
    list_id: str,
    status: str,
    api_key: str
) -> list[dict]:
    """
    Capability: project-board-read
    Returns all tasks in a list filtered by status.
    Returns [{task_id, name, status, custom_fields, url}]
    """

def get_task(
    task_id: str,
    api_key: str
) -> dict:
    """
    Capability: project-board-read
    Returns full task detail by ID, including custom fields.
    Returns {task_id, name, status, custom_fields, url}
    """

def get_all_tasks(
    list_id: str,
    api_key: str
) -> list[dict]:
    """
    Capability: project-board-read
    Returns all tasks in a list regardless of status.
    Used by sync_clickup_to_roadmap.py.
    Returns [{task_id, name, status, custom_fields}]
    """
```

### ClickUp API Basics

- **Base URL:** `https://api.clickup.com/api/v2`
- **Auth header:** `Authorization: {CLICKUP_API_KEY}` (no "Bearer" prefix)
- **Rate limit (free tier):** 100 req/min — log a warning at 80
- **Key endpoints:**
  - `POST /list/{list_id}/task` — create task
  - `PUT /task/{task_id}` — update status, name, description
  - `POST /task/{task_id}/comment` — add comment
  - `GET /list/{list_id}/task?statuses[]={status}` — filtered task list
  - `GET /list/{list_id}/task` — all tasks in list
  - `GET /task/{task_id}` — single task

### Error Handling

If a ClickUp API call fails:
1. Log the error with full response body
2. **Do not halt the caller** — board sync is observability, not a gate
3. Call `comms/send_slack.py` with the failure to `#platform-alerts`
4. Retry once after 5 seconds before alerting

---

## Sync Scripts

Two scripts handle keeping ClickUp and ROADMAP.md in sync. Both live in `/scripts/`.

---

### `scripts/seed_clickup_from_roadmap.py`

**Direction:** ROADMAP.md → ClickUp (one-time seed + idempotent re-run)

**When to run:** Once after ClickUp workspace is set up. Re-runnable — skips tasks that already exist (matched by `roadmap_id` custom field).

```
Usage:
  python3 scripts/seed_clickup_from_roadmap.py
  python3 scripts/seed_clickup_from_roadmap.py --dry-run   # Preview without creating
```

**Logic:**
1. Parse every item in ROADMAP.md (all priority sections + Done table)
2. For each item, determine the target Space using the assignment rules below
3. Check if a task with `roadmap_id = {item_id}` already exists in that Space's list
4. If not: create the task with name, description, status, and all custom fields
5. If yes: skip (do not overwrite — ClickUp is the live source after seeding)
6. Print summary: `{N} created, {M} skipped (already exist)`

**Space assignment rules (first match wins):**

| Condition | Space |
|---|---|
| Item ID is H-09 or M-09, or description references `dashboard` or `management app` | Management Console |
| `type = System` | Platform |
| Description references `etsy` or `CLAUDE_etsy.md` | Etsy |
| Description references `marketing_audit` | Marketing Audit |
| Description references `podcast_notes` or `content_studio` | Podcast Notes |
| Description references `content_channels` | Content Channels |
| No match | Platform (default) |

**Status mapping (ROADMAP → ClickUp):**

| ROADMAP status | ClickUp status |
|---|---|
| `idea` | `Backlog` |
| `planned` | `Planned` |
| `in-progress` | `In Progress` |
| `done` | `Done` |
| `on-hold` | `On Hold` |

---

### `scripts/sync_clickup_to_roadmap.py`

**Direction:** ClickUp → ROADMAP.md (ongoing sync)

**When to run:** Weekly, or manually after a sprint review. Updates ROADMAP.md to reflect current ClickUp task statuses.

```
Usage:
  python3 scripts/sync_clickup_to_roadmap.py
  python3 scripts/sync_clickup_to_roadmap.py --dry-run      # Show diffs without writing
  python3 scripts/sync_clickup_to_roadmap.py --roadmap-wins  # Override: ROADMAP.md wins on conflict
```

**Logic:**
1. For each Space, call `get_all_tasks(list_id)` to retrieve current statuses
2. For each task with a `roadmap_id` custom field:
   a. Map ClickUp status → ROADMAP.md status (see table below)
   b. Find the row in ROADMAP.md where `# = {roadmap_id}`
   c. If the status column differs, update it
3. Items moved to `Done` in ClickUp:
   - Remove from their current priority table in ROADMAP.md
   - Add a row to the ✅ Done table with today's date and a one-line note
4. Write the updated ROADMAP.md to disk
5. Print summary: `{N} statuses updated, {M} items moved to Done, {K} unchanged`

**Conflict rule:** ClickUp is the source of truth for status after initial seeding. To override from ROADMAP.md, use `--roadmap-wins` flag (use with caution — intended for recovery only).

**Status mapping (ClickUp → ROADMAP):**

| ClickUp status | ROADMAP.md status |
|---|---|
| `Backlog` | `idea` |
| `Planned` | `planned` |
| `In Progress` | `in-progress` |
| `Review` | `in-progress` |
| `Done` | `done` |
| `On Hold` | `on-hold` |
| `Blocked` | `planned` + append blocker note to description |

---

## Setup Steps (One-Time Manual Steps)

These cannot be automated. Complete before running any scripts.

### Step 1 — Create ClickUp Account
Sign up at https://clickup.com (free, no credit card). Create a Workspace named `AI Infra`.

### Step 2 — Create Spaces
Create 6 Spaces with these exact names:
- `Platform`
- `Etsy`
- `Marketing Audit`
- `Podcast Notes`
- `Content Channels`
- `Management Console`

### Step 3 — Create Lists
Inside each Space, create one List named `Tasks`.

### Step 4 — Configure Status Set
All Spaces share the same status set. For each Space:
- Go to Space Settings → Statuses
- Replace all defaults with: `Backlog`, `Planned`, `In Progress`, `Review`, `Done`, `On Hold`, `Blocked`
- Assign colours as defined in the Status Set table above

### Step 5 — Create Custom Fields
In each Space, add these custom fields to the Tasks list:
- `roadmap_id` — Text field
- `type` — Dropdown: `Venture`, `System`
- `priority` — Dropdown: `Urgent`, `High`, `Medium`, `Low`
- `venture` — Dropdown: `Platform`, `Etsy`, `Marketing Audit`, `Podcast Notes`, `Content Channels`, `Management Console`
- `blocked_by` — Text field

### Step 6 — Note List IDs
For each List, open it in ClickUp. The List ID is in the URL:
`https://app.clickup.com/{workspace}/v/li/{LIST_ID}`
Copy all 6 IDs into `.env`.

### Step 7 — Generate API Token
Settings → Apps → API Token → Generate → copy to `.env`.

### Step 8 — Populate `.env`

```
# ClickUp
CLICKUP_API_KEY=pk_xxxxxxxxxxxxxxxx
CLICKUP_LIST_PLATFORM=
CLICKUP_LIST_ETSY=
CLICKUP_LIST_MARKETING_AUDIT=
CLICKUP_LIST_PODCAST_NOTES=
CLICKUP_LIST_CONTENT_CHANNELS=
CLICKUP_LIST_MANAGEMENT_CONSOLE=
```

### Step 9 — Seed the Backlog
Once setup is complete and `.env` is populated:
```
python3 scripts/seed_clickup_from_roadmap.py --dry-run   # verify first
python3 scripts/seed_clickup_from_roadmap.py             # create all tasks
```

---

## Registering the Skill

Add to `/platform/registry/skills.json`:

```json
{
  "project-board-write": {
    "capability": "project-board-write",
    "tools": [
      {
        "id": "clickup",
        "tier": "standard",
        "cost_per_call": 0,
        "module": "platform.skills.comms.update_project_board",
        "active": true,
        "note": "ClickUp REST API — free tier, 100 req/min. Dev tracking only."
      }
    ]
  },
  "project-board-read": {
    "capability": "project-board-read",
    "tools": [
      {
        "id": "clickup",
        "tier": "standard",
        "cost_per_call": 0,
        "module": "platform.skills.comms.update_project_board",
        "active": true
      }
    ]
  }
}
```

---

## Architecture Constraints

- **`update_project_board.py` is a platform skill** — it knows nothing about any venture. It receives typed inputs and returns typed outputs.
- **Never store operational data in ClickUp** — no listing slugs, no order IDs, no assets, no Drive links for day-to-day ops. Dev tasks only.
- **Never block on board sync** — ClickUp API failures are logged and alerted, never raised as pipeline exceptions.
- **ClickUp is the status source of truth post-seeding** — `sync_clickup_to_roadmap.py` flows ClickUp → ROADMAP.md, not the reverse.
- **ROADMAP.md remains the idea intake point** — all new items are added to ROADMAP.md first, then seeded to ClickUp on next seed run. Never create ClickUp tasks without a corresponding ROADMAP.md entry.

---

## Sprint Roadmap

| Sprint | Duration | Goal | Status |
|---|---|---|---|
| **Sprint 1 — Skill + Manual Setup** | 1 week | Complete Steps 1–8 (manual ClickUp setup). Build `comms/update_project_board.py` — all 6 functions, unit tests with mock API responses. Manual end-to-end test: create task → update status → add comment → retrieve by status. | Planned |
| **Sprint 2 — Seed + Sync Scripts** | 1 week | Build `seed_clickup_from_roadmap.py`. Parse ROADMAP.md, assign to spaces, create all tasks. Verify full backlog visible in ClickUp. Build `sync_clickup_to_roadmap.py`. Test round-trip: change status in ClickUp → run sync → confirm ROADMAP.md updated. | Planned |

---

## Current Status

**Sprint 1 — Complete (2026-03-26)**

- [x] ClickUp workspace `AI Infra` created
- [x] 5 Spaces created (free-tier limit; Management Console → Platform)
- [x] `Tasks` list in each Space
- [x] Shared status set configured via `setup_clickup_workspace.py`
- [x] 5 custom fields on each list (roadmap_id, type, venture, blocked_by)
- [x] All list IDs added to `.env`
- [x] API token in `.env` as `CLICKUP_API_KEY`
- [x] `comms/update_project_board.py` skill built

**Sprint 2 — Complete (2026-03-26)**

- [x] `scripts/setup_clickup_workspace.py` — one-time workspace configuration
- [x] `scripts/seed_clickup_from_roadmap.py` — ROADMAP.md → ClickUp tasks
- [x] `scripts/sync_clickup_to_roadmap.py` — ClickUp status → ROADMAP.md

**Next:** Run weekly `sync_clickup_to_roadmap.py` after sprint reviews.

## Pipeline Status
<!-- managed by update_task.py -->

| Roadmap ID | Task | Status | Note | Updated |
|---|---|---|---|---|
| U-03 | Project Management Integration | ✅ done | ClickUp workspace live. 4-way sync built: update_task.py keeps ClickUp, ROADMAP.md, venture CLAUDE.m... | 2026-03-27 |
| H-08 | Gig Generator — Fiverr | 🔄 in-progress | Fiverr gig generator skill complete. run_gig_generator.py CLI ready for podcast_notes and marketing_... | 2026-03-28 |
| H-09 | Management App | ✅ done | FastAPI + React webapp live at planBadmin.com. Railway backend + Vercel frontend. Google OAuth. PostgreSQL job state. | 2026-03-31 |
| H-05 | Human Review Gate | ✅ done | /api/jobs/{id}/approve + /api/jobs/{id}/reject endpoints live. Review queue in dashboard UI. | 2026-03-31 |
| M-09 | Dashboard Endpoint | ✅ done | GET /api/platform/dashboard live. Covered by H-09 Management App. | 2026-03-31 |
| D-15 | Database Foundation | ✅ done | SQLAlchemy models + Alembic migrations. job_ops.py upsert. | 2026-03-29 |
| D-16 | Etsy Pipeline Phases 1–6 | ✅ done | Full auto-chain Phase 2→3→4→6 live. Phase 5 gate removed. Etsy drafts created via API. | 2026-04-03 |
| D-17 | Marketing Audit Multi-Page Crawler | ✅ done | BFS crawler in analyze_page.py — 20 pages, sitemap seeding, merges findings. | 2026-04-05 |
| D-18 | Public Sample Endpoints | ✅ done | POST /api/sample/podcast + /api/sample/audit — rate-limited, demo mode, email delivery. | 2026-04-05 |
| D-19 | Pipeline + Email Fixes | ✅ done | Drive upload before review gate; delivery email recipient fallback; Drive link fallback chain; openai in requirements. | 2026-04-05 |
| D-20 | Drive Auth Unified — OAuth Token (AII-137) | ✅ done | create_gdoc.py and drive_organise.py were hardcoded to service account; unified to get_drive_service() from _drive_auth.py. Eliminates storageQuotaExceeded. | 2026-04-05 |
| D-21 | Podcast Order Form — File Upload + Full Fields (AII-138) | ✅ done | Audio file upload replaces URL. Full form fields: email, show, episode, host, guest, instructions. Delivery email + Google Doc sharing fixed. | 2026-04-05 |
