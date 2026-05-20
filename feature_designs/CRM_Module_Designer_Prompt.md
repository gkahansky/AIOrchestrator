# Designer Prompt — Customers (CRM) Page for planBadmin

**Audience:** Claude (designer) generating the UI for `frontend/src/pages/CRM.tsx` and supporting components.

---

## What you're building

A new top-level **Customers** page for planBadmin.com. It is the single place to view, manage, and act on every person who has ever touched any of our ventures — leads picked up by cold outreach, sample-order requesters from echoforge.biz, paid customers across all six ventures, and post-sale follow-ups.

The page must feel like it has always been part of planBadmin — same fonts, same surface tokens, same badge shapes, same iconography — not a bolt-on. Read the existing pages before designing anything new.

---

## Mandatory references (read first)

| File | Why |
|---|---|
| `frontend/src/pages/Marketing.tsx` | Closest sibling page. Copy the badge style, filter pill row, status color map (`STATUS_COLORS` at line 47), table density, and tab structure. |
| `frontend/src/pages/StrategyRoom.tsx` | Reference for multi-tab layout with URL state (`?tab=`). |
| `frontend/src/components/Sidebar.tsx` | Where the new `Customers` entry goes (between Marketing and Finance, icon `groups`). Match the existing item shape exactly. |
| `frontend/src/components/` | Reuse `KpiCard`, `StatusBadge`-style chips, any existing `Drawer`/`Modal`. Do not introduce new component libraries. |
| `feature_designs/CRM_Module_Specification.md` | The full spec — data model, endpoints, lifecycle stages, compliance rules. Every UI element here maps to something in the spec. |

---

## Design system — non-negotiables

- **Font family:** Inter (already loaded). `font-headline` for h-titles, `font-label uppercase tracking-[0.15em]` for chips and column headers.
- **Tokens:** Material 3 tonal palette already in the Tailwind config — use `bg-surface`, `bg-surface-container`, `bg-surface-container-low`, `text-on-surface`, `text-on-surface-variant`, `border-outline`, `text-primary`, `text-error`. Never introduce hex values.
- **Icons:** Material Symbols via `<span className="material-symbols-outlined">icon_name</span>`. Common ones for this page: `groups`, `mail`, `block`, `download`, `delete_forever`, `verified_user`, `history`, `merge_type`, `label`, `gavel`.
- **Badges:** Reuse `STATUS_COLORS` map from `Marketing.tsx:47`. Extend with: `customer` → `bg-emerald-600 text-white`, `repeat` → `bg-emerald-700 text-white`, `dormant` → `bg-surface-dim text-on-surface-variant`, `erased` → `bg-neutral-200 text-neutral-500`.
- **Buttons:** Match Marketing.tsx primary button styling (`bg-primary text-on-primary px-3 py-2 rounded-lg`). Destructive actions: `bg-error text-on-error`.
- **No new design tokens.** No new UI library (no Radix, no Shadcn, no MUI). React + Tailwind + Material Symbols only.

---

## Page structure

Top-level layout matches every other page: full-height flex column under the existing `TopBar` + `Sidebar` shell. Three tabs, URL-driven (`?tab=contacts|detail|compliance`). Default tab: `contacts`.

### Tab 1 — Contacts (the main view)

**Above the table — KPI strip:**

Four `KpiCard` instances in a `grid-cols-4 gap-3`:

| Card | Value | Sub-label |
|---|---|---|
| Total Contacts | `stats.total` | "all ventures" |
| New Leads (30d) | `stats.new_leads_30d` | trend arrow vs prior 30d |
| Active Customers | `stats.customer + stats.repeat` | "purchased ≥1" |
| Lifetime Value | `$X,XXX` | "all-time" |

**Filter row:**

Sticky row of filter pills (use the same pill shape as `Marketing.tsx` PlatformBadge). Filters:

- Lifecycle stage — `[All] [Lead] [Sample] [Customer] [Repeat] [Dormant] [Unsubscribed]`
- Venture — `[All] [Marketing Audit] [Content Studio] [Security] [Etsy] [Market Research] [Content Repurposing]`
- Source — dropdown (outreach platforms + sample + order + manual)
- Tags — multi-select chip input
- Search input — searches name, email, company, usernames (icon: `search`)
- Right side: "Add Contact" button (icon: `person_add`), "Export CSV" button (icon: `download`)

**Table:**

| Column | Source | Notes |
|---|---|---|
| ☐ | Bulk-select checkbox | Header has select-all for current page |
| Contact | `name` + `email` stacked | Click → opens Contact Detail |
| Stage | StatusBadge | Color from extended `STATUS_COLORS` |
| Ventures | Comma-separated venture chips | Truncate at 3, show `+N` |
| Source | `primary_source` | Small text |
| Last Activity | `last_activity_at` | Relative (`2d ago`) with tooltip on hover for full timestamp |
| LTV | `$X` | Right-aligned; dim if `$0` |
| Owner | `owner_user` | Avatar circle with initial |
| ⋮ | Row actions menu | Open detail · Suppress · Merge · Export · Erase |

Pagination at bottom (`Marketing.tsx` already has a pattern — reuse it). Default 50 per page.

**Bulk-action bar** (appears when ≥1 row selected, slides up from bottom): `Tag…  Suppress…  Export…  [Clear selection]`. Cap at 50 rows; show error if more selected.

**Empty / loading / error states:**

- Empty filter result: centered icon `inbox`, "No contacts match these filters." Link "Clear filters" button.
- Loading: skeleton rows (8 of them) with `animate-pulse bg-surface-container`.
- Error: red banner `bg-error/10 text-error` with retry button.

### Tab 2 — Contact Detail

Opened by:
- Clicking a row in the Contacts table
- Direct URL `/crm/{contactId}`
- Mobile: full-screen route. Desktop: right-side drawer (~640px wide) over the Contacts table.

**Header card (sticky at top of drawer):**

```
┌─────────────────────────────────────────────────┐
│  ◯  Jane Doe                                    │
│      jane@example.com    [⎘ copy]               │
│      Acme Inc · acme.com                        │
│                                                 │
│      [stage badge] [primary_source chip]        │
│      Tags: [vip] [podcast-host] [+ add]         │
│                                                 │
│      Last activity: 2 hours ago                 │
│      LTV: $1,240                                │
│                                                 │
│   ── Actions ───────────────────────────────    │
│   [Edit] [Suppress] [Merge] [Export] [Erase]    │
└─────────────────────────────────────────────────┘
```

`[Erase]` is `bg-error text-on-error`. All other action buttons are secondary (`bg-surface-container`).

**Body — three stacked sections:**

1. **Timeline** (default expanded)
   - Vertical timeline, newest at top.
   - Each event: timestamp (left, dim) · venture-colored dot · event type icon · summary text · optional "View →" link to the underlying Job / OutreachSend / etc.
   - Event types: lead_found, lead_qualified, draft_composed, outreach_sent (with open/reply chips), sample_ordered, order_placed, order_delivered, revenue_event ($), consent_grant, consent_revoke, note (operator), manual_edit.
   - Venture-colored dots: each venture has a stable color from the existing palette (no new colors — reuse the Marketing tab's badge colors).
   - Free-text **note** input at the bottom of the timeline ("Add a note…" → expands to textarea → "Save" writes to audit log).

2. **Consent panel** (collapsed by default)
   - Matrix: rows = ventures, columns = channels (email / sms / platform_dm).
   - Each cell: small chip showing current `consent_type` + `lawful_basis`, color-coded:
     - `transactional` → blue chip
     - `marketing (explicit, granted)` → green chip
     - `marketing (revoked)` → red chip with strikethrough
     - `outreach (legitimate_interest)` → amber chip
     - `none` → dimmed dash
   - Click any cell → modal to grant/revoke, with `source` and `lawful_basis` dropdowns. Modal preview shows the exact audit row that will be written.

3. **Linked Records** (collapsed)
   - Three sub-lists: Leads, Jobs, Outreach Sends.
   - Each entry: small row with link to existing page (`/jobs/{id}`, `/marketing?lead={id}`).

### Tab 3 — Compliance

Three vertically stacked panels with their own collapse/expand state. None of these have filters that pollute the URL — this is an admin view.

1. **Suppression List**
   - Table: email · suppressed since · reason · until (or "Permanent") · actions (`Lift` button, disabled if reason in (bounce, complaint)).
   - Sortable by suppressed_at desc.
   - Total count badge in the panel header.

2. **GDPR Queue**
   - Two sub-sections:
     - **Pending Erasures** — contacts with operator-marked erase requests not yet executed. Each row has `[Confirm Erase]` (red, requires typing `ERASE {email}`).
     - **Recent Exports** (last 30 days) — log of every export action, with download link to the saved JSON.

3. **Audit Log**
   - Filter row: actor · action · contact · date range.
   - Table: timestamp · actor_user · action chip · contact (name+email or "—" if erased) · diff summary (collapsible — click to expand JSON before/after side-by-side).
   - 100 rows per page, jump-to-date input.
   - **Read-only** — no edit, no delete. Visible only to ALLOWED_EMAIL JWT.

---

## Destructive action UX (universal rule)

Every destructive action (Suppress, Erase, Merge, Bulk-suppress, Lift-suppression) shows a **confirmation dialog** that:

1. Restates what will change in plain English ("This will permanently erase Jane Doe's contact record across 4 ventures and null out PII in 12 related rows.")
2. Shows the exact `crm_audit_log` row that will be written.
3. Requires either a typed confirmation (`ERASE {email}`) or an explicit checkbox plus reason text.
4. Default-focused button is **Cancel**, not Confirm.

---

## Mobile breakpoint

At `md:` and below:

- Sidebar collapses to drawer (existing behavior — already handled by `Sidebar.tsx`).
- KPI strip becomes `grid-cols-2`.
- Filter row scrolls horizontally.
- Contact Detail becomes a full-screen route, not a drawer.
- Timeline events stack; left-side timestamp moves above the event line.
- Tables become cards (one row → one card).

---

## Empty / loading / error states (universal)

Specify for every list and panel:

- **Loading** — skeleton blocks with `animate-pulse bg-surface-container rounded`. Never use spinners except for inline button states.
- **Empty (zero data)** — centered icon (Material Symbols), one-line title, one-line CTA. Example: "No leads yet. Connect a campaign in Marketing →".
- **Empty (filter result)** — different icon (`filter_alt_off`), "No results match these filters", "Clear filters" link.
- **Error** — `bg-error/10 text-error` banner with the error message and a retry button. Never silently fail.

---

## Accessibility

- Every actionable icon has an aria-label.
- Modals trap focus and close on Escape.
- Color is never the only signal — every status chip has both a color and a text label.
- All tables are keyboard-navigable (tab through rows, Enter to open detail).
- Destructive confirmations honor `prefers-reduced-motion`.

---

## What you should produce

1. **`frontend/src/pages/CRM.tsx`** — the page component, mirroring how `Marketing.tsx` is structured (page-level state + tab routing + sub-components).
2. **`frontend/src/components/crm/`** — sub-components, one per top-level UI block:
   - `ContactsTable.tsx`
   - `ContactsFilters.tsx`
   - `ContactDetailPanel.tsx`
   - `Timeline.tsx`
   - `ConsentPanel.tsx`
   - `ComplianceTab.tsx`
   - `AuditLogTable.tsx`
   - `SuppressionList.tsx`
   - `GdprQueue.tsx`
   - `DestructiveConfirmDialog.tsx`
3. **One-line edit to `frontend/src/components/Sidebar.tsx`** — add the Customers entry between Marketing and Finance.
4. **One-line edit to `frontend/src/App.tsx`** — add the `/crm` and `/crm/:contactId` routes.

Endpoints to call are listed in `feature_designs/CRM_Module_Specification.md` §7. Use the existing `authHeader()` helper from `Marketing.tsx:6` and the existing `API` constant (`import.meta.env.VITE_API_URL`).

Use `@tanstack/react-query` (already in the project) for all data fetching; mutations should invalidate the relevant query keys on success.

---

## Look-and-feel checklist (verify before submitting)

- [ ] Side-by-side screenshot with `/marketing` shows the same fonts, spacing, badge shapes, button styles
- [ ] Sidebar entry uses the same icon + label pattern as the other items
- [ ] No raw hex colors anywhere — only Tailwind tokens from the existing config
- [ ] No external UI libraries imported
- [ ] All destructive actions have a typed-confirmation step
- [ ] All audit-loggable actions show a preview of the audit row in their confirm dialog
- [ ] Status colors for `customer`/`repeat`/`dormant`/`erased` extend (do not replace) the `STATUS_COLORS` map
- [ ] Mobile layout tested at 375px width
- [ ] All empty / loading / error states specified for every list
