# Venture: Accessibility Audit
# CLAUDE.md — Isolation boundary active

## Context
Standalone WCAG 2.1 accessibility scanning service under the EchoForge brand.
Scans any public URL using Playwright + axe-core, generates a branded PDF report
with compliance score, violation breakdown, and remediation steps.

## Isolation Rule
This venture may import platform skills only. No cross-venture imports.
Dependencies: platform → skills only. Never venture → venture.

---

## Service Tiers

| Tier | Price | Pages | Delivery | Notes |
|---|---|---|---|---|
| Single Page | $49 | 1 | 24h | Sample/teaser — limited output |
| Standard | $149 | 5 | 48h | Full report, top 5 pages |
| Premium | $249 | 20 | 72h | Full site crawl, detailed remediation |

---

## Pipeline Phases

1. **Order intake** — UI trigger (`POST /api/ventures/accessibility-audit/orders`) or API
2. **Scan** — `accessibility_scan.py` runs Playwright + axe-core against the target URL
3. **Report generation** — `generate_accessibility_report.py` renders HTML → PDF via Playwright
4. **Drive upload** — PDF stored in `DRIVE_ACCESSIBILITY_ORDERS_ID` (or samples folder for sample tiers)
5. **Review gate** — status set to `review_pending`; human review triggered
6. **Delivery** — after approval, delivery email sent to `client_email` with Drive link

---

## Skills Used (from platform/skills/)

- `audit/accessibility_scan.py` — Playwright + axe-core WCAG scan
- `audit/generate_accessibility_report.py` — HTML-to-PDF report renderer
- `storage/drive_organise.py` — create per-order Drive folder
- `storage/drive_write.py` — upload PDF to Drive
- `comms/send_email.py` — delivery notification to client

---

## Pipeline Entry Points

```python
from ventures.accessibility_audit.pipeline import run_order, deliver_order

run_order(audit_id, url)               # Phases 2–5: scan → generate → upload → review_pending
deliver_order(job_id, review_notes)    # Phase 6: email → mark delivered
```

Celery task registrations in `worker.py` call these functions — tasks contain no business logic.

---

## Human Tasks

### One-time setup
- Create two Google Drive folders: `/AccessibilityOrders/` and `/AccessibilitySamples/`
- Add their IDs to Railway env vars: `DRIVE_ACCESSIBILITY_ORDERS_ID`, `DRIVE_ACCESSIBILITY_SAMPLES_ID`
- Set `HUMAN_REVIEW_EMAIL` on Railway to the reviewer's inbox

### Per-order review gate
- Every order lands at `review_pending` before delivery
- Reviewer receives an email with the Drive link
- Approval/rejection via management app: planBadmin.com → Ventures → Accessibility Audit
- Reviewer should check: score plausibility, PDF renders correctly, no PII leakage

### Escalation
- If a scan fails (JS-heavy SPA, auth wall, bot detection): set order to `failed`, notify client
- Do not re-run without adjusting the target URL or scan settings

### Post-delivery
- Log revenue: `finance/log_revenue.py` — called manually until auto-logging is wired
- File the signed client agreement before delivering premium reports

---

## Environment Variables

```
DRIVE_ACCESSIBILITY_ORDERS_ID=   # Google Drive folder for full order PDFs
DRIVE_ACCESSIBILITY_SAMPLES_ID=  # Google Drive folder for sample/teaser PDFs
DRIVE_ACCESSIBILITY_ROOT_ID=     # Fallback root if split folders not set
HUMAN_REVIEW_EMAIL=              # Inbox that receives review notifications
AUTO_APPROVE=false               # Set true after 20 validated deliveries
```

---

## Order Status State Machine

```
pending → running → review_pending → delivered
                               └→ failed
```

---

## Key Constraints

- Never deliver a report without human review (until AUTO_APPROVE is enabled)
- Reports are based on publicly accessible page content only — no authenticated scans
- PDF contains WCAG 2.1 violation data only — no client source code or credentials
- Tier controls page depth, not scoring methodology

---

## Sprint Roadmap

### Sprint 1 — Core Pipeline (complete)
- [x] `accessibility_scan.py` — Playwright + axe-core scan skill
- [x] `generate_accessibility_report.py` — branded PDF skill
- [x] Celery task registration in worker.py
- [x] DB model: `AccessibilityAudit`
- [x] Admin UI: planBadmin.com → Accessibility Audit page
- [x] Integrated into premium marketing audit (appended to main PDF)

### Sprint 2 — Proper venture structure (current)
- [x] `src/ventures/accessibility_audit/` created
- [x] `config.py` — env vars + tier definitions
- [x] `pipeline.py` — `run_order()` + `deliver_order()` extracted from worker.py
- [x] `CLAUDE.md` — venture context

### Sprint 3 — Enhancements
- [ ] Multi-page crawl for Standard/Premium tiers
- [ ] Auto-approve after N deliveries
- [ ] Public sample endpoint `POST /api/sample/accessibility`
- [ ] Revenue logging wired into pipeline
