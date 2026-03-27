# Platform Roadmap
## Echoforge — AI Business Orchestrator

> **How to use this file**
> Add any new idea here before building it. Assign a type and priority immediately.
> Review and re-prioritise weekly. Claude Code reads this file as part of platform context —
> keep descriptions specific enough that the agent understands scope without needing to ask.
>
> **Types:** `Venture` = standalone revenue-generating service | `System` = shared platform capability
> **Priority:** `urgent` = blocking current sprint | `high` = next sprint | `medium` = next 4 weeks | `low` = backlog

---

## Legend

| Field | Values |
|---|---|
| **Type** | `Venture` / `System` |
| **Status** | `idea` → `planned` → `in-progress` → `done` |
| **Priority** | `urgent` / `high` / `medium` / `low` |

---

## 🔴 Urgent

| # | Name | Type | Status | Description |
|---|---|---|---|---|
| U-01 | Core Podcast Pipeline — Sprint 1 & 2 | Venture | `done` | Manual trigger pipeline: audio → transcription (Whisper) → Claude content generation → Google Doc + full PDF + sample PDF (watermarked, redacted sections, CTA). `--demo` mode for testing without audio. Venture: `content_studio`. |
| U-02 | Marketing Audit Pipeline — Sprint 1 | Venture | `done` | Manual trigger pipeline complete and live-tested against echoforge.biz. See D-09 in Done table. |
| U-03 | Project Management Integration | System | `done` | ClickUp workspace live: 5 spaces, 53 tasks seeded from ROADMAP.md, custom fields per list. Skill: `comms/update_project_board.py`. Scripts: `seed_clickup_from_roadmap.py`, `sync_clickup_to_roadmap.py`, `setup_clickup_workspace.py`, `update_task.py`, `retry_pending_updates.py`. 4-way sync: ClickUp + ROADMAP.md + venture CLAUDE.md + session log on every status change. Auto git push on done. |

---

## 🟠 High

| # | Name | Type | Status | Description |
|---|---|---|---|---|
| H-01 | Podcast Pipeline — Sprint 3: Upwork Delivery | Venture | `planned` | Full Upwork integration: OAuth2 non-expiring token, polling, delivery via contract message. Venture: `content_studio`. |
| H-02 | Marketing Audit — Sprint 2: PDF Polish | Venture | `done` | Full PDF now renders: dimension details, copy examples, 30-day roadmap, competitor table (word-wrapped), 5-level status thresholds (Excellent/Strong/Fair/Needs Work/Critical). Score consistency fixed: temperature=0 + unified scoring instructions so dimension scores are identical across all tiers for the same site. Branding updated to Echoforge. Page promises locked: Snapshot 5–10 / Full 10–15 / Premium 15–20 pages. Remaining: Echoforge logo + visual header in PDF, `audit_deliver.py` (Drive upload + marketplace delivery). Venture: `marketing_audit`. |
| H-03 | Upwork Order Listener — Podcast | System | `planned` | GraphQL API polling every 5 min for new podcast_notes contracts. Routes to core pipeline on detection. Part of `marketplace/upwork_listener.py`. |
| H-04 | Upwork Order Listener — Marketing Audit | System | `planned` | Same polling mechanism as H-03 but routes to audit pipeline. Separate order form parsing for URL + tier. Separate skill: `marketplace/audit_order_listener.py`. |
| H-05 | Human Review Gate | System | `planned` | 30-min review window with email + Slack alert. `/orders/{id}/approve` FastAPI endpoint. Auto-approve flag (`AUTO_APPROVE=false`) per venture after 20 validated orders. |
| H-06 | Podcast Sample Generator | Venture | `done` | `--demo` mode in `run_content_studio.py` generates full + sample PDFs from canned content (tech/business/marketing). `--pdf-only` regenerates PDFs from any completed order. Sample PDF: watermark, timestamps/guest bio in full, all other sections redacted with CTA. |
| H-07 | Gemini Imagen 4 Integration | System | `done` | Gemini Imagen 4 (`imagen-4.0-generate-001`) live as standard-tier image tool. DALL-E 3 demoted to fallback. Mockup skill (`create_mockup.py`) rewritten — uses `gemini-2.5-flash-image` (image-in, image-out): actual artwork PNG passed as input so mockups are visually consistent with the real artwork. Pillow composite retained as fallback. Fully tested end-to-end. See D-11. |
| H-08 | Gig Generator — Fiverr | System | `planned` | Automatically generate and upload new Fiverr gigs for any venture. Given a venture config + service tier, generates gig title, description, FAQ, pricing packages, and cover image via `media/generate_image.py`. Uploads gig as a draft via Fiverr API. Human reviews draft in Fiverr dashboard and publishes manually. Skill: `marketplace/generate_fiverr_gig.py`. Reusable across all ventures — venture context injected at call time. |
| H-09 | Management App | System | `planned` | Web interface for monitoring and controlling all ventures. Sections: venture status overview (active/paused/on-hold), billing and API cost summary, open orders per venture with pipeline stage, and a product generation panel — supply customer or test data for any venture and trigger a full pipeline run from the UI. Built on FastAPI + lightweight React frontend. Hosted on Railway. Reads from existing `/dashboard` and `/finances` endpoints; adds order-trigger and pipeline-control endpoints. Complements but does not replace the project management board (U-03). |
| H-10 | Promotion Agent | System | `planned` | Automated venture promotion across relevant platforms. For podcast service: post in podcast communities (Reddit r/podcasting, Facebook groups), LinkedIn outreach. For marketing audit: LinkedIn cold outreach with 3 specific homepage findings snippet. For Etsy: Pinterest pins + social queue. Orchestrated by a dedicated Comms sub-agent. Skill: `comms/promote_venture.py`. Rate-limited, logged, de-duplicated per platform. |

---

## 🟡 Medium

| # | Name | Type | Status | Description |
|---|---|---|---|---|
| M-01 | Podcast Pipeline — Sprint 3: Upwork Delivery | Venture | `planned` | Full Upwork integration: OAuth2 non-expiring token, polling, delivery via contract message. Venture: `podcast_notes`. |
| M-02 | Marketing Audit — Sprint 3: Upwork Integration | Venture | `planned` | Upwork order detection + automated delivery of PDF report link via contract message. Venture: `marketing_audit`. |
| M-03 | Podcast Add-on: Brand Voice Guide | Venture | `done` | Analyse 2–3 episode transcripts → structured Brand Voice Guide (tone, vocabulary, sentence style). Cached as JSON per client for reuse. Skill: `generate_brand_voice.py`. Price: $79. |
| M-04 | Podcast Add-on: Episode Promotional Copy | Venture | `done` | Platform description + audiogram caption + newsletter teaser + LinkedIn post from one episode. Skill: `generate_promo_copy.py`. Price: $39. |
| M-05 | Podcast Add-on: 30-Day Social Calendar | Venture | `planned` | 30 ready-to-post pieces from 4 episodes using `market-social/SKILL.md` with podcast context prefix. Skill: `generate_social_calendar.py`. Price: $79. |
| M-06 | Podcast Add-on: Listener Email Sequence | Venture | `planned` | 5-email nurture sequence for new subscribers using `market-emails/SKILL.md`. Skill: `generate_email_sequence.py`. Price: $99. |
| M-07 | Fiverr Order Listener — Podcast | System | `planned` | Gmail polling via APScheduler every 5 min. Parses order confirmation email for audio link. Skill: `marketplace/fiverr_listener.py`. |
| M-08 | Fiverr Order Listener — Marketing Audit | System | `planned` | Same Gmail mechanism as M-07. Parses website URL + tier from requirements form. Skill: `marketplace/audit_fiverr_listener.py`. |
| M-09 | Dashboard Endpoint | System | `planned` | FastAPI `/dashboard` showing: active orders, pipeline status, revenue totals, cost totals, failed jobs. Per-venture filters. Railway hosted. |
| M-10 | Marketing Audit — Sample Cold Outreach | Venture | `planned` | Generate 3 sample audit reports (SaaS / service / e-commerce). Outreach queue: scan prospect homepage → generate 3 specific findings snippet → personalise cold email template. |
| M-11 | Podcast Add-on: Guest Outreach Templates | Venture | `planned` | 3 email templates (cold/warm/follow-up) for pitching guests. Skill: `generate_guest_outreach.py`. Price: $29. |
| M-12 | Podcast Add-on: Show Landing Page Audit | Venture | `planned` | Scored CRO audit of podcast website/episode page using `market-landing/SKILL.md` with podcast context prefix. Price: $49. |
| M-13 | Financial Tracker | System | `planned` | Unified income vs expenses dashboard across all ventures. Log all API costs (OpenAI, Claude, ElevenLabs, Runway, etc.), platform fees (Etsy, Fiverr commission), and revenue (Upwork, Fiverr, Etsy sales). Extends existing `finance/log_cost.py` and `finance/log_revenue.py` skills. Adds a `/finances` FastAPI endpoint showing: monthly P&L per venture, running totals, cost-per-order, revenue trend. Export to Google Sheets optional. |
| M-14 | Content Creation Agent | System | `planned` | Reusable agent for generating marketing collateral: website landing pages, logo concepts (SVG), banner images, gig cover images, social profile assets. Built on top of existing `media/generate_image.py` and a new `media/generate_svg_asset.py`. Triggered on-demand per venture or on new gig creation. Output stored in `/platform/brand/{venture}/` in Drive. |
| M-15 | Copywriting Services — Jasper Integration | Venture | `idea` | Standalone copywriting service powered by Jasper AI for long-form and brand copy: landing pages, email sequences, ad copy, product descriptions. Jasper handles brand voice consistency and long-form generation; platform pipeline handles intake, packaging, review gate, and delivery. Venture: `copywriting`. Needs: Jasper API access, new `CLAUDE_copywriting.md`, new `media/generate_copy_jasper.py` skill. Research Jasper API tier requirements before committing. |
| M-16 | Lead Generation System | System | `planned` | Venture-aware lead generation pipeline. Per-venture config defines target audience profile, search signals, and offer sheet template. Pipeline: crawl target platforms (LinkedIn, Reddit, directories, Upwork search) → score leads by fit → generate a personalised observation from their public presence (website/podcast/profile) → assemble a tailored one-page offer sheet PDF → queue for outreach. Skills: `research/find_leads.py`, `media/generate_offer_sheet.py`. Output stored in `/platform/leads/{venture}/` in Drive. Rate-limited and de-duplicated per platform. |

---

## 🔵 Low

| # | Name | Type | Status | Description |
|---|---|---|---|---|
| L-01 | Podcast Pipeline — Sprint 5: Freelancer.com | Venture | `planned` | Freelancer SDK integration (`freelancersdk` on PyPI). Webhook: `project.awarded` event → FastAPI `/webhooks/freelancer`. Venture: `podcast_notes`. Apply for API access first. |
| L-02 | Podcast Add-on: Competitive Show Analysis | Venture | `idea` | Benchmark vs 3 competing shows using `market-competitors/SKILL.md`. Skill: `generate_competitive_analysis.py`. Price: $79. |
| L-03 | Podcast Add-on: Launch Playbook | Venture | `idea` | Full launch plan for new/relaunching shows using `market-launch/SKILL.md`. 8-week pre-launch timeline, guest framework, social calendar, directory checklist. Skill: `generate_launch_playbook.py`. Price: $149. |
| L-04 | GEO / AI Search Optimisation Service | Venture | `idea` | Standalone service: audit any site for AI search visibility (ChatGPT, Claude, Perplexity, Gemini). Based on `zubair-trabzada/geo-seo-claude` repo — same author as ai-marketing-claude, same architecture pattern. Research and evaluate before committing. |
| L-05 | Content Channels — Venture B | Venture | `idea` | Faceless YouTube/TikTok/Instagram channel system. Channel = config entry, not new codebase. First channel: "Project Post-Mortem" (tech failure investigations, true-crime style). Needs: Veo/Runway API access, ElevenLabs, TikTok Content Posting API (1–4 wk approval), Instagram Graph API (1–2 wk). |
| L-06 | Etsy Digital Image Shop — Venture A | Venture | `on-hold` | Automated Etsy shop selling AI-generated digital wall art. **Blocked:** Etsy API key pending approval. Gemini Imagen 4 artwork + mockup generation live and tested. Resume Sprint 1 once Etsy API key is confirmed. |
| L-07 | Auto-Approve System | System | `planned` | After 20 validated deliveries per venture, flip `AUTO_APPROVE=true`. Separate flag per venture + per add-on type. Triggered via admin endpoint, not manually. |
| L-08 | LangGraph Orchestration | System | `idea` | Replace current sequential pipeline calls with LangGraph for stateful, resumable workflows. Registered in platform tech stack but not yet built. Only implement when pipeline complexity justifies it (>5 phases with branching). |
| L-09 | Redis Pub/Sub for Inter-Agent Events | System | `idea` | Currently agents communicate via function calls. Redis pub/sub would enable event-driven architecture: e.g., "transcription_complete" event triggers content generation without tight coupling. Prerequisite for parallel multi-venture operation at scale. |
| L-10 | Qdrant Long-Term Memory | System | `idea` | Per-venture namespaced memory for research history, brand guidelines, recurring client preferences. Currently not built — Redis used for short-term state only. Implement when a venture needs cross-session context (e.g., returning podcast client brand voice reuse). |
| L-11 | AI Sales Team Integration | System | `idea` | `zubair-trabzada/ai-sales-team-claude` — same architecture as ai-marketing-claude. 14 skills: prospect research, BANT/MEDDIC qualify, decision-maker identification, outreach sequences, proposal generation, PDF pipeline reports. Evaluate as a platform-level prospecting layer across all ventures. |
| L-12 | Outreach Automation | System | `idea` | Systematic cold outreach pipeline: crawl target list → generate personalised observation from their website/podcast → send via platform-native messaging (Upwork InMail / LinkedIn DM). Rate-limited, logged per prospect, de-duplicated. |

---

## ✅ Done

| # | Name | Type | Completed | Notes |
|---|---|---|---|---|
| D-01 | Echoforge Landing Page | System | 2026-03 | Deployed to Cloudflare Pages at echoforge.biz. Two services: podcast content + marketing audit. Platform cards live with Upwork + Fiverr links. |
| D-02 | Brand Identity & Logo System | System | 2026-03 | 3D glossy eye icon in warm terracotta palette. Wordmark: "hey" ink / "eye" terracotta. Favicon, app icon, horizontal lockup. Files in `/echoforge-landing/`. |
| D-03 | Platform CLAUDE.md Hierarchy | System | 2026-03 | Root `/CLAUDE_root.md` + venture-level CLAUDE.md per venture. VS Code scoping: open from venture directory. |
| D-04 | Podcast Venture CLAUDE.md | Venture | 2026-03 | Enhanced v2: core pipeline + 8 marketing add-ons specced. ai-marketing-claude integration pattern documented. |
| D-05 | Marketing Audit Venture CLAUDE.md | Venture | 2026-03 | Full 6-sprint roadmap, scoring framework, pipeline phases, skills map, env vars. |
| D-06 | Platform Metadata v4 | System | 2026-03 | Fiverr + Upwork gig copy for both podcast and marketing audit services. Outreach templates included. |
| D-07 | Upwork Profile Live (Echoforge) | Venture | `pending` | New account to be created today. Old profile: https://www.upwork.com/freelancers/~017f07e5d7ff255755 |
| D-08 | Fiverr + Freelancer Profiles (Echoforge) | Venture | `pending` | New Fiverr, Freelancer, and Upwork accounts to be created today under Echoforge brand. Publish gigs from platform_metadata_v4 once live. |
| D-09 | Marketing Audit Pipeline — Sprint 1 | Venture | 2026-03 | Full manual-trigger pipeline built and live-tested against echoforge.biz (29/100, Grade F, 14 findings, $0.07 cost). Phases: scrape → Claude audit → full PDF + Markdown + sample PDF + sample MD → human review gate → delivery stub. Sample report: diagonal watermark, redaction bars with accurate counts, Echoforge branding, mailto CTA. Resumable via `--resume --order-id`. CLI: `scripts/run_marketing_audit.py`. |
| D-10 | Podcast Pipeline — Sprint 1 & 2 | Venture | 2026-03 | Manual-trigger pipeline: audio → Whisper transcription → Claude content generation (tier-aware) → Google Doc + full PDF backup + watermarked sample PDF. Sample shows timestamps + guest bio in full, all other sections redacted with CTA. `--demo` mode (no audio needed) + `--pdf-only` flag. Venture: `content_studio`. CLI: `scripts/run_content_studio.py`. |
| D-12 | Podcast Add-ons — Sprint 3b: Brand Voice + Promo Copy | Venture | 2026-03-25 | `generate_brand_voice.py`: analyses transcripts, outputs Brand Voice Guide, cached as `{show-slug}-brand-voice.json`. `generate_promo_copy.py`: 4 promo pieces with optional brand voice injection. Add-on runner (Phase 3b) wired into `content_studio/pipeline.py`. CLI: `--addons brand-voice promo-copy`. Premium truncation fixed: `CLAUDE_MAX_TOKENS_PREMIUM = 16000`. Tested end-to-end with real 60-min episode. |
| D-13 | Project Management — ClickUp Integration + Sync | System | 2026-03-27 | ClickUp workspace `AI Infra` live with 5 spaces, 53 tasks seeded. `comms/update_project_board.py` skill (create/update/read tasks). `comms/sync_task_status.py` skill: 4-way sync (ClickUp + ROADMAP.md + venture CLAUDE.md + session log) on every status change; auto git push on done; failures queued in `logs/pending_updates.json`. Scripts: `setup_clickup_workspace.py`, `seed_clickup_from_roadmap.py`, `sync_clickup_to_roadmap.py`, `update_task.py`, `retry_pending_updates.py`. |
| D-11 | Gemini Image Generation + Consistent Mockups | System | 2026-03 | Artwork: Gemini Imagen 4 (`imagen-4.0-generate-001`) standard tier; DALL-E 3 fallback. Mockups: `gemini-2.5-flash-image` multimodal — actual artwork PNG passed as image input so all 3 mockup scenes are visually consistent with the real artwork. Pipeline key fixes: mockup keys updated to `product_shot`/`living_room`/`flat_lay`. Pillow composite retained as fallback. Full Phase 3 tested end-to-end at $0.10/listing. |

---

## How to Add a New Item

Copy this template and paste into the correct priority section:

```markdown
| X-## | [Name] | [Venture/System] | `idea` | [One sentence: what it does, which skills it uses, what it costs/charges, which venture it belongs to.] |
```

**Rules:**
- Every item gets a type and priority before being added — no "TBD"
- Ventures reference their `CLAUDE.md` location
- System items reference which skill file(s) they affect
- Move to ✅ Done when shipped, not when "mostly done"
- Re-prioritise the whole table at the start of each week