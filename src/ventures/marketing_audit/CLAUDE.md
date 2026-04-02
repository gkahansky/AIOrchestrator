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

## Pipeline Phases

1. **Order intake** — platform listener detects new order (Upwork / Fiverr / email)
2. **URL scrape** — `scrape_website.py` wraps `analyze_page.py` from ai-marketing-claude
3. **Competitor scrape** — `competitor_scanner.py` (Standard & Premium only; included in Phase 2)
4. **Audit report** — `generate_audit_report.py` calls Claude API, returns structured JSON
5. **Report generation** — Phase 4 generates reports per `report_type`:
   - `both` (default): full PDF + full MD + sample PDF + sample MD
   - `full`: full PDF + full MD only
   - `sample`: sample/censored PDF + MD only
6. **Human review gate** — email to HUMAN_REVIEW_EMAIL with PDF(s) attached
7. **Delivery** — PDF(s) uploaded to Drive; full PDF emailed to client

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
- Polls Upwork /contracts for "marketing audit" tagged orders (5-min interval)
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
generating_report → report_ready → review_pending →
approved → delivering → delivered
                    └→ revision_requested → re_delivering → delivered
                    └→ failed
```

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

### Sprint 1 — Core Pipeline (manual trigger) ✓ DONE
- [x] `scrape_website.py` — wraps ai-marketing-claude `analyze_page.py` + `competitor_scanner.py`
- [x] `generate_audit_report.py` — Claude API, tier-aware JSON output, authoritative score recomputation
- [x] Full PDF via `generate_pdf_report.py` from ai-marketing-claude (path fix: 5 parent hops from `pipeline.py`)
- [x] Full Markdown report
- [x] Sample/censored PDF — `sample_report.py` with diagonal "SAMPLE" watermark, redaction bars, CTA page
- [x] Sample Markdown for proposal letter embedding (`🔒` blockquotes)
- [x] `--report-type both|full|sample` CLI flag
- [x] `--demo` mode for PDF testing without API calls
- [x] Resumable pipeline — `order.json` checkpoint after every phase; `--resume --order-id`
- [x] Live tested against `https://echoforge.biz/` — 29/100 (Grade F), 14 findings, cost $0.07
- Manual trigger: `python scripts/run_marketing_audit.py --url https://example.com --tier full`

### Sprint 2 — PDF Polish + Delivery Format
- [ ] Customise full report PDF with EchoForge branding (logo, colour palette, score gauges, bar charts)
- [ ] Build `audit_deliver.py` platform skill (Drive upload + Upwork/Fiverr message delivery)
- Sample PDF polish ✓ done in Sprint 1: EchoForge branding, correct margins, centred score pill, accurate redaction counts, mailto CTA link

### Sprint 3 — Upwork Integration
- Build `audit_order_listener.py` for Upwork
- Auto-trigger pipeline on new contract detection
- Deliver report link via Upwork contract message

### Sprint 4 — Proposal Letter + Outreach System
- Build proposal letter generator: takes sample MD + client context → full outreach email
- Outreach queue: scan prospect URLs → generate personalised sample → personalised cold email
- 3 reference sample audits (SaaS, service business, e-commerce) for portfolio

### Sprint 5 — Fiverr + Gmail Integration
- Build Fiverr listener via Gmail APScheduler
- Route Fiverr orders into same pipeline

### Sprint 6 — Auto-approve + Dashboard
- Enable AUTO_APPROVE after 20 validated deliveries
- Build /dashboard endpoint showing order pipeline + revenue
- Add monitoring alerts for failed audits

---

## Pre-Sprint Checklist

- [x] Clone ai-marketing-claude: cloned to `C:\Projects\AI\ai-marketing-claude`
- [x] `pip install reportlab` — installed; used by `sample_report.py` and `generate_pdf_report.py`
- [ ] Run install.sh to place skills in ~/.claude/skills/ (needed for Claude skill routing, not for API pipeline)
- [ ] Set `AI_MARKETING_CLAUDE_PATH=C:\Projects\AI\ai-marketing-claude` in `.env` (currently uses sibling heuristic)
- [ ] Create `/MarketingAudits/` Google Drive folder; add ID to `.env` as `GOOGLE_DRIVE_AUDIT_ROOT_ID`
- [ ] Create new Fiverr gig (see platform_metadata_v4.md Part A)
- [ ] Add marketing audit Project Catalog entries to Upwork profile
- [ ] Add new env vars to `.env.example`

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
