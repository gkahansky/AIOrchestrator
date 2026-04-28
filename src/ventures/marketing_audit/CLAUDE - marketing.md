# Venture: Website Marketing Audit
# CLAUDE.md — Isolation boundary active

## Context
Standalone service: audit any public website across 6 weighted marketing dimensions,
deliver a scored PDF + Markdown report within 24–72 hours depending on tier.
Powered by ai-marketing-claude skill system + custom EchoForge delivery pipeline.

## Isolation Rule
This venture may import platform skills only. No cross-venture imports.
Dependencies: platform → skills only. Never venture → venture.

---

## Web UI Trigger

Orders can be submitted via the management app at planBadmin.com (Ventures → Marketing Audit → New Order).
The UI posts to `POST /api/ventures/marketing-audit/orders` which writes the job to DB and queues a Celery task.
CLI trigger still works: `python scripts/run_marketing_audit.py`.

---

## Service Tiers

| Tier | Price | Delivery | Output |
|---|---|---|---|
| Snapshot | $49 | 24h | Score + top 5 actions, PDF — 5–10 pages |
| Full Audit | $149 | 48h | 6 dimensions + 2 competitors + copy examples, PDF — 10–15 pages |
| Audit + Strategy | $249 | 72h | Full audit + 30-day roadmap + 3 competitors, PDF — 15–20 pages |

---

## Scoring Framework (weighted, 0–100 total)

| Dimension | Weight | Measures |
|---|---|---|
| Content & Messaging | 25% | Copy quality, value props, headlines, CTAs |
| Conversion Optimisation | 20% | Funnel flow, friction, social proof, urgency |
| SEO & Discoverability | 20% | On-page SEO, technical, content structure |
| Competitive Positioning | 15% | Differentiation, market awareness, moats |
| Brand & Trust | 10% | Design quality, trust signals, authority |
| Growth Strategy | 10% | Pricing clarity, acquisition channels, retention |

---

## Public Sample Endpoint

Unauthenticated endpoint for lead generation: `POST /api/sample/audit`

- Rate-limited: 1 request per email per 24 hours (enforced via DB)
- Inputs: `email` (Form), `url` (Form)
- Runs the full pipeline with `report_type=sample`
- Emails the sample PDF to the requester after approval
- No client revenue logged (uses `sample_email` field, not `client_email`)

---

## Pipeline Phases

1. **Order intake** — UI trigger (`POST /api/ventures/marketing-audit/orders`) or CLI or sample endpoint
2. **URL scrape** — `scrape_website.py` wraps `analyze_page.py` from ai-marketing-claude. BFS multi-page crawler (up to 20 pages), seeded from `sitemap.xml`, merges findings across all pages before scoring.
3. **Competitor scrape** — `competitor_scanner.py` (Standard & Premium only; included in Phase 2)
4. **Audit report** — `generate_audit_report.py` calls Claude API, returns structured JSON
5. **Report generation** — Phase 4 generates reports per `report_type`:
   - `both` (default): full PDF + full MD + sample PDF + sample MD
   - `full`: full PDF + full MD only
   - `sample`: sample/censored PDF + MD only
6. **Upload + review gate** — PDFs uploaded to Drive; review email sent to `HUMAN_REVIEW_EMAIL` with Drive links; status set to `review_pending`
7. **Delivery** — triggered after approval; full PDF (or sample PDF for sample orders) emailed to `client_email` or `sample_email`

---

## Sample / Teaser Report

**File:** `ventures/marketing_audit/sample_report.py`

The sample report is a censored version of the full audit, designed for cold outreach
and sales emails. It shows enough to demonstrate value without giving away the full analysis.

### Censoring rules

| Section | What's shown | What's censored |
|---|---|---|
| Score breakdown | Full — all 6 dimensions with scores and key findings | Nothing |
| Key findings | Severity counts (all 4 levels) + 1–2 sample findings (High/Medium preferred) | All remaining findings shown as redaction bars with count |
| Action plan | First item from each timeframe (Quick Wins / Medium-Term / Strategic) | All remaining items shown as redaction bars with count |

**Critical findings** are censored unless all findings are critical (then 1 is surfaced).

### Outputs
- `{order_id}-audit-sample.pdf` — branded PDF with "SAMPLE" watermark + CTA footer
- `{order_id}-audit-sample.md` — Markdown with `🔒` redaction blocks (for proposal letters)

### Future workflow
The sample MD is designed to be embedded into a proposal letter generator (Sprint 4).
The `_censored_findings` and `_censored_actions` keys in `censor_report_data()` are the
canonical data structures for any downstream proposal template that needs the censored data.

---

## Skills Used (from platform + ai-marketing-claude)

### From ai-marketing-claude (install to ~/.claude/skills/):
- `market/SKILL.md` — orchestrator, routes /market commands
- `skills/market-audit/SKILL.md` — full audit orchestration
- `skills/market-quick/SKILL.md` — snapshot tier
- `skills/market-copy/SKILL.md` — before/after copy examples
- `skills/market-competitors/SKILL.md` — competitor benchmarking
- `skills/market-report-pdf/SKILL.md` — PDF generation
- `skills/market-report/SKILL.md` — Markdown report

### From platform/skills/:
- `storage/drive_write.py` — store report in Google Drive
- `comms/send_email.py` — delivery notification
- `comms/send_slack.py` — internal review alert
- `finance/log_revenue.py` — log order revenue
- `finance/log_cost.py` — log API costs

---

## Platform Skills — Status

### Built (Sprint 1)
- `media/scrape_website.py` ✓ — wraps `analyze_page.py` + `competitor_scanner.py` from ai-marketing-claude. Path resolved via `AI_MARKETING_CLAUDE_PATH` env var (default: sibling repo heuristic at `C:\Projects\AI\ai-marketing-claude`).
- `media/generate_audit_report.py` ✓ — calls Claude API with JSON-only prompt; tier-aware output; recomputes `overall_score` from weighted dimensions authoritatively.

### To Build (Sprint 2+)

#### `marketplace/audit_order_listener.py`
- Polls Fiverr via Gmail for order confirmation emails
- Parses website URL from requirements form
- Creates order record with status: pending

#### `marketplace/audit_deliver.py`
- Uploads PDF to Google Drive (client-facing folder)
- Posts view-only link via platform delivery mechanism
- Updates order status: delivered

---

## Order Status State Machine

```
pending → scraping → scraped → auditing → audited →
generating_report → report_ready →
uploading → uploaded → review_pending →
approved → delivering → delivered
                    └→ revision_requested → re_delivering → delivered
                    └→ failed
```

> **Note:** Upload to Drive happens before the review gate (Phase 5 upload + notify), not after.
> The review email contains Drive links; no PDFs are attached.
> Delivery email (Phase 6) is sent only after approval and goes to `client_email` OR `sample_email`.

---

## Environment Variables

```
AUDIT_UPWORK_CONSUMER_KEY=
AUDIT_UPWORK_ACCESS_TOKEN=
GOOGLE_CREDENTIALS_PATH=
GOOGLE_DRIVE_AUDIT_ROOT_ID=        # /MarketingAudits/ Drive folder
HUMAN_REVIEW_EMAIL=
SLACK_WEBHOOK_URL=
RAILWAY_PUBLIC_URL=
AUTO_APPROVE=false                  # Set true after 20 validated deliveries
COMPETITOR_MAX=3                    # Max competitors scraped per report
```

---

## Sprint Roadmap

### Sprint 1 — Core Pipeline ✓ DONE
- [x] `scrape_website.py` — wraps ai-marketing-claude `analyze_page.py` + `competitor_scanner.py`
- [x] `generate_audit_report.py` — Claude API, tier-aware JSON output, authoritative score recomputation
- [x] Full PDF via `generate_pdf_report.py` from ai-marketing-claude
- [x] Full Markdown report
- [x] Sample/censored PDF — `sample_report.py` with diagonal "SAMPLE" watermark, redaction bars, CTA page
- [x] Accessibility Audit Component — Switched to Playwright HTML-to-PDF rendering pipeline featuring Tailwind styling, EchoForge branding, tables, vertical instance breakdown, direct WCAG mapping, and compliance code-snippet generator.
- [x] Sample Markdown for proposal letter embedding (`🔒` blockquotes)
- [x] `--report-type both|full|sample` CLI flag
- [x] `--demo` mode for PDF testing without API calls
- [x] Resumable pipeline — `order.json` checkpoint after every phase; `--resume --order-id`
- [x] Live tested against `https://echoforge.biz/` — 29/100 (Grade F), 14 findings, cost $0.07
- Manual trigger: `python scripts/run_marketing_audit.py --url https://example.com --tier full`

### Sprint 2 — PDF Polish + Management App Integration ✓ DONE
- [x] EchoForge branded header/footer on all PDF pages
- [x] Management app at planBadmin.com — UI trigger, Orders tab, Testing checkbox
- [x] Drive upload before review gate (not after) — review email has Drive links, no attachment
- [x] Delivery email post-approval to `client_email` OR `sample_email`
- [x] Orders tab crash fixed (`input_data` added to `JobSummary` schema)
- [x] Testing mode — skips revenue logging, no email required

### Sprint 2b — Multi-Page Crawler + Sample Endpoint ✓ DONE
- [x] BFS site crawler — seeds from `sitemap.xml`, crawls up to 20 pages, deduplicates, merges findings
- [x] Language-agnostic CTA detection (Hebrew/English contact hrefs)
- [x] Prompts include `pages_crawled` count + URL list for accurate Claude context
- [x] Public sample endpoint `POST /api/sample/audit` — rate-limited, emails sample PDF to requester
- [x] Rate limiting: 1 request per email per 24h via DB
- [x] `openai` added to `requirements.txt`

### Sprint 3 — Proposal Letter + Outreach System
- Build proposal letter generator: takes sample MD + client context → full outreach email
- Outreach queue: scan prospect URLs → generate personalised sample → personalised cold email
- 3 reference sample audits (SaaS, service business, e-commerce) for portfolio

### Sprint 5 — Fiverr + Gmail Integration
- Build Fiverr listener via Gmail APScheduler
- Route Fiverr orders into same pipeline

### Sprint 6 — Auto-approve + Monitoring
- Enable AUTO_APPROVE after 20 validated deliveries
- Add monitoring alerts for failed audits

---

## Pre-Sprint Checklist

- [x] Clone ai-marketing-claude: vendored to `vendor/ai-marketing-claude/` in the repo
- [x] `pip install reportlab` — in `requirements.txt`
- [x] `pip install openai` — in `requirements.txt`
- [x] Multi-page BFS crawler live in `vendor/ai-marketing-claude/scripts/analyze_page.py`
- [x] Management app pipeline trigger live at planBadmin.com
- [x] Public sample endpoint live at `/api/sample/audit`
- [ ] Set `GOOGLE_DRIVE_TOKEN_JSON` + `GOOGLE_TOKEN_PATH=/tmp/google_token.json` in Railway (fixes Drive quota)
- [ ] Create `/MarketingAudits/` Google Drive folder; add ID to `.env` as `GOOGLE_DRIVE_AUDIT_ROOT_ID`
- [ ] Create new Fiverr gig (see platform_metadata_v4.md Part A)

---

## Key Constraints

- Agent never publishes a report without human review (first 20 orders)
- Competitor URLs always sourced from client requirements form or publicly known — never scraped from private data
- Reports never claim live data accuracy — always note audit is based on publicly visible page content at time of scrape
- Client receives PDF only — no source code, no raw JSON

## Pipeline Status
<!-- managed by update_task.py -->

| Roadmap ID | Task | Status | Note | Updated |
|---|---|---|---|---|
| H-02 | Marketing Audit — Sprint 2: PDF Polish | ✅ done | Added EchoForge branded header/footer to all PDF pages: dark navy band with echoforge wordmark + ter... | 2026-03-27 |
| D-17 | Multi-page BFS Crawler | ✅ done | BFS crawler with sitemap seeding, up to 20 pages, merges findings. Language-agnostic CTA detection. | 2026-04-05 |
| D-18 | Sample Audit Endpoint | ✅ done | POST /api/sample/audit live — rate-limited, emails sample PDF to requester. | 2026-04-05 |
| D-19 | Pipeline Ordering + Email Fixes | ✅ done | Upload before review gate; post-approval delivery email; sample_email fallback; Drive link fallback chain. | 2026-04-05 |
