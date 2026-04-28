# Echoforge — Security Audit Venture
**Venture ID:** `security-audit`
**Status:** Active — Phases 1–5 live, full report pipeline complete
**Last Updated:** April 2026

---

## 1. Overview

### Positioning
A fully automated black-box and grey-box web application security audit service, targeting the underserved gap between cheap automated scan PDFs (~$500–2,000) and expensive enterprise manual pentests ($15,000–50,000+).

The product delivers confirmed, evidence-backed vulnerability reports — with real proof-of-concept exploitation, multi-finding attack chain narratives, and actionable remediation roadmaps — at a price accessible to SMBs, SaaS startups, freelancers, and compliance-driven teams.

### Target Market
- SMBs and SaaS startups needing annual compliance audits (SOC 2, ISO 27001, GDPR)
- Freelance developers who need to audit client sites before handoff
- Internal teams who want continuous testing without enterprise contracts
- Agencies offering security as an add-on to web/dev services

### Core Differentiators
1. **Confirmed exploitation** — every Critical/High finding ships with a PoC screenshot or request/response pair proving exploitability, not just pattern matching
2. **Attack chain correlation** — Claude API chains individual findings into multi-step attack narratives that single scanners never surface
3. **Authenticated depth** — Playwright-powered crawl behind login discovers IDOR, privilege escalation, and business logic flaws invisible to unauthenticated scanners
4. **Not a cheap scan PDF** — the output reads like an analyst wrote it, because the AI layer produces contextual, targeted remediation rather than generic advice

---

## 2. Audit Categories & Test Coverage

### 2.1 Reconnaissance & Attack Surface Mapping
- DNS enumeration (subdomains, zone transfers, MX/TXT records)
- Certificate transparency log parsing (crt.sh)
- Technology fingerprinting (framework, CMS, CDN, server)
- Open port and service discovery
- Exposed assets via internet-wide scan databases (Censys, Criminal IP)
- Leaked credentials and source code (GitHub dorks, HaveIBeenPwned)
- Historical URL corpus (Wayback Machine, Common Crawl)

### 2.2 Authentication & Session Management
- Password policy enforcement and brute-force resistance
- MFA presence and bypass attempts
- Session token entropy and predictability
- Session fixation, hijacking, and timeout behaviour
- OAuth/OIDC implementation flaws
- Password reset flow weaknesses (token expiry, enumeration)
- Cookie flags: `HttpOnly`, `Secure`, `SameSite`
- JWT: `alg:none`, weak secrets, missing expiry, signature bypass

### 2.3 Injection Vulnerabilities (OWASP Top 10)
- SQL Injection (classic, blind, time-based, out-of-band)
- NoSQL Injection
- Command Injection
- LDAP / XPath Injection
- Server-Side Template Injection (SSTI)
- XML External Entity (XXE)

### 2.4 Cross-Site Attacks & Client-Side
- Reflected XSS
- Stored XSS
- DOM-based XSS
- CSRF (token presence and strength)
- Clickjacking (X-Frame-Options / CSP frame-ancestors)
- Open Redirect

### 2.5 Authorization & Access Control
- IDOR (Insecure Direct Object References)
- Horizontal and vertical privilege escalation
- Forced browsing to unlinked admin/internal paths
- Mass assignment via unexpected API body fields
- API endpoint enumeration and undocumented route discovery

### 2.6 Security Misconfiguration
- HTTP security headers (CSP, HSTS, X-Content-Type-Options, Referrer-Policy)
- TLS/SSL configuration (weak ciphers, TLS 1.0/1.1, HSTS preload)
- Exposed admin interfaces (Kibana, phpMyAdmin, Swagger UI, Jenkins)
- Default credentials on discovered services
- Directory listing enabled
- Verbose error messages leaking stack traces or DB schema
- Exposed `.git`, `.env`, `backup.zip`, `config.php` files

### 2.7 API Security
- REST / GraphQL / gRPC endpoint discovery
- GraphQL introspection enabled
- Rate limiting absence
- Excessive data exposure (API returns more fields than the UI shows)
- Mass assignment via API body parameters

### 2.8 Infrastructure & Network Layer
- Open ports beyond 80/443
- Cloud storage misconfigurations (public S3 buckets, Azure blobs)
- Subdomain takeover (dangling DNS)
- Shodan/Censys-exposed services

### 2.9 Business Logic & Flow
- Price parameter tampering
- Workflow bypass (skipping payment steps)
- Race conditions (double-spend, duplicate accounts)
- Feature abuse (referral fraud, coupon stacking)

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI — Job API                        │
│         POST /audit  •  GET /audit/{id}  •  GET /report    │
└────────────────────────────┬────────────────────────────────┘
                             │
                     ┌───────▼────────┐
                     │  Redis Queue   │
                     │  (Celery)      │
                     └───────┬────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │         Pipeline Orchestrator        │
          │   (Celery Worker — phases as tasks)  │
          └──┬───────┬───────┬───────┬───────┬──┘
             │       │       │       │       │
         Phase 1  Phase 2  Phase 3  Phase 4  Phase 5
         (OSINT) (Surface)(Scanning)(Exploit)(Auth)
             │       │       │       │       │
          ┌──▼───────▼───────▼───────▼───────▼──┐
          │         PostgreSQL — findings DB      │
          │  + MinIO/S3 — artifacts (screenshots, │
          │    request logs, raw tool output)     │
          └─────────────────┬────────────────────┘
                            │
                   ┌────────▼────────┐
                   │   Claude API    │
                   │ (correlation,   │
                   │  scoring,       │
                   │  narrative)     │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │  PDF Generator  │
                   │  (WeasyPrint /  │
                   │  ReportLab)     │
                   └─────────────────┘
```

### Component Notes
- Each pipeline phase runs in an **isolated Docker container**, spun up per job and destroyed on completion
- The FastAPI layer handles tenant isolation — one customer's scan cannot reach another's job queue or artifact storage
- All active probe traffic is **rate-limited** and **logged with timestamps** (liability protection)
- Phase outputs write to PostgreSQL (structured findings JSON) and MinIO (raw artifacts)
- The Claude API call happens once, after all active phases complete, receiving the full aggregated findings JSON

---

## 4. Pipeline Phases

### Phase 1 — Passive OSINT Recon
*Zero traffic to the target. Runs entirely against third-party data sources.*

**Inputs:** Target domain/URL, scope boundary

**Tasks:**
- Subdomain enumeration via `subfinder` and `amass`
- Certificate transparency parsing via `crt.sh` API
- IP enrichment via Censys free API (ports, services, CVEs)
- IP enrichment fallback via `uncover` (aggregates Censys, Criminal IP, ZoomEye)
- Exposed database detection via LeakIX
- Historical URL corpus via `gau` + `waybackurls`
- DNS record analysis via `dnsx` (SPF/DMARC, zone transfer attempts)
- Public credential leak check via HaveIBeenPwned API
- GitHub dork search for org name / domain in public repos via `trufflehog`

**Outputs:** subdomain list, IP inventory, known CVE list, historical endpoint list, credential leak flags

---

### Phase 2 — Active Surface Mapping
*Low-noise probing. Confirms live assets and enumerates the attack surface.*

**Tasks:**
- Port and service discovery via `nmap` (SYN scan, service version detection)
- Live host confirmation and response fingerprinting via `httpx`
- Technology stack detection via `wappalyzer-cli`
- Directory and file fuzzing via `ffuf` (admin panels, backup files, config exposure)
- URL parameter discovery via `paramspider`
- Favicon hash matching and default login page detection via `nuclei` (recon templates)

**Outputs:** live host list, open port inventory, tech stack fingerprint, exposed path list, parameter corpus

---

### Phase 3 — Automated Vulnerability Scanning
*Broad, fast coverage across all known vulnerability patterns.*

**Tasks:**
- Full template scan via `nuclei` (9,000+ templates: CVEs, misconfigs, exposed panels, weak headers)
- Server misconfiguration and dangerous file detection via `nikto`
- Full TLS/SSL audit via `testssl.sh`
- HTTP security header grading via `securityheaders.com` API
- Cloud storage misconfiguration checks via `s3scanner`

**Outputs:** preliminary findings list with severity tags, header audit, TLS audit, cloud exposure flags

---

### Phase 4 — Active Exploit Testing
*The phase that separates this product from cheap scan PDFs. Findings are actively confirmed with real PoC payloads.*

**Status: Implemented (core tools live). Extended tools planned for v1.1.**

**Implemented (live):**
- Vulnerability template scan via `nuclei` (Phase 4 tags: sqli, xss, ssrf, ssti, traversal, injection, lfi, rfi, redirect)
- XSS confirmation via `dalfox` — PoC payload + affected parameter
- SQL injection detection via `sqlmap` (`--level=2 --risk=1`, `--technique=BEUS`)
- JWT security analysis (pure Python) — alg:none, weak signature, missing exp, sensitive claims in payload
- Open redirect detection — tests 17 common redirect param names; confirmed by 3xx + Location header
- Path traversal / LFI — tests path segments and file params with `../../etc/passwd` payloads; confirmed by content match
- SSTI detection — injects `{{7*7}}` / `${7*7}` / ERB / Mako payloads; confirmed by computed result in response
- All tools scoped to `scope_domain`; failures are non-fatal and never block delivery
- Gated to Professional and Agency tiers only; gracefully skipped on Starter

**Outputs:** confirmed exploits with PoC payload strings, affected parameters, tool attribution

---

### Phase 5 — Authenticated & Session Testing
*Requires customer-supplied credentials. Playwright drives a real browser session.*

**Tasks:**
- Full authenticated crawl to discover endpoints invisible to unauthenticated phases
- IDOR testing: extract all resource IDs seen during crawl, attempt cross-account access
- Session token entropy analysis via repeated login token captures
- Cookie flag audit: `HttpOnly`, `Secure`, `SameSite` enforcement
- Privilege escalation: replay requests with lower-privilege tokens
- Business logic testing: price parameter tampering, workflow step skipping
- Mass assignment: inject extra fields in API request bodies
- Rate limiting absence: detect missing throttling on auth endpoints

**Outputs:** authenticated findings with PoC, IDOR evidence, session entropy analysis, privilege escalation proof

---

### Phase 6 — AI Correlation & Report Generation
*Claude API receives the full aggregated findings JSON and produces the analyst-grade report.*

**Input data passed to Claude (all phases):** `phase1_recon`, `phase2_surface`, `phase3_vuln`, `phase4_exploit` — each summarised by a dedicated helper in `report_generator.py` (`_summarise_recon`, `_summarise_surface`, `_summarise_vulns`, `_summarise_exploits`).

**Tasks:**
- Deduplicate overlapping findings from different phases
- Group findings into attack chains (e.g. subdomain takeover + stored XSS = session hijack without interaction)
- Assign contextual CVSS 3.1 scores (base + temporal + environmental)
- Generate specific, targeted remediation guidance per finding (not generic advice)
- Write executive summary in plain language with business risk framing
- Produce risk-prioritised remediation roadmap ordered by exploitability × impact
- Generate full PDF report via WeasyPrint/ReportLab

**Report Structure:**
1. Executive Summary (plain-language risk posture for non-technical stakeholders)
2. Scope & Methodology
3. Findings (severity, description, evidence/PoC, CVSS score, remediation)
4. Attack Chain Narratives
5. Risk Register (prioritised by exploitability × impact)
6. Remediation Roadmap (quick wins vs. longer-term fixes)
7. Appendix (raw tool output, request/response logs)

---

## 5. Tool Stack

| Tool | Phase | Purpose | License | Cost |
|------|-------|---------|---------|------|
| `subfinder` | 1 | Subdomain enumeration | MIT | Free |
| `amass` | 1 | Deep subdomain recon | Apache 2.0 | Free |
| `dnsx` | 1 | DNS resolution and analysis | MIT | Free |
| `gau` | 1 | Historical URL collection | MIT | Free |
| `waybackurls` | 1 | Wayback Machine URLs | MIT | Free |
| `trufflehog` | 1 | Secret/credential leak detection | AGPL-3.0 | Free |
| Censys API | 1 | IP/host enrichment | Free tier | Free |
| `uncover` | 1 | Multi-source IP intel aggregation | MIT | Free |
| Criminal IP API | 1 | IP threat intelligence | Free tier | Free |
| LeakIX | 1 | Exposed database detection | Free | Free |
| HaveIBeenPwned API | 1 | Credential breach check | Subscription | ~$4/mo |
| `nmap` | 2 | Port and service discovery | GPL-2.0 | Free |
| `httpx` | 2 | HTTP fingerprinting | MIT | Free |
| `wappalyzer-cli` | 2 | Tech stack detection | MIT | Free |
| `ffuf` | 2, 4 | Directory/parameter fuzzing | MIT | Free |
| `paramspider` | 2 | URL parameter discovery | MIT | Free |
| `nuclei` | 3, 4 | Vulnerability scanning (9,000+ templates) | MIT | Free |
| `nikto` | 3 | Server misconfiguration scanning | GPL-2.0 | Free |
| `testssl.sh` | 3 | TLS/SSL audit | GPLv2 | Free |
| securityheaders.com API | 3 | HTTP header grading | Free tier | Free |
| `s3scanner` | 3 | Cloud storage misconfiguration | MIT | Free |
| `sqlmap` | 4 | SQL injection exploitation | GPL-2.0 | Free |
| `dalfox` | 4 | XSS confirmation | MIT | Free |
| `qsreplace` | 4 | Query string fuzzing helper | MIT | Free |
| `mitmproxy` | 4 | Traffic interception (XXE/SSTI) | MIT | Free |
| `jwt_tool` | 4 | JWT attack suite | MIT | Free |
| Playwright (Python) | 5 | Authenticated browser testing | Apache 2.0 | Free |
| FastAPI | Orchestration | Job API | MIT | Free |
| Celery + Redis | Orchestration | Task queue | BSD / BSD | Free |
| PostgreSQL | Storage | Findings database | PostgreSQL | Free |
| MinIO | Storage | Artifact storage (screenshots, logs) | AGPL-3.0 | Free |
| Claude API (Sonnet) | 6 | Correlation, narrative, scoring | Commercial | ~$0.60–1.20/report |
| WeasyPrint / ReportLab | 6 | PDF generation | BSD / BSD | Free |

---

## 6. Cost Per Report (COGS)

| Component | Calculation | Cost |
|-----------|-------------|------|
| Compute (EC2 t3.medium) | ~$0.04/hr × 3–4 hr average scan | $0.12–0.16 |
| HaveIBeenPwned API | $4/mo amortised over ~200 scans | ~$0.02 |
| Censys / Criminal IP | Free tier — no cost | $0.00 |
| Claude API (Sonnet) | ~80K input tokens + ~8K output | $0.60–1.20 |
| S3/MinIO artifact storage | ~50MB per scan × $0.023/GB | ~$0.001 |
| **Total COGS per report** | | **~$0.75–1.40** |

---

## 7. Pricing Recommendations

### Tier Structure

#### Starter — $49
*For individual developers and freelancers auditing a single site*
- Black-box only (no credentials required)
- 1 domain, up to 50 endpoints
- Phases 1–4 only (no authenticated testing)
- Report: executive summary + findings list with CVSS scores
- Turnaround: under 4 hours
- 1 free retest within 30 days

#### Professional — $149
*For startups and SMBs needing compliance-ready evidence*
- Grey-box (optional credentials for authenticated testing via Phase 5)
- 1 domain, unlimited endpoints
- Phases 1–4 always; Phase 5 runs when credentials supplied: authenticated crawl, IDOR, session entropy, cookie flags, privilege escalation, business logic, mass assignment, rate limiting
- Full PDF report: attack chains, PoC evidence, remediation roadmap
- Turnaround: under 6 hours
- 2 free retests within 60 days
- Compliance mapping: OWASP Top 10, GDPR, SOC 2 relevant controls

#### Agency — $349/site
*For agencies running audits for client handoffs*
- Everything in Professional
- Multi-subdomain scope (up to 5 subdomains)
- White-label report option (agency branding)
- Priority queue (under 3 hours)
- Dedicated retest window: 90 days
- Volume discount available (see below)

#### Continuous — $199/mo
*For teams who want ongoing validation, not a one-time snapshot*
- Full Professional scan run monthly
- Delta report: only new or changed findings since last scan
- Slack/email alert on critical finding discovery
- Trending dashboard: security posture over time
- Unlimited retests during subscription period

### Volume Pricing (Agency tier)
| Scans/month | Per-scan price |
|-------------|----------------|
| 1–4 | $349 |
| 5–9 | $299 |
| 10–19 | $249 |
| 20+ | $199 |

### Gross Margin Analysis
| Tier | Price | COGS | Gross Margin |
|------|-------|------|--------------|
| Starter | $49 | ~$1.20 | ~97.5% |
| Professional | $149 | ~$1.40 | ~99.1% |
| Agency | $349 | ~$1.60 | ~99.5% |
| Continuous | $199/mo | ~$1.40 | ~99.3% |

### Add-ons (future)
- API integration report (extra GraphQL/REST depth): +$49
- Manual review of AI-generated findings by a human analyst: +$99
- Compliance letter / auditor-ready attestation document: +$29
- Retest after remediation (outside free retest window): +$29

---

## 8. Competitive Positioning

| Vendor | Price | Manual? | Authenticated? | Turnaround |
|--------|-------|---------|----------------|------------|
| Cheap scan PDF | $500–2,000 | No | No | Hours |
| **Echoforge Starter** | **$49** | **AI-correlated** | **No** | **<4 hrs** |
| **Echoforge Professional** | **$149** | **AI-correlated** | **Yes** | **<6 hrs** |
| BreachLock Standard | $2,000 | Yes | Yes | Days |
| Cobalt.io | $2,500+/mo | Yes | Yes | Days–weeks |
| Manual boutique firm | $10,000+ | Yes | Yes | Weeks |

---

## 9. Echoforge Platform Integration Notes

### Naming Convention
Context file: `CLAUDE_SecurityAudit.md` (this file)
Venture directory: `ventures/security-audit/`

### Shared Platform Services
The following are shared with the Accessibility Audit Module (AAM) and the broader platform:
- FastAPI job API skeleton
- Celery + Redis orchestration layer
- PostgreSQL findings schema (extend with `audit_type` discriminator)
- Playwright browser automation patterns
- Claude API correlation pipeline
- WeasyPrint PDF generation
- MinIO artifact storage

### New Components (security-specific)
- Docker container images for each tool phase
- `nuclei` template management and update pipeline
- Rate-limit proxy wrapper (prevent inadvertent DoS during active phases)
- Scope validation middleware (ensure tools cannot probe out-of-scope hosts)
- PoC screenshot capture and evidence tagging system

### Freelance Platform Positioning (Fiverr)
- Fiverr: list as "I will perform a professional web security audit report"
  — Basic gig: $49 (Starter), Standard: $149 (Professional), Premium: $349 (Agency)
- Differentiate in listings with: turnaround time, PoC evidence, attack chain narrative, CVSS scores

---

## 10. Legal & Compliance Notes

- **Scope validation is non-negotiable**: the pipeline must verify the customer owns or has authorisation for the target domain before any active phase begins. No active scanning phase runs until `scope_verified = True` on the `SecurityAudit` record.
- All active probe traffic must be logged with timestamps for liability protection.
- Terms of service must explicitly state the customer is responsible for obtaining authorisation to test their target.
- A **Rules of Engagement checkbox** is required at order submission — `tos_accepted` must be `True` before the order is accepted. The acceptance timestamp is stored in `input_data.tos_accepted_at`.
- Shodan InternetDB is **not usable commercially** — use Censys free API and `uncover` instead.
- Data retention policy: raw artifacts (screenshots, traffic logs) should be purged after 30–90 days. Inform customers in ToS.

### 10.1 Scope Verification Flow (Implemented)

Scope verification uses **email confirmation as the primary method**, with DNS TXT as a secondary fallback available to the admin.

**Email verification (primary):**
1. On order creation, the API sends a one-click authorisation email containing a `scope_token` link.
2. Recipient selection priority:
   - `verification_email` if provided in the order form **and** its domain matches the target domain
   - `client_email` if its domain matches the target domain
   - Fallback: `admin@{domain}`, `webmaster@{domain}`, `security@{domain}` role addresses
3. The verification contact (`verification_email`) is a dedicated field in the order form, separate from `client_email` (the report delivery address). It must be an `@{target_domain}` address. Any email address at the domain is accepted — not restricted to role addresses.
4. Clicking the link calls `GET /api/ventures/security-audit/verify-email?token={scope_token}` (public, no auth). This sets `scope_verified=True`, `scope_method="email"`, and queues the Celery scan task automatically.
5. The admin can resend the email via `POST /orders/{audit_id}/resend-verification-email`.

**DNS TXT verification (secondary / admin fallback):**
- Record format: `_echoforge-verify.{domain}  TXT  "{scope_token}"`
- Checked via `POST /orders/{audit_id}/verify-scope`, which calls `scope_validator.verify_dns_txt()`.
- Available in the admin order detail panel (collapsed by default).

**Manual override (admin only):**
- `POST /orders/{audit_id}/approve-scope` — marks scope verified with `scope_method="manual"`. Use for testing or when a customer has provided a signed authorisation letter offline.

**Env vars required:**
- `PUBLIC_API_URL` — base URL for the verify link in emails (default: `https://api.planbadmin.com`)

### 10.2 Order Delivery Flow (Implemented)

```
Order created (scope_pending)
  → Verification email sent automatically
  → Customer clicks link → scope_verified → Celery scan task queued
  → Scan runs (phases 1–3 + Claude correlation + PDF)
  → PDF uploaded to Drive (orders or samples folder)
  → Status → review_pending
  → Admin reviews PDF in admin UI → Approve
  → Approval auto-triggers deliver_security_audit_job Celery task
  → Report emailed to client_email with Drive link
  → Status → delivered
```

**Drive folder routing:**
- `is_testing=True` (Demo Mode) → `DRIVE_SECURITY_SAMPLES_ID`
- `is_testing=False` (real order) → `DRIVE_SECURITY_ORDERS_ID`
- Both fall back to `DRIVE_SECURITY_ROOT_ID` if the specific var is not set.

**Env vars required for Drive upload:**
- `DRIVE_SECURITY_ORDERS_ID` — Google Drive folder ID for paid report PDFs
- `DRIVE_SECURITY_SAMPLES_ID` — Google Drive folder ID for demo/testing PDFs
- `DRIVE_SECURITY_ROOT_ID` — fallback parent folder

---

## 11. Human Tasks — What Requires a Human

The pipeline automates the scanning, correlation, and report generation. The following tasks cannot be automated and require human judgment or action at specific points in the workflow.

### 11.1 Before Going Live (One-Time Setup)

| Task | Why human | When |
|---|---|---|
| **Target ownership verification** | ✅ Implemented — email one-click verification (primary) + manual admin override. DNS TXT panel removed from UI. See Section 10.1. | Done |
| **echoforge.biz order page** | ✅ Spec written — see Section 13. Developer prompt provided for implementation. | Spec done — implementation pending |
| **Terms of Service review** | Legal language covering authorisation responsibility, liability limits, data retention, and Rules of Engagement must be written and reviewed. | Before MVP |
| **Tool Docker images hardening** | Each scanning tool (`nuclei`, `sqlmap`, `nmap`, etc.) runs in an isolated container. Container build, network isolation rules, and egress restrictions must be reviewed before production. | Before MVP |
| **Rate-limit tuning** | Automated scans can inadvertently cause service disruption. Humans must set per-host request rates and test against a staging target before production use. | Before MVP |
| **Fiverr listing creation** | Platform-specific listing text, portfolio samples, pricing packaging, and response templates must be written and published manually. | Before first orders |
| **Payment and billing setup** | Stripe or platform billing for paid orders is not in scope for the pipeline — must be configured manually. | Before first orders |

### 11.2 Per Order — Human Review Gate

Every report goes through a mandatory human review gate before delivery. This is not optional — the review catches:

| Review task | What to check |
|---|---|
| **False positive triage** | Automated scanners (especially `nuclei`) produce false positives. A human reviewer confirms that each Critical and High finding is genuinely exploitable before the report ships. |
| **PoC evidence quality** | Check that screenshots, request/response pairs, and payload strings are clear, correctly labelled, and sufficient to convince the client the finding is real. |
| **Attack chain narrative accuracy** | Claude's chain correlations are AI-generated — verify that the narrative is logically coherent and the chained steps are actually connected. |
| **CVSS score sanity check** | Spot-check 2–3 scores against the NVD or internal reference. AI scoring can be off when environmental factors are unusual. |
| **Client-appropriate language** | Ensure the executive summary reads at a non-technical level and the remediation steps are specific to the client's stack. |
| **Scope compliance check** | Confirm every finding relates to an in-scope host and no out-of-scope probing occurred. Check logs if in doubt. |

**Review SLA:** reviewer must action within 2 hours of the review notification email for Starter orders (4-hour turnaround) and 4 hours for Professional (6-hour turnaround).

### 11.3 Exceptional Situations — Escalation Required

These situations require human decision before the pipeline can continue:

| Situation | Required action |
|---|---|
| **Critical RCE or database dump discovered** | Pause delivery, notify the client immediately by phone/email before sending the report. Do not leave a live RCE unreported while waiting for normal review. |
| **Scan accidentally reaches out-of-scope host** | Halt the job. Document the incident, notify the client, and review scope validation logic before accepting new orders. |
| **Client disputes ownership during scan** | Cancel the job and refund. Do not complete an active scan on a disputed target under any circumstances. |
| **Tool produces output that looks like real credentials** | Do not include raw credentials in the report. Redact, notify the client, and advise immediate rotation. |
| **Scan triggers a client's WAF or IDS alert** | The client may be unaware you are scanning their system. Have a prepared communication template ready and contact them proactively. |

### 11.4 Post-Delivery

| Task | Why human |
|---|---|
| **Retest verification** | After the client claims to have remediated findings, a human must judge whether the retest evidence is convincing before marking the finding as resolved. |
| **Client Q&A** | Clients will have follow-up questions about findings, remediation steps, and compliance implications. These require human responses — especially for Professional and Agency tier clients. |
| **Compliance attestation letters** | Any document that serves as evidence for SOC 2, ISO 27001, or GDPR audits must be reviewed and signed off by a human before delivery. |

---

## 12. Roadmap

### MVP (Phase 1 launch) — Target: Q2 2026
- [x] Phases 1–3 pipeline (OSINT + surface mapping + automated scanning)
- [x] Claude API correlation and PDF report (Playwright-rendered, EchoForge branded)
- [x] Scope verification — email one-click (primary) + manual admin override (DNS panel removed)
- [x] Human review gate — admin reviews PDF before delivery; approval auto-triggers client email
- [x] Drive upload — orders → `DRIVE_SECURITY_ORDERS_ID`, demos → `DRIVE_SECURITY_SAMPLES_ID`
- [x] Drive permissions — explicit reader grant per `client_email` + anyone-with-link fallback
- [x] Claude token limit fix — 16K tokens + extended output beta + JSON repair for truncated responses
- [x] Admin UI — Security Audit venture card, order form, order detail, scope panel, review gate
- [x] Backend domain validation on `verification_email` (subdomain support)
- [x] Phase 4 core exploit testing — dalfox (XSS PoC) + sqlmap (SQLi detection); gated to pro/agency; Phase 4 findings wired into Claude correlation prompt (`_summarise_exploits`)
- [x] Professional tier live — Phases 1–4, confirmed XSS/SQLi PoC, full PDF report
- [ ] echoforge.biz public order page (`order-security/index.html`) — see Section 13
- [ ] Cloudflare Function proxy (`functions/api/security-audit/create-order.js`)
- [ ] Starter tier live on Fiverr ($49, black-box)

### v1.0
- [x] Phase 5 (Playwright authenticated testing — 8 tests: crawl, IDOR, session entropy, cookie flags, privilege escalation, business logic, mass assignment, rate limiting)
- [x] Runtime optimisations — concurrent Phase 3 tools, per-tool timeouts, dynamic Phase 5 crawl depth cap
- [x] Tests Performed section in PDF report — per-phase table covering all 5 phases
- [x] Phase 4 extended tools — nuclei exploit templates (sqli/xss/ssrf/ssti/lfi/rfi/redirect), JWT analysis, open redirect, path traversal/LFI, SSTI detection
- [x] Agency white-label branding — logo image + name injection in PDF header and footer via `white_label_name` / `white_label_logo_url` order fields
- [x] Multi-subdomain scope for Agency tier — Phase 3 and Phase 4 run against root + up to 4 live subdomains (5 total); findings merged and subdomain-labelled

### v1.5
- [ ] Continuous tier with monthly delta reports
- [ ] Slack/email alerting
- [ ] Compliance mapping overlays (OWASP, GDPR, SOC 2)

### v2.0
- [ ] Retest workflow
- [ ] Dashboard for security posture trending
- [ ] API endpoint for programmatic audit triggering (CI/CD integration)
- [ ] Volume pricing portal for agencies
