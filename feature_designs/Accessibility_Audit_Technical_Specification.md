# Technical Specification: Accessibility Audit Module (AAM)

**Project:** Echoforge Audit Infrastructure
**Status:** Ready for Implementation
**Priority:** High (Core Revenue Feature)

---

## 1. Functional Overview

The AAM is a "Productized Service" module designed to perform automated accessibility scans and generate a Development Roadmap (PDF/JSON). It must function in two modes:

- **Standalone:** A deep-dive audit focused solely on WCAG 2.1/2.2 compliance.
- **Bundled:** A high-level compliance "health check" integrated into the Elite Growth Audit pipeline.

---

## 2. Technical Stack & Tools

| Component | Tool |
|---|---|
| Engine | axe-core (industry standard for automated accessibility) |
| Driver | Playwright (Python) for headless browser interaction and DOM rendering |
| Integration Library | axe-playwright-python |
| Backend | FastAPI (Existing) for asynchronous job orchestration |
| Data Store | PostgreSQL (Existing) using a JSONB column for raw audit results |
| Report Generation | WeasyPrint or ReportLab (Python) — Markdown/HTML → PDF |

---

## 3. Architecture & Workflow

The module follows a **non-blocking worker pattern** to handle the compute-heavy nature of DOM scanning.

### A. API Layer (FastAPI)

- `POST /v1/audit/accessibility/initiate`
  Accepts `target_url`, `client_id`, and `is_bundled` flag. Returns a `job_id`.

- `GET /v1/audit/accessibility/status/{job_id}`
  Returns progress percentage and current status: `Queued | Scanning | Analyzing | Completed`.

- `GET /v1/audit/accessibility/report/{job_id}`
  Retrieves the final JSON data or a signed URL for the PDF download.

### B. Worker Logic (The "Scanner")

1. **Initialization:** Launch Playwright headless instance.
2. **Authentication Handling:** Ability to inject headers/cookies if the target site is behind a login (for premium manual-plus-auto audits).
3. **The Scan:** Inject axe-core and execute `axe.run()`.
4. **Impact Filtering:** Categorize findings by `Critical`, `Serious`, `Moderate`, and `Minor`.
5. **Code Snippet Extraction:** For every violation, capture the exact HTML snippet and the "Target" CSS selector to facilitate developer fixes.

---

## 4. Database Schema Requirements

Add the following to the existing PostgreSQL `audits` table or a new `accessibility_audits` relation:

| Column | Type | Description |
|---|---|---|
| `audit_id` | UUID (PK) | Unique identifier for the audit. |
| `raw_axe_results` | JSONB | The complete JSON output from the Axe engine. |
| `roadmap_data` | JSONB | Processed findings: [Violation] |
| `compliance_score` | Integer | Calculated percentage (0–100) for high-level reporting. |
| `manual_override_notes` | Text | Placeholder for manual human testing notes (future-proofing). |

---

## 5. Implementation Details for Coding Agent

### Phase 1: The Core Scanner (Python)

```python
from playwright.async_api import async_playwright
from axe_playwright_python.async_playwright import Axe

async def run_accessibility_scan(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)

        axe = Axe()
        results = await axe.run(page)
        await browser.close()
        return results
```

### Phase 2: The "Roadmap" Generator

The agent must implement a logic layer that translates raw Axe results into a Development Roadmap.

- **Input:** Axe JSON
- **Logic:** Group by `rule_id`
- **Output:** A structured list of "Tickets" including:
  - Problem description (user-friendly)
  - Impact level
  - Remediation guidance (e.g., *"Add aria-label to this element"*)
  - Source code location

### Phase 3: Integration with "Elite Growth Audit"

When `is_bundled == True`:

- The worker should only return the **top 5 "Critical" violations** and the overall compliance score to be injected into the main Marketing Audit PDF.
- Add a call-to-action in the report: *"Upgrade to the Full Accessibility Roadmap for 100% compliance coverage."*

---

## 6. Definition of Done (DoD)

- [ ] API can accept a URL and return a valid JSON of accessibility violations.
- [ ] Data is successfully persisted to PostgreSQL JSONB columns.
- [ ] A PDF report can be generated containing at least the "Critical" and "Serious" violations.
- [ ] System handles SPA (Single Page Application) rendering correctly via Playwright's `wait_until="networkidle"`.
