# Platform System — Project Management Integration
## Claude Code Context File — Jira Integration

**Read `/CLAUDE_root.md` first for platform architecture rules.**
**This file governs the Jira integration that spans all ventures.**

---

## Purpose & Scope

Jira tracks **development and infrastructure work only**.

This means: sprint tasks, feature builds, system capabilities, venture setup, and testing.

**Not in scope:** day-to-day venture operations (listing pipelines, order queues, content publishing). Those remain in Google Drive metadata and the venture state machines.

---

## Tool Selection: Jira Cloud

Jira Cloud (project key: **AII**) is the project management tool for the AI-Infra platform.

- **Workspace:** `aiinfra.atlassian.net`
- **Project:** `AII` (AI Infrastructure)
- **Auth:** HTTP Basic — `JIRA_EMAIL:JIRA_API_KEY` (base64-encoded)
- **API:** Jira Cloud REST API v3 — `https://aiinfra.atlassian.net/rest/api/3`

---

## Issue Hierarchy

```
Feature  — top-level capability or venture milestone
  └── Story    — deliverable piece of functionality under a Feature
        └── Task     — internal breakdown under a Story
              └── Bug      — problem in the finished product
```

All active sprint work is tracked as **Stories** under the AII project. Each story maps to a ROADMAP.md entry via the `roadmap_id` label (e.g. `H-02`, `U-03`).

---

## Status Set (Jira Workflow)

| Jira Status   | Meaning                                            |
|---------------|----------------------------------------------------|
| `To Do`       | Captured / planned — not yet in progress           |
| `In Progress` | Actively being built                               |
| `In Review`   | In human review / testing                          |
| `Done`        | Shipped and verified                               |
| `Pending`     | On hold or blocked on external dependency          |

### Mapping to ROADMAP.md

| ROADMAP.md status | Jira status   |
|-------------------|---------------|
| `idea`            | `To Do`       |
| `planned`         | `To Do`       |
| `in-progress`     | `In Progress` |
| `done`            | `Done`        |
| `on-hold`         | `Pending`     |
| `blocked`         | `Pending`     |

---

## Labels (Custom Fields)

All issues carry a `roadmap_id` label (e.g. `AII-137`, `H-02`) to link back to ROADMAP.md.

| Field        | How set                                    |
|--------------|--------------------------------------------|
| `roadmap_id` | Label on the issue — e.g. `H-02`, `D-25`  |
| `venture`    | Label — e.g. `etsy`, `marketing_audit`     |
| `priority`   | Jira native priority field                 |

---

## Project Backlog

See ROADMAP.md for the canonical backlog. Jira is kept in sync via `scripts/seed_jira_from_roadmap.py` (ROADMAP.md → Jira, idempotent) and `scripts/sync_jira_to_roadmap.py` (Jira status → ROADMAP.md, post-sprint).

**Jira is the status source of truth after initial seeding.**

---

## The Skill: `comms/update_jira_board.py`

This is the **only** file that calls the Jira API. All pipeline and script code routes through this skill.

```python
def create_issue(
    project_key: str,
    summary: str,
    issue_type: str,          # "Story" | "Task" | "Bug" | "Feature"
    description: str | None,
    labels: list[str] | None,  # includes roadmap_id label
    priority: str | None,
    parent_key: str | None,    # link to a Feature
) -> dict:
    """
    Capability: project-board-write
    Creates a new issue in the specified Jira project.
    Returns {issue_key, url, status}
    """

def update_issue_status(
    issue_key: str,
    status: str,               # "In Progress" | "Done" | "Pending" etc.
    comment: str | None = None
) -> dict:
    """
    Capability: project-board-write
    Transitions the issue to a new status. Optionally posts a comment.
    Returns {issue_key, status, updated_at}
    """

def add_comment(
    issue_key: str,
    comment: str,
) -> dict:
    """
    Capability: project-board-write
    Posts a comment on an issue.
    Returns {comment_id}
    """

def get_issue(
    issue_key: str,
) -> dict:
    """
    Capability: project-board-read
    Returns full issue detail by key (e.g. AII-42).
    Returns {issue_key, summary, status, labels, url}
    """

def search_issues(
    project_key: str,
    jql_extra: str | None = None,
) -> list[dict]:
    """
    Capability: project-board-read
    Returns issues matching a JQL query.
    Returns [{issue_key, summary, status, labels, url}]
    """

def find_issue_by_label(
    project_key: str,
    label: str,
) -> dict | None:
    """
    Capability: project-board-read
    Finds an issue whose labels include the given value (e.g. roadmap_id).
    Returns None if not found.
    """
```

### Jira API Basics

- **Base URL:** `https://aiinfra.atlassian.net/rest/api/3`
- **Auth:** HTTP Basic — `base64(JIRA_EMAIL:JIRA_API_KEY)` in `Authorization` header
- **Rate limit (free tier):** ~1 req/s — log a warning when throttled
- **Key endpoints:**
  - `POST /issue` — create issue
  - `PUT /issue/{key}` — update fields
  - `POST /issue/{key}/transitions` — change status
  - `POST /issue/{key}/comment` — add comment
  - `GET /issue/{key}` — single issue
  - `GET /search?jql=...` — JQL search

### Error Handling

If a Jira API call fails:
1. Log the error with full response body
2. **Do not halt the caller** — board sync is observability, not a gate
3. Call `comms/send_slack.py` with the failure to `#platform-alerts`
4. Retry once after 5 seconds before alerting

---

## Sync Scripts

Two scripts keep Jira and ROADMAP.md in sync. Both live in `/scripts/`.

---

### `scripts/seed_jira_from_roadmap.py`

**Direction:** ROADMAP.md → Jira (one-time seed + idempotent re-run)

**When to run:** Once after initial setup. Re-runnable — skips issues that already exist (matched by `roadmap_id` label).

```
Usage:
  python3 scripts/seed_jira_from_roadmap.py
  python3 scripts/seed_jira_from_roadmap.py --dry-run   # Preview without creating
```

**Logic:**
1. Parse every item in ROADMAP.md (all priority sections + Done table)
2. For each item, determine the issue type and set labels
3. Check if an issue with label `roadmap_id={item_id}` already exists in AII
4. If not: create the issue with summary, description, status, and labels
5. If yes: skip (do not overwrite — Jira is the live source after seeding)
6. Print summary: `{N} created, {M} skipped (already exist)`

---

### `scripts/sync_jira_to_roadmap.py` *(if built)*

**Direction:** Jira → ROADMAP.md (ongoing sync)

**When to run:** Weekly, or manually after a sprint review.

**Conflict rule:** Jira is the source of truth for status after initial seeding.

---

## 4-Way Sync: `comms/sync_task_status.py`

The skill `comms/sync_task_status.py` is the **primary sync mechanism** used by all scripts and pipelines. On every status change it updates:

1. **Jira** — transitions the issue + posts a comment
2. **ROADMAP.md** — updates the status column for the matching row
3. **Venture CLAUDE.md** — upserts the `## Pipeline Status` managed table
4. **Session log** — appends an entry to `logs/session_{date}.md`
5. **Git push** — when status = `done`, stages and pushes to `origin/main`

Failed sync steps are queued in `logs/pending_updates.json` and retried via `scripts/retry_pending_updates.py`.

---

## Registering the Skill

In `/platform/registry/skills.json`:

```json
{
  "project-board-write": {
    "capability": "project-board-write",
    "tools": [
      {
        "id": "jira",
        "tier": "standard",
        "cost_per_call": 0,
        "module": "platform.skills.comms.update_jira_board",
        "active": true,
        "note": "Jira Cloud REST API v3 — AII project. Dev tracking only."
      }
    ]
  },
  "project-board-read": {
    "capability": "project-board-read",
    "tools": [
      {
        "id": "jira",
        "tier": "standard",
        "cost_per_call": 0,
        "module": "platform.skills.comms.update_jira_board",
        "active": true
      }
    ]
  }
}
```

---

## Environment Variables

```
JIRA_API_KEY=<Jira Cloud API token>
JIRA_DOMAIN=https://aiinfra.atlassian.net
JIRA_EMAIL=gkahansky@gmail.com
```

---

## Architecture Constraints

- **`update_jira_board.py` is a platform skill** — it knows nothing about any venture. It receives typed inputs and returns typed outputs.
- **Never store operational data in Jira** — no listing slugs, no order IDs, no assets, no Drive links for day-to-day ops. Dev tasks only.
- **Never block on board sync** — Jira API failures are logged and alerted, never raised as pipeline exceptions.
- **Jira is the status source of truth post-seeding** — `sync_jira_to_roadmap.py` flows Jira → ROADMAP.md, not the reverse.
- **ROADMAP.md remains the idea intake point** — all new items are added to ROADMAP.md first, then seeded to Jira on next seed run. Never create Jira issues without a corresponding ROADMAP.md entry.

---

## Current Status

**Sprint 1 — Complete**
- [x] Jira project `AII` created at `aiinfra.atlassian.net`
- [x] `comms/update_jira_board.py` skill built (create/update/read issues)
- [x] `comms/sync_task_status.py` — 4-way sync (Jira + ROADMAP.md + venture CLAUDE.md + session log) on every status change; auto git push on done
- [x] `scripts/seed_jira_from_roadmap.py` — ROADMAP.md → Jira issues (idempotent)
- [x] API token in `.env` as `JIRA_API_KEY`

**Next:** Run weekly `sync_jira_to_roadmap.py` after sprint reviews.

## Pipeline Status
<!-- managed by update_task.py -->

| Roadmap ID | Task | Status | Note | Updated |
|---|---|---|---|---|
| U-03 | Project Management Integration | ✅ done | Jira workspace live. 4-way sync built: update_task.py keeps Jira, ROADMAP.md, venture CLAUDE.m... | 2026-03-27 |
| H-08 | Gig Generator — Fiverr | ✅ done | Finished mapping Fiverr exact metadata and UI generator constraints, audio limits in content_studio,... | 2026-04-06 |
| H-09 | Management App | ✅ done | FastAPI + React webapp live at planBadmin.com. Railway backend + Cloudflare Pages frontend. Google OAuth. PostgreSQL job state. | 2026-03-31 |
| H-05 | Human Review Gate | ✅ done | /api/jobs/{id}/approve + /api/jobs/{id}/reject endpoints live. Review queue in dashboard UI. | 2026-03-31 |
| M-09 | Dashboard Endpoint | ✅ done | GET /api/platform/dashboard live. Covered by H-09 Management App. | 2026-03-31 |
| D-15 | Database Foundation | ✅ done | SQLAlchemy models + Alembic migrations. job_ops.py upsert. | 2026-03-29 |
| D-16 | Etsy Pipeline Phases 1–6 | ✅ done | Full auto-chain Phase 2→3→4→6 live. Phase 5 gate removed. Etsy drafts created via API. | 2026-04-03 |
| D-17 | Marketing Audit Multi-Page Crawler | ✅ done | BFS crawler in analyze_page.py — 20 pages, sitemap seeding, merges findings. | 2026-04-05 |
| D-18 | Public Sample Endpoints | ✅ done | POST /api/sample/podcast + /api/sample/audit — rate-limited, demo mode, email delivery. | 2026-04-05 |
| D-19 | Pipeline + Email Fixes | ✅ done | Drive upload before review gate; delivery email recipient fallback; Drive link fallback chain; openai in requirements. | 2026-04-05 |
| D-20 | Drive Auth Unified — OAuth Token (AII-137) | ✅ done | create_gdoc.py and drive_organise.py were hardcoded to service account; unified to get_drive_service() from _drive_auth.py. Eliminates storageQuotaExceeded. | 2026-04-05 |
| D-21 | Podcast Order Form — File Upload + Full Fields (AII-138) | ✅ done | Audio file upload replaces URL. Full form fields: email, show, episode, host, guest, instructions. Delivery email + Google Doc sharing fixed. | 2026-04-05 |
| D-22 | Cold Outreach Pipeline | ✅ done | Lead discovery (7 channels), A/B email composition, human review gate, Resend send, open-tracking, A/B analysis. Admin UI in Marketing page. | 2026-04-08 |
| D-23 | Advisory Board Activation | ✅ done | Real claude-sonnet-4-6 API calls in run_advisor.py. Fixed pm→product ID mismatch, removed duplicate worker defs, architect webhook live. | 2026-04-09 |
| D-24 | Strategy Room — Roadmap Tab | ✅ done | Backlog + WIP sections, drag-drop reorder, recently done, feature dropdown, roadmap_features table, status enum→varchar migration. | 2026-04-09 |
| D-25 | Strategy Room Redesign | ✅ done | Architectural Curator design. Agent cards with skills, proposals per agent, prompt editor, chat (up to 5 sessions), manual triggers. New /chat and /trigger endpoints. | 2026-04-09 |
