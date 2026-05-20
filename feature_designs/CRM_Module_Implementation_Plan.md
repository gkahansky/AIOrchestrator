# Implementation Plan — CRM Module

**Parent Feature:** `AII-CRM` "Unified CRM Module"
**Roadmap ID:** `H-11`
**Venture label:** `platform`
**Spec:** `feature_designs/CRM_Module_Specification.md`
**Designer prompt:** `feature_designs/CRM_Module_Designer_Prompt.md`

Stories below are sized as **S** (≤1 day), **M** (2–3 days), **L** (4+ days). Each story is Jira-ready and carries the `roadmap_id` label `H-11`.

The sprint sequence is **strict** — Sprint N depends on Sprint N-1 landing. Within a sprint, stories can be parallelized except where called out.

---

## Sprint 1 — Foundation (DB + Ingestion)

Goal: schema in place, all writers go through `crm_ops.upsert_contact`, suppression gate moved into the skill. No new UI yet.

### S1.1 — Alembic migration: `crm_module` (M)

**File:** `alembic/versions/<hash>_crm_module.py` (new)

**Acceptance:**
- Adds columns to `contacts`: `lifecycle_stage`, `lifetime_value_cents`, `tags`, `owner_user`, `do_not_contact_until`, `gdpr_erasure_at`, `email_hash`, `primary_source`.
- Creates `crm_audit_log` table with all columns from spec §3.3 and indexes on `actor_user`, `contact_id`, `action`, `at`.
- Creates `crm_consent` table per spec §3.4 with unique composite `(contact_id, venture, channel, consent_type)`.
- Adds `Lead.contact_id` FK column.
- Backfill: populate `lifecycle_stage` from existing `status`; `email_hash` for all non-null emails; `lifetime_value_cents` from joined `RevenueEvent`; `primary_source` from outreach sends.
- Reversible (`downgrade` drops everything cleanly).

**Files touched:** new migration · `src/aiplatform/database/models.py` (model class extensions).
**Dependencies:** none.

### S1.2 — Extend `crm_ops.py` with core helpers (M)

**File:** `src/aiplatform/database/crm_ops.py`

**Acceptance:**
- `upsert_contact(email, usernames=None, lifecycle_stage=None, primary_source=None, venture=None, owner_user=None) -> Contact` — idempotent; merges usernames; updates `last_activity_at`; appends venture to `ventures_approached`; writes audit row.
- `recompute_stage(contact_id)` — runs the transition logic from spec §5.
- `can_send_outreach(email, venture, days=60) -> bool` — mirrors existing `can_send_sample`.
- `can_send_marketing(email, days=7) -> bool` — new.
- `validate_outbound_body(body: str, send_id: UUID) -> None` — raises if unsubscribe token missing.
- `add_revenue_to_contact(email, cents)` — increments LTV + advances stage when threshold hit.
- `merge_contacts(winner_id, loser_id, actor_user)` — moves all FKs to winner, archives loser to audit log.
- `log_audit(actor_user, contact_id, action, before, after, reason=None)` — single audit-write helper.
- Unit tests covering each helper.

**Files touched:** `crm_ops.py` · `tests/test_crm_ops.py` (new).
**Dependencies:** S1.1.

### S1.3 — Move suppression gate into `send_email.py` (S)

**File:** `src/aiplatform/skills/comms/send_email.py`

**Acceptance:**
- Before calling Resend, the skill looks up the recipient `Contact` (lowercased email) and returns `{error: "suppressed", reason: "..."}` if `do_not_contact_until > now()` OR `lifecycle_stage in (unsubscribed, erased)`.
- New required arg `consent_type` (`transactional` | `marketing` | `outreach`); for `marketing`, also checks `crm_consent` for an active grant.
- All existing callers updated to pass `consent_type` — fail-loud if missing.
- Existing worker.py suppression check is removed (now redundant).
- One regression test per consent_type.

**Files touched:** `send_email.py` · `worker.py` (remove redundant check) · all callers across ventures (~10 sites) · tests.
**Dependencies:** S1.2.

### S1.4 — Wire sample endpoints to upsert Contact (S)

**Files:** `src/aiplatform/webapp/routers/sample.py` (or wherever sample endpoints live).

**Acceptance:**
- Each of `POST /api/sample/podcast`, `/audit`, `/accessibility` calls `crm_ops.upsert_contact(email, lifecycle_stage="sample", primary_source=f"sample_{venture}", venture=venture)` before queuing the Job.
- If `ContactSuppressed` is raised, the endpoint returns 403 with operator-friendly message; Job is NOT queued.
- Manual test: hit each endpoint with a brand-new email → Contact row exists with correct stage and source.

**Files touched:** sample router · tests.
**Dependencies:** S1.2, S1.3.

### S1.5 — Wire venture order endpoints to upsert Contact (M)

**Files:** every venture's order router under `src/aiplatform/webapp/routers/`.

**Acceptance:**
- Marketing Audit, Security Audit, Content Studio, Content Repurposing, Market Research, Etsy phase 6 — each calls `crm_ops.upsert_contact(email, lifecycle_stage="customer", primary_source=f"order_{venture}", venture=venture)`.
- Cooldown enforcement: if `can_send_outreach()` returns False AND this is an outreach-followup order, block with operator-overrideable error.
- Each venture has at least one integration test covering the new ingestion path.

**Files touched:** ~6 venture routers · tests.
**Dependencies:** S1.2, S1.4 pattern.

### S1.6 — Outreach worker writes through crm_ops (S)

**File:** `src/aiplatform/worker.py` (outreach tasks `run_find_leads` + `run_send_approved_drafts`).

**Acceptance:**
- `run_find_leads` after qualifying a lead → calls `upsert_contact` with `lifecycle_stage="lead"`, `primary_source=f"outreach_{platform}"`, sets `Lead.contact_id`.
- `run_send_approved_drafts` no longer writes to `Contact` directly; calls `upsert_contact` + `log_contact_message` (existing helper).
- Existing behavior preserved (idempotency, dedup).

**Files touched:** `worker.py` · tests.
**Dependencies:** S1.2.

### S1.7 — Finance: revenue → LTV propagation (S)

**File:** `src/aiplatform/skills/finance/log_revenue.py`

**Acceptance:**
- After writing a `RevenueEvent`, calls `crm_ops.add_revenue_to_contact(email, cents)`.
- If no Contact exists for the email, it is created with `lifecycle_stage=customer`.
- Stage transitions `customer → repeat` validated by test.

**Files touched:** `log_revenue.py` · tests.
**Dependencies:** S1.2.

**Sprint 1 exit criteria:** all six ingestion paths populate the Contact table correctly; suppression gate works in `send_email.py`; full Alembic migration applied on staging.

---

## Sprint 2 — API

Goal: complete `/api/crm/*` surface from spec §7 and the Resend webhook.

### S2.1 — New router `crm.py` — read endpoints (M)

**File:** `src/aiplatform/webapp/routers/crm.py` (new)

**Acceptance:**
- `GET /api/crm/contacts` with filters, search, pagination per spec §7.
- `GET /api/crm/contacts/{id}` returns full record + counts.
- `GET /api/crm/contacts/{id}/timeline` aggregates events from Jobs, OutreachSends, ContactMessages, LeadDrafts, audit log notes — sorted desc.
- `GET /api/crm/stats` returns funnel counters.
- `GET /api/crm/audit` paginated audit log view.
- `GET /api/crm/consent/{contact_id}` lists active + revoked consent rows.
- All endpoints behind `Depends(require_user)`.
- OpenAPI schema validates.

**Files touched:** `crm.py` · `webapp/__init__.py` (mount router) · tests.
**Dependencies:** Sprint 1 complete.

### S2.2 — Router write endpoints + audit log middleware (M)

**File:** `src/aiplatform/webapp/routers/crm.py`

**Acceptance:**
- `POST`, `PATCH`, `POST /merge`, `POST /note`, `POST /suppress` — all call into `crm_ops` and produce exactly one `crm_audit_log` row per request.
- Manual contact add requires either email or at least one username (per existing `Contact` constraint).
- `actor_user` is read from JWT subject on every write.
- All endpoints return updated entity or 204.

**Files touched:** `crm.py` · tests.
**Dependencies:** S2.1.

### S2.3 — GDPR export + erase endpoints (M)

**File:** `src/aiplatform/webapp/routers/crm.py`

**Acceptance:**
- `POST /api/crm/contacts/{id}/export` collects rows from `contacts`, `leads`, `lead_drafts`, `outreach_sends`, `contact_messages`, `jobs`, `crm_audit_log`, `crm_consent` — returns one JSON bundle.
- Export action audit-logged (with `before=null`, `after={"row_counts": {...}}`).
- `POST /api/crm/contacts/{id}/erase` — sets `gdpr_erasure_at`, `lifecycle_stage=erased`, nulls PII per spec §6.4.
- Cascades: nulls PII fields on linked `leads`, `lead_drafts`, `contact_messages`, `outreach_sends`.
- Scrubs existing audit rows' `before`/`after` PII; replaces with `{"erased": true, "email_hash": "..."}`.
- Requires `confirm: true` in payload; rejects without.

**Files touched:** `crm.py` · `crm_ops.py` (gdpr_export, gdpr_erase helpers) · tests.
**Dependencies:** S2.2.

### S2.4 — Resend webhook handler (S)

**File:** `src/aiplatform/webapp/routers/webhooks.py` (new)

**Acceptance:**
- `POST /api/webhooks/resend` verifies signature against `RESEND_WEBHOOK_SECRET`.
- Handles `email.bounced` (hard only) → `do_not_contact_until=2099-01-01`, audit `bounce`.
- Handles `email.complained` → same as bounce + `lifecycle_stage=unsubscribed`, audit `complaint`.
- Handles `email.delivered|opened|clicked` → updates `OutreachSend` timestamps.
- Unsigned or unknown event-type requests → 400.
- Manual test with Resend CLI / curl payload included.

**Files touched:** `webhooks.py` · env: add `RESEND_WEBHOOK_SECRET` · tests.
**Dependencies:** S1.2.

### S2.5 — Extend existing unsubscribe handler (S)

**File:** `src/aiplatform/webapp/routers/outreach.py` (~L1040)

**Acceptance:**
- Existing `/api/outreach/unsubscribe/{send_id}` continues to work.
- On click also writes a `crm_consent` revoke row (across all ventures for that contact's email).
- Writes a `crm_audit_log` row with action `consent_revoke`.
- HTML confirmation page unchanged.

**Files touched:** `outreach.py` · tests.
**Dependencies:** S1.2.

### S2.6 — `validate_outbound_body` enforcement on draft approval (S)

**File:** `src/aiplatform/webapp/routers/outreach.py` (draft approval endpoint)

**Acceptance:**
- Approving a `lead_drafts` row runs `crm_ops.validate_outbound_body(body, draft.id)`.
- Missing unsubscribe token → 400 with clear error.
- Pre-existing approved drafts unaffected.

**Files touched:** `outreach.py` · tests.
**Dependencies:** S1.2.

### S2.7 — Celery beat: nightly stage recompute + dormant sweep (S)

**File:** `src/aiplatform/worker.py`

**Acceptance:**
- New `crm.purge_expired_leads` task — flips stage to `dormant` (lead/sample stages, no activity 180d) and triggers GDPR erase on stage in (lead, sample) with no activity 12m.
- New `crm.recompute_stages` task — reruns `recompute_stage` for all contacts touched in the last 24h.
- Both tasks scheduled in Celery beat config.

**Files touched:** `worker.py` · Celery beat config · tests (mock time).
**Dependencies:** S1.2.

**Sprint 2 exit criteria:** every endpoint in spec §7 returns correct data; Resend webhook configured in Resend dashboard; staging verification matrix items 4–8 pass.

---

## Sprint 3 — Frontend

Goal: build the page per `CRM_Module_Designer_Prompt.md`.

### S3.1 — Sidebar entry + route wiring (S)

**Files:** `frontend/src/components/Sidebar.tsx` · `frontend/src/App.tsx`

**Acceptance:**
- New nav item `{ label: "Customers", to: "/crm", icon: "groups" }` between Marketing and Finance.
- Routes `/crm` and `/crm/:contactId` mount `<CRM />`.

**Dependencies:** none (parallel with backend).

### S3.2 — Contacts tab (M)

**Files:** `frontend/src/pages/CRM.tsx` · `frontend/src/components/crm/ContactsTable.tsx`, `ContactsFilters.tsx`, `KpiStrip` (reuses existing `KpiCard`).

**Acceptance:**
- KPI strip + filter pills + search + bulk-select table per designer prompt.
- Uses react-query for data fetching with `staleTime: 60s`.
- Empty / loading / error states implemented.
- Mobile layout verified at 375px.

**Dependencies:** S2.1.

### S3.3 — Contact Detail (M)

**Files:** `frontend/src/components/crm/ContactDetailPanel.tsx`, `Timeline.tsx`, `ConsentPanel.tsx`.

**Acceptance:**
- Header card with stage badge, tags editor, action buttons (per designer prompt).
- Timeline shows all 12 event types with venture-color dots and links into Jobs / OutreachSends.
- Consent matrix (venture × channel) with grant/revoke modal.
- Free-text note input writes to audit log.
- Destructive actions show preview of audit row before confirm.

**Dependencies:** S2.2, S2.3.

### S3.4 — Compliance tab (M)

**Files:** `frontend/src/components/crm/ComplianceTab.tsx`, `SuppressionList.tsx`, `GdprQueue.tsx`, `AuditLogTable.tsx`.

**Acceptance:**
- Suppression list with `Lift` action (disabled for bounce/complaint reasons).
- GDPR queue with `Confirm Erase` requiring typed `ERASE {email}`.
- Audit log with filter row, expandable JSON diff per row, 100/page.
- Read-only — no edit/delete UI.

**Dependencies:** S2.3.

### S3.5 — Destructive-confirm dialog component (S)

**File:** `frontend/src/components/crm/DestructiveConfirmDialog.tsx`

**Acceptance:**
- Reusable component used by Suppress, Erase, Merge, Bulk-suppress, Lift-suppression.
- Shows plain-English explanation + audit row preview + typed/checkbox confirmation.
- Default-focused button is **Cancel**.
- Honors `prefers-reduced-motion`.

**Dependencies:** none (used by S3.3, S3.4).

**Sprint 3 exit criteria:** verification matrix items 1–3, 9, 10 pass via the UI on staging.

---

## Sprint 4 — Polish & Rollout

### S4.1 — Bulk operations (S)

**Files:** `frontend/src/components/crm/ContactsTable.tsx` (bulk action bar) · `src/aiplatform/webapp/routers/crm.py` (new bulk endpoints).

**Acceptance:**
- `POST /api/crm/contacts/bulk` with `{ ids: [...], action: tag|suppress|export }`.
- Cap of 50 ids enforced server-side; UI shows error past 50.
- Each affected contact gets its own audit log row.

**Dependencies:** S3.2.

### S4.2 — Funnel stats endpoint hardening (S)

**File:** `src/aiplatform/webapp/routers/crm.py` (extend `/api/crm/stats`)

**Acceptance:**
- Filters by venture, date range.
- Returns conversion funnel: `leads → samples → customers → repeat` counts + percentage retention.
- Aggregates LTV by venture.
- 5-minute Redis cache.

**Dependencies:** S2.1.

### S4.3 — End-to-end verification (M)

**File:** `tests/test_crm_e2e.py`

**Acceptance:**
- Executes all 12 verification items from spec §10 as Playwright + pytest integration tests.
- Runs in CI on PR.
- Documented in `feature_designs/CRM_Module_Specification.md` Appendix.

**Dependencies:** all prior sprints.

### S4.4 — Multi-user readiness audit (S)

**Files:** report only — `docs/crm_multiuser_readiness.md` (new)

**Acceptance:**
- Confirms `owner_user` populated on every Contact.
- Confirms all audit rows carry `actor_user`.
- Confirms `crm_consent.ip_address` + `user_agent` captured where applicable.
- Documents the exact schema delta required to switch on multi-user (no migration needed — only UI).
- File committed to repo.

**Dependencies:** all prior.

### S4.5 — Cut-over: deprecate legacy `/api/outreach/contacts` (S)

**File:** `src/aiplatform/webapp/routers/outreach.py`

**Acceptance:**
- Legacy `GET /api/outreach/contacts` returns a 301 → `/api/crm/contacts` with same query params.
- Marketing.tsx already-using-the-old-endpoint code paths verified to still work.
- Deprecation removal scheduled for one release later.

**Dependencies:** S2.1.

### S4.6 — Documentation + Confluence page (S)

**Acceptance:**
- `docs/crm.md` covers operator workflows (add contact, run export, run erase, lift suppression).
- Confluence page (via Jira MCP) summarizes the architecture and links to the spec.

**Dependencies:** all prior.

---

## Dependency Graph (high level)

```
   S1.1 ─┬─► S1.2 ─┬─► S1.3 ─► S1.4 ──► S1.5
         │         ├─► S1.6
         │         └─► S1.7
         │
         └─► S2.1 ─► S2.2 ─► S2.3
                            └─► S2.5
                            └─► S2.6
              S2.4 (parallel, needs S1.2)
              S2.7 (parallel, needs S1.2)

   Sprint 3 ► all depends on S2.1 + S2.2 + S2.3
   Sprint 4 ► depends on Sprint 3
```

## Effort Summary

| Sprint | Stories | Estimate |
|---|---|---|
| 1 — Foundation | 7 | ~10 dev-days |
| 2 — API | 7 | ~10 dev-days |
| 3 — Frontend | 5 | ~9 dev-days |
| 4 — Polish & Rollout | 6 | ~6 dev-days |
| **Total** | **25 stories** | **~35 dev-days** |

---

## Seeding into Jira

After this plan is committed, run:

```
python3 scripts/seed_jira_from_roadmap.py
```

The H-11 ROADMAP.md row will create the `AII-CRM` parent Feature. Story creation under it is done manually for v1 (this plan serves as the source) — once stable, automation can be extended to seed child stories from headed Markdown lists.

Status updates flow via `comms/sync_task_status.py` (4-way sync to Jira + ROADMAP.md + venture CLAUDE.md + session log) per the AII platform conventions in `src/aiplatform/CLAUDE.md`.
