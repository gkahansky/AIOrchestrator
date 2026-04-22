# DevLog

Append a new row after every commit. Format: Date & Time (local, ISO 8601) | Jira Key | Commit ID (7 chars) | Description (why + what).

| Date & Time | Jira Key | Commit ID | Description |
|---|---|---|---|
| 2026-04-03 16:50 | | f40ccd8 | Fixed Etsy API list error response handling and tag truncation to 20 chars |
| 2026-04-03 16:57 | | 201faba | Filled all Etsy listing fields — shop section, AI disclosure, auto-renew |
| 2026-04-03 17:01 | | 30c0725 | Fixed job detail page — phase spinner, cancel button, scrollable data sections |
| 2026-04-03 17:17 | | 7068c0d | Fixed Phase 6 mockup/ZIP download from Drive — ephemeral containers can't rely on /tmp |
| 2026-04-03 17:36 | D-16 | d75f8df | Removed Phase 5 human review gate — Phase 4 now auto-chains to Phase 6 |
| 2026-04-03 17:47 | | d5b876c | Fixed themes endpoint — removed status filter, added Drive fallback |
| 2026-04-03 19:07 | | 8ca27f5 | Etsy Phase 7 promotion stub added |
| 2026-04-04 15:04 | D-18 | 5b59539 | Added public sample endpoints, Slack alerts, nurture emails, Fiverr parser, weekly digest |
| 2026-04-04 15:12 | | 25df011 | Added python-multipart to requirements for Form/File upload endpoints |
| 2026-04-04 15:19 | | 63825c5 | Fixed venture enum values in sample endpoints |
| 2026-04-04 15:26 | | 8797490 | Fixed Docker build — populate ai-marketing-claude submodule |
| 2026-04-04 15:33 | | eb2dd29 | Vendored ai-marketing-claude scripts as plain files, removed submodule |
| 2026-04-04 15:39 | | b80c693 | Added reportlab to requirements |
| 2026-04-04 21:31 | D-19 | 2cac676 | Fixed sample email delivery, Drive folder routing, job UUID navigation, Arabic font support |
| 2026-04-04 21:36 | | fd1fc38 | Fixed Drive uploads routing to correct EchoForge folders per venture |
| 2026-04-04 21:52 | | 3ba1cc4 | Added Slack alerts for new orders and review needed |
| 2026-04-04 22:12 | | e168719 | Added Testing checkbox to audit form; fixed Orders tab crash |
| 2026-04-04 22:26 | D-17 | 53af806 | Added multi-page BFS crawler to marketing audit — was homepage-only before |
| 2026-04-04 22:34 | | af297e1 | Fixed pipeline to upload to Drive before review gate; email client only after approval |
| 2026-04-05 05:59 | | 7457233 | Fixed sample email delivery and podcast sample 422 error |
| 2026-04-05 06:10 | | dcb1984 | Added openai to requirements — needed for Whisper transcription |
| 2026-04-05 06:13 | | 3c25f27 | Fixed delivery email to fall back to sample PDF Drive link for sample-only orders |
| 2026-04-05 06:14 | | 0808622 | Fixed demo=True handling in podcast pipeline when no audio file is provided |
| 2026-04-05 10:29 | AII-138 | cf0fe2d | Replaced URL input with file upload for podcast orders; added Drive OAuth logging |
| 2026-04-05 10:37 | | 3a0ced0 | Attempted to move Drive upload to worker (reverted — /tmp not shared between containers) |
| 2026-04-05 10:42 | AII-138 | bb05f21 | Fixed file access: audio must be uploaded to Drive in the web router, not the worker |
| 2026-04-05 10:49 | AII-138 | f076dc4 | Added proper error handling for audio upload failure and missing /tmp files |
| 2026-04-05 10:53 | AII-137 | 3642e14 | Fixed create_gdoc and drive_organise — both were hardcoded to service account, bypassing OAuth token |
| 2026-04-05 12:04 | AII-138 | 8aba884 | Added episode_title and host_name to podcast order form; fixed Google Doc sharing to be public link |
| 2026-04-05 12:20 | AII-138 | 5330919 | Added guest name and special instructions fields to podcast order form |
| 2026-04-05 14:00 | | 707cbb5 | Added DevLog.md, updated ROADMAP and CLAUDE.md files for D-20/D-21; added DevLog commit directive to root CLAUDE.md |
| 2026-04-05 14:30 | | 6ee51f7 | Replaced "Vercel" with "Cloudflare Pages" across CLAUDE.md, ROADMAP.md, src/aiplatform/CLAUDE.md — frontend is hosted on Cloudflare Pages |
| 2026-04-05 19:57 | | ace4c73 | Implemented Fiverr Gig Generator complete with platform webapp UI, backend endpoints, and cover image generation (H-08) |
| 2026-04-06 12:14 | | cc30cbb | Updated Fiverr Gig Generator with buyer requirements section |
| 2026-04-06 12:46 | | 20250ea | Updated Fiverr Gig Generator with strict length limits, package features, and audio length validation per tier via mutagen |
| 2026-04-06 13:41 | | 517aedd | Fixed Gig Generator package mappings (Title max 35 chars, Description max 100 chars) |
| 2026-04-06 13:41 |  | 12d95a4 | Fixed Gig Generator package mappings (Title max 35 chars, Description max 100 chars) |
| 2026-04-06 13:46 | | 85d8bf0 | Fixed FastAPI Pydantic schema stripping 'title' from Fiverr Gig Generator payload |
| 2026-04-06 15:58 | | 87892ea | Fixed UnicodeDecodeError in docker deployment caused by corrupted file encoding |
| 2026-04-06 15:40 | AII-0 | 80541d2 | Implemented system prompts editing UI in StrategyRoom and decoupled strings into platform registry markdown |
| 2026-04-06 16:30 | | 85d4399 | Fixed frontend ts build by removing unused roadmap import |
| 2026-04-06 16:33 | | b591314 | Corrected backend path to advisors.json in strategy router |
| 2026-04-07 13:20 | AII-XXX | 4105da6 | Fixed 500 error in sample accessibility route by directly initiating Job model with phase arguments instead of passing kwargs to upsert_job |
| 2026-04-07 14:06 | AII-XXX | e76bdf4 | Formatted accessibility audit report tables, direct WCAG mapped links, and removed lead-gen block |
| 2026-04-08 | AII-XXX | 0b41c37 | Fixed mobile sidebar transparency (missing surface-container-lowest in Tailwind config) and unreachable Sign Out (overflow-y-auto on nav) |
| 2026-04-08 14:35 |  | ee7a69b | Add cold outreach pipeline — lead discovery, A/B email, tracking, admin UI |
| 2026-04-08 14:41 |  | 01810c0 | Fix alembic revision chain — outreach migration must follow 0e7d1c3ae8ee not a7eb62fd41b3 |
| 2026-04-08 14:45 |  | 5506ca4 | Fix Marketing.tsx — remove unused useMutation import (TS error broke Cloudflare build) |
| 2026-04-08 15:34 |  | 46ffbbf | Marketing module v2 — contacts CRM, unsubscribe, spam guard, prompt review flow |
| 2026-04-08 15:43 |  | 12e455f | Replace 'EchoForge' with 'us' on unsubscribe page for brand-agnostic messaging |
| 2026-04-08 16:04 |  | e6b9697 | Show live search progress banner while find-leads task runs in background |
| 2026-04-08 16:14 |  | b3d72d1 | Expand lead discovery to 6 channels: Reddit, Google, LinkedIn, HN, IndieHackers, Fiverr |
| 2026-04-08 16:14 |  | bac3538 | Update marketing_module.md to document all 7 lead discovery channels |
| 2026-04-08 17:39 | AII-138 | d5572a8 | Use Insightful Clarity design for Marketing Audit PDF and add Open Document buttons to preview pages |
| 2026-04-09 10:02 |  | a650374 | Add Roadmap tab to Strategy Room with backlog, WIP, drag-drop, and recently done |
| 2026-04-09 10:23 |  | 2bfe0c7 | Add missing alembic migrations for contacts and contact_messages tables |
| 2026-04-09 10:25 |  | ff630ea | Fix migration: convert roadmap status enum to varchar before updating values |
| 2026-04-09 10:43 |  | dec38c3 | Roadmap: WIP section on top, backlog below; show ID in edit form |
| 2026-04-09 10:53 |  | cc19798 | Activate Advisory Board — real LLM calls, remove duplicates, wire architect webhook |
| 2026-04-09 13:07 |  | 0a0f160 | Strategy Room redesign — Architectural Curator design system + full agent interactivity (chat, proposals per agent, prompt editor, manual triggers) |
| 2026-04-09 13:41 |  | dcb6fa6 | AII-XXX Update docs â€” DevLog fix, ROADMAP done entries D-22â€“D-25, Pipeline Status table |
| 2026-04-09 14:26 |  | 6d8585e | Fix IndentationError in worker.py â€” two misindented crm_ops imports crashed uvicorn on startup |
| 2026-04-09 14:49 |  | b8eac57 | Strategy Room UX â€” larger prompt editor, skill spinners, roadmap redesign |
| 2026-04-09 15:45 |  | 6bbc07d | Fix advisor trigger: sync execution, content type bug, run history panel |
| 2026-04-09 15:54 |  | ba46e09 | Add advisor diagnostics endpoint and always-visible run history panel |
| 2026-04-09 15:58 |  | 987e872 | Fix proposals endpoints â€” remove Pydantic response_model causing 500 on JSONB content |
| 2026-04-09 |  | (pending) | Multi-platform outreach — add platform field to campaigns, platform_username to leads, 6-platform compose_outreach skill, platform-aware router and Marketing UI |
| 2026-04-10 12:38 |  | 660be9c | Support multiple allowed emails via ALLOWED_EMAILS env var |
| 2026-04-10 12:41 |  | ece88ea | Rebrand AI-Infra â†’ Plan B in sidebar, login page, and browser title |
| 2026-04-11 11:26 |  | 991794a | Multi-platform outreach â€” extend campaigns from email-only to 6 platforms |
| 2026-04-11 18:29 |  | f6d6fc1 | Redirect to login with message on session expiry |
| 2026-04-11 20:00 |  | 454226f | Disable fiverr-email-check beat task â€” gmail.modify scope not granted |
| 2026-04-14 08:51 |  | ea59a62 | Add JobLinks component â€” Drive doc/folder buttons on all order lists and detail page |
| 2026-04-14 08:57 |  | 9eaf780 | Fix Drive upload silent failure + email delivery for marketing audit |
| 2026-04-14 09:01 |  | 7d66906 | Add Drive upload diagnostics â€” full traceback + auth path logging |
| 2026-04-14 09:06 |  | 779a914 | Fix silent credential logging â€” use print() in _materialise_google_credentials |
| 2026-04-14 09:47 |  | 5ca9ee7 | Change default report_type to 'full' in new audit order form |
| 2026-04-14 09:51 |  | cf83439 | Fix blank first page in audit PDF â€” remove sticky header |
| 2026-04-14 10:06 |  | c8341aa | Fix audit findings display â€” render Severity/Finding labels instead of raw dict string |
| 2026-04-14 10:07 |  | 31c7cb3 | Update DevLog for c8341aa — audit findings display fix |
| 2026-04-14 10:09 |  | ec4fb4c | Wire accessibility PDF into premium marketing audit pipeline |
| 2026-04-14 17:55 |  | 9f2a254 | Fix Roadmap features dropdown blank — list_features and create_feature returned raw ORM objects that detach/expire after session close; serialize to dicts inside the with block |
| 2026-04-14 18:13 |  | a180dd9 | Fix edit form not closing after Save Changes on roadmap item |
| 2026-04-14 18:19 |  | dc234b0 | Split audit findings into Problem / Impact / Resolution |
| 2026-04-14 18:24 |  | 85bdb09 | Fix audit PDF layout â€” margins, section order, executive summary title |
| 2026-04-14 19:46 |  | 56c57fb | Add Security Audit venture to root CLAUDE.md + human tasks section |
| 2026-04-14 20:30 |  |  | Extract accessibility_audit into proper venture — config.py + pipeline.py + CLAUDE.md; worker.py tasks thinned to single-line dispatchers |
| 2026-04-15 08:01 |  | 93f7e26 | Extract accessibility_audit into proper venture structure |
| 2026-04-15 08:30 |  |  | Security Audit venture infrastructure — DB model, 4 platform skills, pipeline, router, Celery tasks, PDF template, frontend page with scope verification flow |
| 2026-04-15 10:12 |  | 46f3a7c | Security Audit venture — full infrastructure (MVP Phases 1-3) |
| 2026-04-15 11:30 |  |  | Security Audit phase C — ToS checkbox + dev notes, Censys bearer token fix, Drive env var alignment, 30-day retention cleanup skill + admin endpoint + Settings Maintenance tab |
| 2026-04-15 14:33 |  | 4ceb0c0 | Security Audit phase C â€” ToS enforcement, Censys fix, Drive cleanup |
| 2026-04-15 14:49 |  | a070b87 | Fix alembic env.py to use DATABASE_PUBLIC_URL for local runs |
| 2026-04-15 14:58 |  | 5bb1059 | Fix startup crash â€” make dns import lazy in scope_validator |
| 2026-04-15 15:15 |  | b19580e | Fix TS6133 â€” remove unused pendingAuditId state in SecurityAudit |
| 2026-04-15 15:27 |  | 6919b69 | Trigger Cloudflare Pages rebuild |
| 2026-04-15 15:51 |  | 4d05386 | Add wrangler.toml and GitHub Actions deploy workflow for frontend |
| 2026-04-15 15:55 |  | aac9b17 | Test GitHub Actions deploy â€” update Settings subtitle |
| 2026-04-15 15:57 |  | 26faa1f | Add workflow_dispatch to deploy-frontend for manual triggering |
| 2026-04-15 19:26 |  | e6553ab | Security Audit UX â€” move to Ventures page, fix button color |
| 2026-04-15 19:38 |  | fdf7981 | Fix security audit tasks missing from webapp worker re-export shim |
| 2026-04-15 19:48 |  | bca0765 | Fix null byte crash in security audit pipeline |
| 2026-04-15 19:55 |  | 45938f3 | Add email scope verification â€” send one-click auth link to admin/webmaster/security role addresses on order create |
| 2026-04-15 19:57 |  | 5a9a183 | Fix review panel â€” move Drive links into review gate, add folder button, show error when Drive not configured |
| 2026-04-15 19:59 |  | cf03647 | Fix generic jobs approve endpoint â€” handle security_audit (approve-only, no Celery task; delivery is a separate step) |
| 2026-04-15 20:09 |  | b17303e | Security audit â€” auto-deliver on approval, degrade gracefully without Drive link, add delivered status UI |
| 2026-04-15 20:11 |  | ad1b408 | Security audit â€” route Drive upload to samples folder for demo orders, orders folder for paid scans |
| 2026-04-15 20:15 |  | 53fb9b3 | Scope verification email â€” send to client_email if domain matches, else fall back to role addresses |
| 2026-04-15 20:17 |  | 7937f92 | Add verification_email field to order form â€” any @targetdomain address, with inline domain validation |
| 2026-04-16 07:52 |  | 9f7bfc7 | Update Security Audit CLAUDE.md â€” document implemented scope verification and delivery flow |

| 2026-04-16 08:31 |  | 0037a18 | Security audit P1 fixes — tier enum validation, backend email domain check, 30-day Celery retention task, credential masking in logs |
| 2026-04-16 08:35 |  | 61d6492 | Merge claude/recursing-cori into main — all four P1 security audit gap fixes |
| 2026-04-16 | | | Security audit P2 features — critical finding alert, retest workflow, OWASP/GDPR/SOC 2 compliance mapping per finding || 2026-04-16 12:29 |  | aaab14b | Fix 4 security audit issues: Claude token limit, domain validation, remove DNS panel, Drive read permissions |
| 2026-04-16 14:11 |  | 48031de | Fix Drive share â€” retry with sendNotificationEmail=True for non-Google accounts |
| 2026-04-16 14:17 |  | 8f3e271 | Fix Drive share retry â€” check exc.content bytes not exc.reason for invalidSharingRequest |
| 2026-04-16 14:37 |  | 46c7e61 | Add Cloudflare redirect: /docs/security-audit-tos â†’ echoforge.biz ToS page |
| 2026-04-16 14:46 |  | c4ab13b | Delivery emails â€” attach PDF directly, remove Drive share links |
## [runtime-opt] Optimize scan timeouts + Phase 3 parallelism + adaptive Phase 5 crawl
- Added subprocess timeouts: nuclei 15min, nmap 5min, nikto 10min, testssl 8min, sqlmap 15min, dalfox 8min. Timeout produces Info finding rather than crash.
- Parallelized Phase 3 tools with ThreadPoolExecutor(max_workers=4) — cuts worst-case Phase 3 from ~40min to ~15min
- Phase 5 crawl now adapts page cap based on measured load time: >5s→15 pages, >3s→30 pages, else 60 pages
| 2026-04-17 14:50 |  | c93d717 | Add Tests Performed section to security report â€” per-phase table with test type, result, and issue count |
| 2026-04-17 14:54 |  | a0464fb | Add Phase 5 rows to Tests Performed table; update CLAUDE.md to reflect Phases 1â€“5 complete |
| 2026-04-17 15:01 |  | 4b73107 | Phase 4 extended tools â€” nuclei exploit templates, JWT analysis, open redirect, path traversal, SSTI |
| 2026-04-17 15:03 |  | 34420d8 | Agency white-label branding â€” logo + name injection in PDF header and footer |
| 2026-04-17 15:04 |  | 0b02492 | Multi-subdomain scope for Agency tier â€” Phase 3 and Phase 4 run against root + up to 4 live subdomains |
| 2026-04-17 15:04 |  | 704bd2d | Update security audit CLAUDE.md â€” v1.0 complete, all Phase 4 extended tools and Agency features live |
| 2026-04-18 09:57 |  | 57bc03b | Market Research venture â€” full implementation (D-26) |
| 2026-04-18 10:14 |  | ab4293d | Fix Alembic duplicate revision ID â€” rename market_research migration to d1e2f3a4b5c6 |
| 2026-04-18 10:20 |  | 976e26a | Fix Alembic multiple heads â€” chain market_research after security_audit retest |
| 2026-04-18 10:27 |  | 1eba2b2 | Support multiple env var names for xAI/Grok API key |
| 2026-04-18 10:32 |  | c51dbb1 | Fix market_research pipeline imports â€” drop src. prefix |
| 2026-04-18 10:38 |  | 9cc56e6 | Fix market_research pipeline â€” use Playwright PDF + correct drive_write signature |
| 2026-04-18 10:43 |  | e2129e4 | Fix Gemini model + graceful Qdrant degradation |
| 2026-04-18 10:50 |  | b679be6 | Market Research UI fixes + Adjust & Rerun feature |
| 2026-04-18 10:55 |  | 0ec2a3e | Market research: skip Drive upload gracefully when no folder ID configured |
| 2026-04-18 16:12 |  | a8a25f4 | Market research: AI-generated title, correct Drive folder, Drive link in email |
| 2026-04-18 16:17 |  | e5a3358 | Gig Generator: add Security Audit venture config |
| 2026-04-18 16:25 |  | a2665fb | Gig Generator: use We/Our voice in all generated copy |
| 2026-04-18 17:00 |  | (pending) | Docs update — create market_research CLAUDE.md, update root CLAUDE.md + ToolStack.MD; create updateprojdocs skill |
| 2026-04-18 21:15 |  | cb5a1a0 | docs: update project docs â€” Market Research venture + updateprojdocs skill |
| 2026-04-18 21:27 |  | 65ad52a | Campaign Manager â€” full implementation |
| 2026-04-19 10:00 |  | (pending) | Campaign Manager fixes — add PATCH /prompt endpoint, fix Gemini safety filter (BLOCK_ONLY_HIGH), stronger no-text directive for ad creatives, inline prompt editor in Creative Lab |
| 2026-04-19 20:23 |  | ceba302 | Campaign Manager fixes â€” prompt editor + image generation improvements |
| 2026-04-19 21:43 |  | a7da328 | Campaign Manager: Save & Regenerate button in Creative Lab |
| 2026-04-20 17:22 |  | c25948d | Market Research: add Office file format support for RAG uploads |
| 2026-04-20 17:28 |  | e5e3b55 | Market Research: fix SyntaxError, missing title in detail, add retry |
| 2026-04-20 17:38 |  | e465d1c | Market Research: fix drawer not opening + Retry button always visible |
| 2026-04-20 19:00 |  | dee9334 | Fix Gemini Imagen safety filter â€” revert to BLOCK_LOW_AND_ABOVE |
| 2026-04-21 10:26 |  | da44d34 | Market Research: render report as styled markdown with proper tables |
| 2026-04-21 11:59 |  | 321c3d5 | Market Research: agentic work-package pipeline (v2) |
| 2026-04-21 12:02 |  | f505b36 | docs: update project docs — Market Research v2 agentic pipeline |
| 2026-04-21 12:07 |  | f369ddb | Commit uncommitted scripts, feature designs, and venture docs |
| 2026-04-21 12:26 |  | 148ed9f | Fix market research timeout (180s per package) and replace deprecated Gemini model with gemini-2.0-flash-001 |
| 2026-04-21 13:25 |  | d2fad0d | Broaden retry eligibility to all in-progress statuses — stuck sessions in any pipeline stage can now be retried |
| 2026-04-21 13:36 |  | a188f82 | Add Celery Beat watchdog task — auto-retries market research sessions stuck in-progress for >30 minutes |
| 2026-04-21 15:35 |  | bf52fa1 | Fix report truncation — replace single-LLM stitch call with sequential Python assembly; exec summary is a separate focused call |
| 2026-04-22 | | (pending) | Market Research V3 — section-based pipeline with fixed section library, per-section 2-round critic loop, citation enforcement, cross-module reference context, and section-level status UI |
