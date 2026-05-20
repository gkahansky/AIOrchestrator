# Technical Specification: CRM Module — Unified Customer & Lead Management

**Status:** Planned · **Roadmap ID:** H-11 · **Owner Feature:** AII-CRM · **Venture label:** `platform`

---

## 1. Overview

### 1.1 Problem

The platform currently captures leads and customers in several disconnected places:

- Cold outreach (10 source handlers under `src/aiplatform/skills/research/sources/`) writes to `leads`, `lead_drafts`, `outreach_sends`.
- Sample order endpoints on echoforge.biz (`POST /api/sample/podcast`, `/audit`, `/accessibility`) write `Job` rows whose `input_data.email` is the only customer identifier.
- Six venture order intakes (Marketing Audit, Content Studio, Content Repurposing, Etsy, Security Audit, Market Research) write `Job` rows with `input_data.client_email`.
- The `contacts` table is partially populated by the outreach worker only.

There is no single place to view, track, and manage a person's journey from first touch (lead, sample, inbound inquiry) through paid order and post-sale follow-up. The Marketing module covers outreach discovery; it is not a CRM.

### 1.2 Goal

A new **CRM module** at `/crm` in planBadmin that unifies all customer and lead activity across ventures, with hard compliance guardrails. The module is the source of truth for:

- Who a person is (name, email, social handles, company)
- Where they came from (outreach source, sample order, paid order, inbound)
- What stage of the lifecycle they are in (lead → sample → customer → repeat → dormant)
- What we have sent them, what they have opened/replied to, what they have bought
- What consent we hold, what cooldowns apply, and what we are allowed to send next

### 1.3 Non-Goals (v1)

- Replacement for the Marketing module (lead discovery + draft review stays there)
- Owning the send infrastructure — Resend integration in `send_email.py` is unchanged in shape
- Bidirectional email inbox sync (no IMAP/Gmail polling for replies in v1)
- Full marketing automation engine (drip sequences, conditional flows)
- Subscription / recurring billing
- Multi-user RBAC UI (single-user gate via `ALLOWED_EMAIL` JWT remains; the data model is designed to support roles later)
- Encryption of PII at rest (noted as a known gap; tracked separately)

---

## 2. Architecture

### 2.1 Design Principles

CRM is a **thin aggregator** over data that already exists. It does not duplicate any model that lives in another router; it reads from `contacts`, `leads`, `lead_drafts`, `outreach_sends`, `contact_messages`, `jobs`, and the new audit / consent tables, and presents one unified view.

### 2.2 Layering

```
            ┌──────────────────────────────────────────────────────┐
            │  Frontend  /crm  →  React (Contacts / Detail /       │
            │                       Compliance)                    │
            └─────────────────────────┬────────────────────────────┘
                                      │  HTTPS + JWT
            ┌─────────────────────────▼────────────────────────────┐
            │  src/aiplatform/webapp/routers/crm.py                │
            │  GET/POST/PATCH endpoints; calls into crm_ops only   │
            └─────────────────────────┬────────────────────────────┘
                                      │
            ┌─────────────────────────▼────────────────────────────┐
            │  src/aiplatform/database/crm_ops.py  (extended)      │
            │  upsert / merge / cooldown / consent / audit helpers │
            └─────────────────────────┬────────────────────────────┘
                                      │
            ┌─────────────────────────▼────────────────────────────┐
            │  models.py: Contact, ContactMessage, Lead,           │
            │            LeadDraft, OutreachSend, Job              │
            │            + new: CrmAuditLog, CrmConsent            │
            └──────────────────────────────────────────────────────┘
```

Every ingestion path (sample endpoints, venture order routers, outreach worker) writes through `crm_ops.upsert_contact()` — never directly to `Contact`. This keeps lifecycle transitions, cooldowns, and audit log writes in one place.

### 2.3 File Layout

| Concern | File |
|---|---|
| API router | `src/aiplatform/webapp/routers/crm.py` (new) |
| DB helpers | `src/aiplatform/database/crm_ops.py` (extend) |
| Models | `src/aiplatform/database/models.py` (extend + 2 new tables) |
| Migration | `alembic/versions/<hash>_crm_module.py` (new) |
| Suppression skill gate | `src/aiplatform/skills/comms/send_email.py` (extend) |
| Resend webhook | `src/aiplatform/webapp/routers/webhooks.py` (new) |
| Frontend page | `frontend/src/pages/CRM.tsx` (new) |
| Frontend shared | `frontend/src/components/crm/` (new) |
| Sidebar | `frontend/src/components/Sidebar.tsx` (add entry) |
| Routing | `frontend/src/App.tsx` (add route) |

---

## 3. Data Model

### 3.1 Existing tables (used as-is)

- `Job` — order/sample work; join key is `input_data.client_email` or `input_data.email`
- `Lead` — outreach prospects
- `LeadDraft` — per-lead AI-composed messages
- `OutreachSend` — Resend delivery log for outreach
- `ContactMessage` — Resend log for any email sent to a Contact
- `OutreachCampaign`, `CampaignSource` — campaign config (read-only for CRM)

### 3.2 `contacts` — new columns

```python
class Contact(Base):
    # ... existing columns ...

    # Replaces `status` over time. Backfilled in migration.
    # Values: lead | sample | customer | repeat | dormant | unsubscribed | erased
    lifecycle_stage    = Column(String(20), nullable=False, default="lead", index=True)

    # Sum of revenue events linked via Job rows for this contact (cents, USD).
    lifetime_value_cents = Column(Integer, nullable=False, default=0)

    # Free-form tags, e.g. ["vip", "podcast-host", "wants-newsletter"]
    tags               = Column(JSONB, nullable=False, default=list)

    # Reserved for future multi-user. Today: always ALLOWED_EMAIL.
    owner_user         = Column(String(255), nullable=True)

    # Hard suppression with date. Set to far-future on bounce/complaint.
    do_not_contact_until = Column(DateTime(timezone=True), nullable=True, index=True)

    # GDPR right-to-erasure timestamp. When set: PII nulled, email_hash retained.
    gdpr_erasure_at    = Column(DateTime(timezone=True), nullable=True)

    # SHA-256 of lowercased email. Used post-erasure to block re-ingest.
    email_hash         = Column(String(64), nullable=True, index=True)

    # Original source channel (highest-weight if multi-source).
    primary_source     = Column(String(50), nullable=True, index=True)
```

`status` is kept and mirrored from `lifecycle_stage` for backwards compatibility with the Marketing module until that module migrates.

### 3.3 `crm_audit_log` — new table

Every CRM write that touches PII or compliance state writes one row.

```python
class CrmAuditLog(Base):
    __tablename__ = "crm_audit_log"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user  = Column(String(255), nullable=False, index=True)  # ALLOWED_EMAIL today
    contact_id  = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"),
                         nullable=True, index=True)
    # Values: status_change | edit | merge | note | suppress | export | erase | bounce |
    #         complaint | consent_grant | consent_revoke | webhook_in
    action      = Column(String(50), nullable=False, index=True)
    before      = Column(JSONB, nullable=True)
    after       = Column(JSONB, nullable=True)
    reason      = Column(Text, nullable=True)   # human note or webhook payload
    at          = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc), index=True)
```

After GDPR erasure the row is retained but `before`/`after` PII fields are scrubbed and replaced with `{"erased": true, "email_hash": "..."}`.

### 3.4 `crm_consent` — new table

Per-venture, per-channel granular consent ledger (GDPR Art. 6/7).

```python
class CrmConsent(Base):
    __tablename__ = "crm_consent"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id    = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    venture       = Column(String(50), nullable=False, index=True)
    channel       = Column(String(20), nullable=False)  # email | sms | platform_dm
    # Values: transactional | marketing | outreach
    consent_type  = Column(String(20), nullable=False)
    # Values: explicit | implicit | legitimate_interest | revoked
    lawful_basis  = Column(String(30), nullable=False)
    source        = Column(String(100), nullable=True)  # "order_form", "outreach_reply", "manual"
    granted_at    = Column(DateTime(timezone=True), nullable=True)
    revoked_at    = Column(DateTime(timezone=True), nullable=True)
    ip_address    = Column(String(64), nullable=True)
    user_agent    = Column(String(500), nullable=True)
```

Composite unique on `(contact_id, venture, channel, consent_type)` — one active row per combo. Revocation never deletes; it sets `revoked_at`.

### 3.5 Migration plan

Single Alembic migration `crm_module`:
1. Add new columns to `contacts` with sensible defaults (no nulls).
2. Create `crm_audit_log` and `crm_consent` tables with indexes.
3. Backfill `lifecycle_stage` from existing `status` via a one-time `UPDATE`:
   - `approached` → `lead`
   - `inquired` → `sample` (when joined to a sample Job) else `lead`
   - `purchased` → `customer`
   - `unsubscribed` → `unsubscribed`
4. Backfill `email_hash` for all rows with non-null email.
5. Backfill `lifetime_value_cents` from `RevenueEvent` joined via `Job.input_data.client_email`.
6. Backfill `primary_source`: outreach contacts → their first `OutreachSend.campaign.platform`; others → `"sample_<venture>"` or `"order_<venture>"`.

Migration is idempotent and reversible.

---

## 4. Cross-System Ingestion

Every system that has a "first contact" today must call `crm_ops.upsert_contact()` instead of writing to `Contact` directly. The helper performs:

1. Lookup by `email` (lowercased) OR by any matching `usernames[platform]` value.
2. If found: merge — union usernames, append `ventures_approached` if new, update `last_activity_at`, log a `CrmAuditLog` row with action `edit` or `status_change`.
3. If not found: insert with `lifecycle_stage` computed from the call site.
4. Run cooldown check: if `do_not_contact_until > now` raise `ContactSuppressed` exception (callers handle gracefully — no send happens but the contact record is still updated).

### 4.1 Ingestion writers

| Caller | When | `lifecycle_stage` set | Source flag |
|---|---|---|---|
| `POST /api/sample/podcast` | On submit, before queueing Job | `sample` | `sample_podcast` |
| `POST /api/sample/audit` | On submit | `sample` | `sample_marketing_audit` |
| `POST /api/sample/accessibility` | On submit | `sample` | `sample_accessibility` |
| `POST /api/ventures/marketing-audit/orders` | On submit | `customer` | `order_marketing_audit` |
| `POST /api/ventures/security-audit/orders` | On submit | `customer` | `order_security_audit` |
| `POST /api/ventures/content-studio/orders` | On submit | `customer` | `order_content_studio` |
| `POST /api/ventures/content-repurposing/...` | On submit | `customer` | `order_content_repurposing` |
| `POST /api/ventures/market-research/` | On submit | `customer` | `order_market_research` |
| Etsy phase 6 (order intake) | When buyer email present | `customer` | `order_etsy` |
| Outreach worker `_qualify_post` → save_lead | After Claude qualifies a lead | `lead` | `outreach_<platform>` |
| Outreach worker `run_send_approved_drafts` | After Resend send | unchanged (already a lead) | n/a; logs `ContactMessage` |
| Manual "Add Contact" in CRM UI | Always | operator-selected | `manual` |
| `POST /api/webhooks/resend` (bounce/complaint) | On Resend webhook | unchanged | n/a; sets `do_not_contact_until` |

### 4.2 Lead → Contact promotion

A `Lead` is never the same row as a `Contact`. When the first non-empty `lead.email` is observed (during qualification or first send), the worker calls `crm_ops.upsert_contact()` with `email=lead.email`, `usernames={lead.source_channel: lead.platform_username}`, `lifecycle_stage="lead"`. A foreign key `Lead.contact_id` (added in migration) links them. This survives lead deletion: contacts persist independently.

### 4.3 Revenue → LTV

`finance/log_revenue.py` is extended to also call `crm_ops.add_revenue_to_contact(email, cents)` which increments `lifetime_value_cents`, advances `lifecycle_stage` from `customer` → `repeat` after the second non-zero revenue event, and stamps `purchased_at` if unset.

---

## 5. Lifecycle Stages & Transitions

```
   ┌──── (manual add) ────┐
   │                      │
   │   (cold outreach,    │
   │    inbound form)     │
   ▼                      ▼
 [lead] ── sample order ──► [sample] ── paid order ──► [customer]
   │                                                       │
   │                                                       │ 2+ paid orders
   │                                                       ▼
   │                                                  [repeat]
   │                                                       │
   │                                                       │ no activity 180d
   │                                                       ▼
   │◄────── unsubscribe (any stage) ──────────────► [unsubscribed]
   │                                                       │
   │                                                  (terminal)
   ▼
[dormant]                                          GDPR erase
(no activity                                             │
 180d as a lead)                                         ▼
                                                    [erased]
                                                    (terminal,
                                                     PII null)
```

Transitions are computed in `crm_ops.recompute_stage(contact_id)`:

- `lead → sample` — first Job with venture-sample input_data
- `sample → customer` — first Job with `input_data.is_testing=false` AND `RevenueEvent > 0`
- `customer → repeat` — second non-zero RevenueEvent
- `* → dormant` — Celery beat task nightly: `last_activity_at < now - 180d` AND stage in (lead, sample)
- `* → unsubscribed` — explicit unsubscribe click, bounce, or complaint
- `* → erased` — GDPR erasure endpoint

Stage never auto-reverses; only manual operator action can move someone back (audited).

---

## 6. Privacy & Compliance (Load-Bearing)

This section defines hard rules. Every "MUST" maps to a concrete code location and a test.

### 6.1 Suppression — single source of truth

**MUST:** Every outbound email goes through `send_email()` in `src/aiplatform/skills/comms/send_email.py`. Before the Resend POST, the skill MUST query `Contact.do_not_contact_until` and `Contact.lifecycle_stage` by lowercased email. If `do_not_contact_until > now` OR `lifecycle_stage in ("unsubscribed", "erased")`, the skill returns `{error: "suppressed", reason: "..."}` and does NOT call Resend.

Today the check lives only in `worker.py` for outreach. This MUST move into the skill so delivery emails from every venture honor it.

### 6.2 Unsubscribe

**MUST:** Every outbound email body MUST contain a working unsubscribe link of the form `https://api.planBadmin.com/api/outreach/unsubscribe/{send_id_or_message_id}`.

**MUST:** Every outbound email MUST include RFC 8058 `List-Unsubscribe: <mailto:unsubscribe@echoforge.biz?subject=unsubscribe-{id}>, <https://...>` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` headers so Gmail/Outlook one-click unsubscribe works.

**MUST:** A draft-approval check rejects any body that does not contain the unsubscribe token. Implemented in `crm_ops.validate_outbound_body(body)`.

The existing unsubscribe handler is extended to also write a `crm_consent` revoke row and a `crm_audit_log` row with action `consent_revoke`.

### 6.3 CAN-SPAM (US) — mandatory elements

| Requirement | Where enforced |
|---|---|
| Accurate "From" name | `EMAIL_FROM` env var; verified at send |
| Non-deceptive subject | Operator review; flagged by `validate_outbound_body()` for known dark patterns |
| Identify message as ad (for marketing/outreach) | Footer template includes "This is a marketing email from EchoForge" |
| Physical postal address in footer | `BUSINESS_ADDRESS` env var injected into every footer |
| Working unsubscribe within 10 business days | Real-time (instant flip on click); see §6.2 |
| Honor opt-outs going forward | §6.1 hard gate |

### 6.4 GDPR (EU) + similar (UK, Israel PPL, California CCPA/CPRA)

| Right | Endpoint | Behavior |
|---|---|---|
| Access | `POST /api/crm/contacts/{id}/export` | Returns JSON containing every row from `contacts`, `leads`, `lead_drafts`, `outreach_sends`, `contact_messages`, `jobs`, `crm_audit_log`, `crm_consent` matching the contact. Triggered by operator on operator-confirmed user request. |
| Rectification | `PATCH /api/crm/contacts/{id}` | Audit-logged. |
| Erasure | `POST /api/crm/contacts/{id}/erase` | Sets `gdpr_erasure_at=now`, `lifecycle_stage=erased`, nulls `email`, `name`, `phone`, `address`, `usernames`, `notes`. Retains `email_hash` so the contact cannot be re-ingested. Cascades: PII fields nulled in `leads`, `lead_drafts`, `contact_messages`, `outreach_sends.email`. `crm_audit_log.before/after` PII scrubbed and replaced with `{"erased": true, "email_hash": "..."}`. |
| Restriction | `POST /api/crm/contacts/{id}/suppress` | Sets `do_not_contact_until=2099-01-01`. |
| Portability | `POST /api/crm/contacts/{id}/export` | Same as Access — JSON format is portable. |
| Objection | Unsubscribe click | See §6.2. |

### 6.5 Cooldowns

| Channel | Default cooldown | Helper |
|---|---|---|
| Sample order (per venture) | 30 days | `can_send_sample(email, venture, days=30)` — exists |
| Cold outreach (any venture) | 60 days | `can_send_outreach(email, venture, days=60)` — new |
| Marketing email (newsletter) | 7 days | `can_send_marketing(email, days=7)` — new |

Cooldowns are enforced at draft-approval AND at order-creation time (to prevent spam re-trigger). Operator override requires a typed reason; reason is audit-logged.

### 6.6 Consent ledger

Every outbound email is categorized at compose time:

| Category | Lawful basis | Requires explicit opt-in? |
|---|---|---|
| `transactional` | Order fulfillment / contract | No (implicit from order) |
| `marketing` | Explicit consent | **Yes** — checked against `crm_consent` |
| `outreach` | Legitimate interest | No, but opt-out MUST be clear |

The `send_email()` skill receives `consent_type` as a required argument and verifies the consent row exists (for `marketing`) before sending.

### 6.7 Bounce & complaint webhook

**MUST:** A new `POST /api/webhooks/resend` endpoint (in `src/aiplatform/webapp/routers/webhooks.py`) handles Resend's events:

- `email.bounced` (hard) → `do_not_contact_until=2099-01-01`, audit `bounce`
- `email.complained` → `do_not_contact_until=2099-01-01`, `lifecycle_stage=unsubscribed`, audit `complaint`
- `email.delivered`, `email.opened`, `email.clicked` → update `OutreachSend.status` timestamps; no contact change

Signature verification via `RESEND_WEBHOOK_SECRET`. Unsigned requests rejected.

### 6.8 PII at rest

`email` is stored plaintext. Encrypting it would require schema-wide changes and is out of scope for v1. The spec calls this out so it can be tracked as future work.

### 6.9 Access control

All `/api/crm/*` endpoints are behind the existing `ALLOWED_EMAIL` JWT (added by `Depends(require_user)` like every other admin router). Every write logs `actor_user` from the JWT subject to `crm_audit_log`. The data model includes `owner_user` so a future multi-user rollout can layer roles without schema change.

### 6.10 Data retention

Driven by `lifecycle_stage`:

| Stage | Retention |
|---|---|
| `lead`, `sample` | 12 months from `last_activity_at`, then auto-erase |
| `customer`, `repeat`, `dormant` | 7 years (tax / business record) |
| `unsubscribed` | Indefinite (must keep to honor opt-out) |
| `erased` | Email hash indefinite; PII fields null |

Auto-erase runs as a nightly Celery beat task `crm.purge_expired_leads`.

---

## 7. API Surface

All endpoints under `/api/crm/*` in `src/aiplatform/webapp/routers/crm.py`. Auth: JWT (`ALLOWED_EMAIL`).

```
GET    /api/crm/contacts
       ?status=...&venture=...&source=...&tag=...&lifecycle_stage=...
       &q=<search>&owner=...&page=1&limit=50
       → { items: [...], total, page, limit }

GET    /api/crm/contacts/{id}
       → full contact + counts (leads_count, jobs_count, sends_count)

PATCH  /api/crm/contacts/{id}
       body: { name?, phone?, company?, website_url?, tags?, owner_user?,
               lifecycle_stage?, do_not_contact_until? }
       → updated contact; audited

POST   /api/crm/contacts
       body: { email?, usernames?, name?, lifecycle_stage?, primary_source?,
               consent: { venture, channel, consent_type, lawful_basis } }
       → created contact; consent row created in same txn; audited

POST   /api/crm/contacts/{id}/merge
       body: { merge_into_id: uuid }
       → merged contact; loser row archived to audit log

POST   /api/crm/contacts/{id}/note
       body: { text: string }
       → audit log row appended; note returned

POST   /api/crm/contacts/{id}/suppress
       body: { until: ISO8601, reason: string }
       → contact with do_not_contact_until set; audited

POST   /api/crm/contacts/{id}/export
       → 200 application/json — full bundle (see §6.4); audited

POST   /api/crm/contacts/{id}/erase
       body: { reason: string, confirm: true }
       → 204; PII nulled; audited (with scrubbed payload)

GET    /api/crm/contacts/{id}/timeline
       → unified, chronological events:
         [{ at, type, venture, source, summary, payload_id }]
         types: lead_found | lead_qualified | draft_composed | outreach_sent |
                outreach_opened | outreach_replied | sample_ordered |
                order_placed | order_delivered | revenue_event |
                consent_grant | consent_revoke | note | manual_edit

GET    /api/crm/consent/{contact_id}
       → list of CrmConsent rows

POST   /api/crm/consent
       body: { contact_id, venture, channel, consent_type, lawful_basis,
               source, granted? : bool }
       → consent row created or revoked; audited

GET    /api/crm/stats
       ?venture=...&from=...&to=...
       → { by_stage: {...}, by_source: {...}, conversion_funnel: {...},
           ltv_total, ltv_avg }

GET    /api/crm/audit
       ?contact_id=...&action=...&from=...&to=...&page=1
       → paginated CrmAuditLog rows (admin only)

POST   /api/webhooks/resend
       headers: svix-signature
       body: Resend event payload
       → 204; event applied (bounce/complaint/delivered)
```

Legacy `/api/outreach/contacts` GET is preserved (redirects internally to `/api/crm/contacts`) until the Marketing module migrates.

---

## 8. Frontend

### 8.1 Routing

New top-level route in `frontend/src/App.tsx`:

```
<Route path="crm" element={<CRM />} />
<Route path="crm/:contactId" element={<CRM />} />
```

New entry in `frontend/src/components/Sidebar.tsx` between Marketing and Finance:

```
{ label: "Customers", to: "/crm", icon: "groups" }
```

### 8.2 Page structure

Single page `frontend/src/pages/CRM.tsx` with three tabs (URL-state via `?tab=`):

1. **Contacts** — filterable table
2. **Contact Detail** — drawer or route `/crm/{id}`, opened from row click
3. **Compliance** — suppression list + GDPR queue + audit log

Sub-components in `frontend/src/components/crm/`:

- `ContactsTable.tsx`
- `ContactDetailPanel.tsx`
- `Timeline.tsx`
- `ConsentPanel.tsx`
- `ComplianceTab.tsx`
- `AuditLogTable.tsx`

### 8.3 Design system

Reuses what `Marketing.tsx` already establishes — no new tokens, no new component library:

- Inter font, `font-headline` for h-titles, `font-label uppercase tracking-[0.15em]` for chips/columns
- Material 3 surface tokens (`bg-surface-container`, `text-on-surface-variant`, `border-outline`)
- Material Symbols icons via `<span className="material-symbols-outlined">`
- Status badges: `STATUS_COLORS` map from `Marketing.tsx:47` — extended with `customer`, `repeat`, `dormant`, `erased`

### 8.4 Funnel KPIs

Top of Contacts tab — four `KpiCard` instances (reusing existing component):

| Card | Value |
|---|---|
| Total contacts | `stats.by_stage.total` |
| New leads (30 d) | `stats.new_leads_30d` |
| Active customers | `stats.by_stage.customer + repeat` |
| LTV total | `stats.ltv_total / 100` $ |

### 8.5 Destructive action UX

- Erase, Suppress, Merge: show a confirm dialog that previews the exact audit log row that will be written
- GDPR Erase requires the operator to type "ERASE {email}" to confirm
- Bulk operations cap at 50 rows per action

---

## 9. Migration & Rollout

| Step | Notes |
|---|---|
| 1. Alembic migration | Add columns + 2 tables + backfill. Reversible. |
| 2. Extend `crm_ops.py` | `upsert_contact`, `recompute_stage`, `can_send_outreach`, `can_send_marketing`, `validate_outbound_body`, `add_revenue_to_contact`, `merge_contacts`. |
| 3. Move suppression gate into `send_email.py` | One-line check; raise `EmailSuppressed`. |
| 4. Wire ingestion writers | Touch sample router + each venture order router to call `upsert_contact`. |
| 5. Build `crm.py` router | All endpoints in §7. |
| 6. Build `webhooks.py` router | Resend webhook. Configure Resend dashboard to point at it. |
| 7. Frontend page | Three tabs. |
| 8. Resend webhook secret | Add `RESEND_WEBHOOK_SECRET` to Railway env. |
| 9. Backfill verification | Spot-check 10 random contacts via the new UI. |
| 10. Cut over Marketing module's contact endpoint | Internal redirect; deprecate old endpoint after one release. |

---

## 10. Verification

End-to-end checklist (operator + automated):

1. **Sample ingestion** — `curl POST /api/sample/podcast` with new email → Contact row exists with `lifecycle_stage=sample`, `primary_source=sample_podcast`, ContactMessage row for delivery email present.
2. **Order ingestion** — Place a Marketing Audit order with a brand-new email → Contact row with `lifecycle_stage=customer`, `purchased_at` set, Job linked.
3. **Repeat detection** — Place a second order from same email → `lifecycle_stage=repeat`.
4. **Suppression hard gate** — `POST /api/crm/contacts/{id}/suppress` → attempt to trigger any delivery email through any venture → `send_email()` returns `suppressed` and no Resend call happens.
5. **Unsubscribe** — Click `unsubscribe/{send_id}` link → `Contact.lifecycle_stage=unsubscribed`, `crm_consent` revoke row exists, future sends to this email blocked across all 6 ventures.
6. **GDPR export** — `POST /api/crm/contacts/{id}/export` → JSON contains rows from at least `contacts`, `jobs`, `contact_messages`, `crm_audit_log` for the test contact.
7. **GDPR erasure** — `POST /erase` → `lifecycle_stage=erased`, `email` null, `email_hash` populated, attempt to re-ingest with the same email → Contact NOT recreated.
8. **Bounce webhook** — Send a test event to `/api/webhooks/resend` with `email.bounced` → `do_not_contact_until=2099-01-01`, audit row `bounce`.
9. **Audit log** — Every PATCH, suppress, merge, erase produces exactly one `crm_audit_log` row with `actor_user` populated.
10. **CAN-SPAM body check** — Approve a draft with the unsubscribe token removed → approval rejected with clear error.
11. **Cooldown** — Try to send a second sample to the same email within 30d → blocked at order-creation with operator-visible message.
12. **Multi-user readiness** — `owner_user` column populated on every Contact; consent rows carry `ip_address` and `user_agent` where captured.

---

## 11. Out of Scope (v1)

- IMAP/Gmail polling for inbound replies (manual-add fallback for now)
- Drip / sequence engine (each campaign still a one-shot)
- Per-contact pricing / quote management
- Subscription billing
- Encryption of PII at rest (column-level KMS) — known gap
- Multi-user role UI (data model is ready; UI is single-user)
- Webhooks out to third-party CRMs (HubSpot, Salesforce)
- Slack notifications on lifecycle change

---

## 12. Open Questions

- Should `customer` → `repeat` require 2 distinct ventures purchased, or 2 orders in any venture? Current spec: any 2.
- Retention for `customer` set to 7 years (tax). Confirm against jurisdiction for echoforge.biz operating entity.
- Should `BUSINESS_ADDRESS` be per-venture or single platform-wide? Current spec: single, set on Railway env.
- Resend webhook secret rotation — manual today; tracked separately.
