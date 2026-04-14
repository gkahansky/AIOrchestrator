#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

"""
Seed the Jira workspace from ROADMAP.md data.

Creates:
  AII (AI Infra)      — Features for each active/done venture or capability,
                          with Stories representing sprints and deliverables.
  PRM (Product Roadmap) — Ideas for future ventures not yet started.

Issue hierarchy:
  Feature  → top-level venture or platform capability
  Story    → sprint or deliverable within a Feature
  Task     → (not created in seed; added manually per story)
  Bug      → (not created in seed)
  Idea     → product roadmap items in PRM project

Idempotent: checks labels before creating. Safe to re-run.

Usage:
    python scripts/seed_jira_from_roadmap.py             # create all
    python scripts/seed_jira_from_roadmap.py --dry-run   # preview
    python scripts/seed_jira_from_roadmap.py --feature "Podcast Notes"  # one feature only
"""

import argparse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from aiplatform.skills.comms.update_jira_board import (
    create_issue,
    transition_issue,
    add_comment,
    find_issue_by_label,
    search_issues,
    list_projects,
)


# ─── Data model ───────────────────────────────────────────────────────────────
# Each Feature groups related ROADMAP.md items as Stories.
# Status values must match Jira workflow exactly (case-insensitive match in skill).

JIRA_STATUS = {
    "done":        "Done",
    "in-progress": "In Progress",
    "planned":     "To Do",
    "idea":        "To Do",
    "on-hold":     "Pending",
    "blocked":     "Pending",
}

PRIORITY_MAP = {
    "urgent": "Highest",
    "high":   "High",
    "medium": "Medium",
    "low":    "Low",
}

# ── AI Infra features (AII project) ─────────────────────────────────────────

FEATURES = [
    {
        "roadmap_id":  "F-podcast",
        "summary":     "Podcast Notes — Content Pipeline",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "Highest",
        "description": (
            "AI-powered podcast content pipeline.\n"
            "Transforms episode audio into professional show notes, full transcripts, "
            "LinkedIn posts, newsletter teasers, and promotional copy.\n"
            "Delivered as PDF + Google Doc within 24-48 hours. "
            "Venture: podcast_notes / content_studio."
        ),
        "labels": ["venture", "venture-podcast_notes"],
        "stories": [
            # (roadmap_id_label, summary, status, description)
            ("U-01", "Sprint 1 & 2 — Core Pipeline (audio to PDF)",
             "Done",
             "Manual-trigger pipeline: audio -> Whisper transcription -> Claude content generation "
             "-> Google Doc + full PDF + sample PDF (watermarked). --demo mode, --pdf-only flag. "
             "Venture: content_studio."),
            ("H-06", "Sample PDF Generator (--demo mode + watermark)",
             "Done",
             "Demo mode generates full + sample PDFs from canned content (tech/business/marketing). "
             "Sample PDF: watermark, timestamps/guest bio in full, all other sections redacted with CTA."),
            ("M-03", "Add-on: Brand Voice Guide",
             "Done",
             "Analyse 2-3 episode transcripts -> structured Brand Voice Guide (tone, vocabulary, "
             "sentence style). Cached as JSON per client. Skill: generate_brand_voice.py. Price: $79."),
            ("M-04", "Add-on: Episode Promotional Copy",
             "Done",
             "Platform description + audiogram caption + newsletter teaser + LinkedIn post from one episode. "
             "Skill: generate_promo_copy.py. Premium truncation fixed (CLAUDE_MAX_TOKENS_PREMIUM=16000). Price: $39."),
            ("M-05", "Add-on: 30-Day Social Calendar",
             "To Do",
             "30 ready-to-post pieces from 4 episodes. Skill: generate_social_calendar.py. Price: $79."),
            ("M-06", "Add-on: Listener Email Sequence",
             "To Do",
             "5-email nurture sequence for new subscribers. Skill: generate_email_sequence.py. Price: $99."),
            ("M-11", "Add-on: Guest Outreach Templates",
             "To Do",
             "3 email templates (cold/warm/follow-up) for pitching guests. "
             "Skill: generate_guest_outreach.py. Price: $29."),
            ("M-12", "Add-on: Show Landing Page Audit",
             "To Do",
             "Scored CRO audit of podcast website/episode page. Price: $49."),
            ("L-01", "Sprint 5 — Freelancer.com Integration",
             "To Do",
             "Freelancer SDK integration. Webhook: project.awarded event -> FastAPI /webhooks/freelancer. "
             "Apply for API access first."),
            ("L-02", "Add-on: Competitive Show Analysis",
             "To Do",
             "Benchmark vs 3 competing shows. Skill: generate_competitive_analysis.py. Price: $79."),
            ("L-03", "Add-on: Launch Playbook",
             "To Do",
             "Full launch plan for new/relaunching shows. 8-week pre-launch timeline. "
             "Skill: generate_launch_playbook.py. Price: $149."),
            ("H-01", "Sprint 3 — Upwork Delivery Integration",
             "Pending",
             "Full Upwork integration: OAuth2 non-expiring token, polling, delivery via contract message. "
             "BLOCKED: Upwork integration deferred — Fiverr-first strategy."),
        ],
    },
    {
        "roadmap_id":  "F-audit",
        "summary":     "Marketing Audit — Report Pipeline",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "Highest",
        "description": (
            "AI-powered website marketing audit service.\n"
            "Scores any public website across 6 dimensions (content, conversion, SEO, "
            "competitive positioning, brand trust, growth strategy) and delivers a "
            "professional branded PDF report with prioritised action plan.\n"
            "Tiers: Snapshot $49 / Full Audit $149 / Audit + Strategy $249."
        ),
        "labels": ["venture", "venture-marketing_audit"],
        "stories": [
            ("U-02", "Sprint 1 — Core Audit Pipeline",
             "Done",
             "Manual-trigger pipeline complete and live-tested against echoforge.biz. "
             "Score: 29/100. 14 findings. Cost: $0.07. Resumable via --resume --order-id."),
            ("H-02", "Sprint 2 — PDF Polish & Echoforge Branding",
             "Done",
             "Full PDF: dimension details, copy examples, 30-day roadmap, competitor table. "
             "Echoforge branded header/footer (dark navy band, terracotta accent, page numbers). "
             "Score consistency: temperature=0 + unified scoring instructions."),
            ("M-10", "Sprint 4 — Sample Cold Outreach Pipeline",
             "To Do",
             "Generate 3 sample audit reports (SaaS/service/e-commerce). "
             "Outreach queue: scan prospect homepage -> generate 3 specific findings snippet "
             "-> personalise cold email."),
            ("M-02", "Sprint 3 — Upwork Integration",
             "Pending",
             "Upwork order detection + automated delivery of PDF report link via contract message. "
             "BLOCKED: Upwork integration deferred — Fiverr-first strategy."),
        ],
    },
    {
        "roadmap_id":  "H-08",
        "summary":     "Gig Generator — Fiverr",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "High",
        "description": (
            "Automatically generate Fiverr gig content packages for any venture.\n"
            "Given a venture service definition, generates: SEO-optimised gig title, "
            "description, pricing packages (Basic/Standard/Premium), FAQ (5 Q&A), and tags.\n"
            "Note: Fiverr has no public gig creation API — output is structured JSON "
            "for manual upload. Skill: marketplace/generate_fiverr_gig.py."
        ),
        "labels": ["system", "venture-platform"],
        "stories": [
            ("H-08-skill", "Build generate_fiverr_gig.py skill",
             "Done",
             "Claude API skill: generates gig title, description, packages, FAQ, tags. "
             "Venture-agnostic — service config injected at call time. Saves JSON to output/gigs/."),
            ("H-08-runner", "Build run_gig_generator.py CLI runner",
             "Done",
             "Runner script with service configs for podcast_notes and marketing_audit. "
             "Tested both ventures. Outputs structured JSON for manual Fiverr upload."),
            ("H-08-image", "Add cover image generation via generate_image.py",
             "To Do",
             "Compose the gig runner to also call platform/media/generate_image.py "
             "for a branded cover image. Save to output/gigs/{venture}/ alongside the JSON."),
        ],
    },
    {
        "roadmap_id":  "F-pm",
        "summary":     "Platform — Project Management",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "High",
        "description": (
            "Platform-level project management integration.\n"
            "Tracks development work, syncs task status across ROADMAP.md, "
            "venture CLAUDE.md files, and the project board (Jira). "
            "Auto-pushes to GitHub on task completion."
        ),
        "labels": ["system", "venture-platform"],
        "stories": [
            ("U-03", "Project Management Integration — Jira",
             "Done",
             "Jira project AII live at aiinfra.atlassian.net. "
             "Skill: comms/update_jira_board.py. "
             "4-way sync: Jira + ROADMAP.md + venture CLAUDE.md + session log. "
             "Auto git push on done. Scripts: seed_jira/update_task/retry."),
            ("F-pm-jira", "Jira Integration — Active PM Tool",
             "Done",
             "Jira is the active project management tool for the AII platform. "
             "Skill: comms/update_jira_board.py. "
             "Seed script: seed_jira_from_roadmap.py. "
             "Update sync_task_status.py + update_task.py to use Jira."),
            ("H-05", "Human Review Gate",
             "To Do",
             "30-min review window with email + Slack alert. "
             "/orders/{id}/approve FastAPI endpoint. "
             "AUTO_APPROVE=false flag per venture after 20 validated orders."),
            ("H-09", "Management App (FastAPI + React)",
             "To Do",
             "Web interface: venture status overview, billing summary, open orders per venture, "
             "product generation panel. FastAPI + lightweight React. Hosted on Railway."),
            ("M-09", "Dashboard Endpoint",
             "To Do",
             "FastAPI /dashboard: active orders, pipeline status, revenue totals, "
             "cost totals, failed jobs. Per-venture filters."),
        ],
    },
    {
        "roadmap_id":  "F-marketplace",
        "summary":     "Platform — Marketplace Automation",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "High",
        "description": (
            "Automated order intake and delivery across Fiverr, Upwork, and Freelancer.\n"
            "Order listeners parse incoming orders and route them to the correct venture pipeline. "
            "Delivery sends completed output back via the originating platform."
        ),
        "labels": ["system", "venture-platform"],
        "stories": [
            ("M-07", "Fiverr Order Listener — Podcast Notes",
             "To Do",
             "Gmail polling via APScheduler every 5 min. "
             "Parses order confirmation email for audio link. "
             "Skill: marketplace/fiverr_listener.py."),
            ("M-08", "Fiverr Order Listener — Marketing Audit",
             "To Do",
             "Same Gmail mechanism as M-07. "
             "Parses website URL + tier from requirements form. "
             "Skill: marketplace/audit_fiverr_listener.py."),
            ("H-03", "Upwork Order Listener — Podcast",
             "Pending",
             "GraphQL API polling every 5 min for new podcast_notes contracts. "
             "BLOCKED: Upwork integration deferred — Fiverr-first strategy."),
            ("H-04", "Upwork Order Listener — Marketing Audit",
             "Pending",
             "Same polling mechanism as H-03 but routes to audit pipeline. "
             "BLOCKED: Upwork integration deferred — Fiverr-first strategy."),
        ],
    },
    {
        "roadmap_id":  "F-finance",
        "summary":     "Platform — Finance & Analytics",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "Medium",
        "description": (
            "Unified financial tracking and analytics across all ventures.\n"
            "Tracks API costs, platform fees, and revenue. "
            "Auto-approve system for validated orders."
        ),
        "labels": ["system", "venture-platform"],
        "stories": [
            ("M-13", "Financial Tracker (P&L dashboard)",
             "To Do",
             "Unified income vs expenses across all ventures. Log API costs, platform fees, revenue. "
             "Extends log_cost.py + log_revenue.py. Adds /finances FastAPI endpoint. "
             "Monthly P&L per venture, running totals, cost-per-order."),
            ("L-07", "Auto-Approve System",
             "To Do",
             "After 20 validated deliveries per venture, flip AUTO_APPROVE=true. "
             "Separate flag per venture + per add-on type. "
             "Triggered via admin endpoint, not manually."),
        ],
    },
    {
        "roadmap_id":  "F-promotion",
        "summary":     "Platform — Promotion & Growth",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "Medium",
        "description": (
            "Automated promotion and outreach pipeline across platforms.\n"
            "Generates personalised content, posts to communities, and manages lead generation "
            "for each venture."
        ),
        "labels": ["system", "venture-platform"],
        "stories": [
            ("H-10", "Promotion Agent",
             "To Do",
             "Automated venture promotion: Reddit r/podcasting, Facebook groups, LinkedIn outreach. "
             "For marketing audit: LinkedIn cold outreach with 3 specific homepage findings. "
             "For Etsy: Pinterest pins + social queue. Skill: comms/promote_venture.py."),
            ("M-14", "Content Creation Agent",
             "To Do",
             "Generate marketing collateral: landing pages, logo concepts (SVG), banner images, "
             "gig cover images, social profile assets. Skill: media/generate_svg_asset.py."),
            ("M-16", "Lead Generation System",
             "To Do",
             "Crawl target platforms (LinkedIn, Reddit, directories) -> score leads -> "
             "generate personalised observation -> assemble offer sheet PDF. "
             "Skills: research/find_leads.py, media/generate_offer_sheet.py."),
            ("L-11", "AI Sales Team Integration",
             "To Do",
             "Evaluate zubair-trabzada/ai-sales-team-claude: 14 skills for prospect research, "
             "BANT qualify, outreach sequences, proposal generation. "
             "Potential platform-level prospecting layer."),
            ("L-12", "Outreach Automation",
             "To Do",
             "Systematic cold outreach: crawl target list -> personalised observation -> "
             "send via Upwork InMail / LinkedIn DM. Rate-limited, de-duplicated per prospect."),
        ],
    },
    {
        "roadmap_id":  "F-image",
        "summary":     "Image Generation Pipeline",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "High",
        "description": (
            "AI image generation pipeline for digital products and marketing assets.\n"
            "Gemini Imagen 4 (standard tier) + DALL-E 3 (fallback). "
            "Consistent artwork-based mockup generation via gemini-2.5-flash-image."
        ),
        "labels": ["system", "venture-platform"],
        "stories": [
            ("H-07", "Gemini Imagen 4 Integration",
             "Done",
             "Gemini Imagen 4 (imagen-4.0-generate-001) live as standard tier. "
             "DALL-E 3 demoted to fallback. Tool Router updated in skills.json."),
            ("D-11", "Consistent Mockup Generation",
             "Done",
             "Mockup skill rewritten: gemini-2.5-flash-image multimodal — actual artwork PNG "
             "passed as image input so all 3 mockup scenes are visually consistent. "
             "Pillow composite retained as fallback. Full Phase 3 tested end-to-end at $0.10/listing."),
        ],
    },
    {
        "roadmap_id":  "F-brand",
        "summary":     "Echoforge Brand & Launch",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "High",
        "description": (
            "Echoforge brand identity, landing page, and marketplace presence. "
            "Foundation work completed before service launch."
        ),
        "labels": ["system", "venture-platform"],
        "stories": [
            ("D-01", "Landing page (echoforge.biz)",
             "Done",
             "Deployed to Cloudflare Pages. Two services: podcast content + marketing audit. "
             "Platform cards live with Upwork + Fiverr links."),
            ("D-02", "Brand identity & logo system",
             "Done",
             "3D glossy eye icon in warm terracotta palette. "
             "Wordmark: 'hey' ink / 'eye' terracotta. Favicon, app icon, horizontal lockup."),
            ("D-06", "Platform metadata v4",
             "Done",
             "Fiverr + Upwork gig copy for podcast and marketing audit services. "
             "Outreach templates included."),
            ("D-07", "Upwork profile live (Echoforge)",
             "Done",
             "Echoforge Upwork profile created and live. "
             "Old profile: upwork.com/freelancers/~017f07e5d7ff255755"),
            ("D-08", "Fiverr + Freelancer profiles (Echoforge)",
             "Done",
             "Fiverr, Freelancer, and Upwork accounts created under Echoforge brand. "
             "Gigs published from platform_metadata_v4."),
        ],
    },
    {
        "roadmap_id":  "F-arch",
        "summary":     "Platform Architecture",
        "project":     "AII",
        "type":        "Epic",
        "priority":    "Medium",
        "description": (
            "Core platform architecture — CLAUDE.md context hierarchy, "
            "orchestration framework, caching, and memory systems."
        ),
        "labels": ["system", "venture-platform"],
        "stories": [
            ("D-03", "Platform CLAUDE.md hierarchy",
             "Done",
             "Root /CLAUDE.md + venture-level CLAUDE.md per venture. "
             "VS Code scoping: open from venture directory."),
            ("D-04", "Podcast venture CLAUDE.md",
             "Done",
             "Enhanced v2: core pipeline + 8 marketing add-ons specced. "
             "ai-marketing-claude integration pattern documented."),
            ("D-05", "Marketing Audit venture CLAUDE.md",
             "Done",
             "Full 6-sprint roadmap, scoring framework, pipeline phases, skills map, env vars."),
            ("L-08", "LangGraph Orchestration",
             "To Do",
             "Replace sequential pipeline calls with LangGraph for stateful, resumable workflows. "
             "Only implement when pipeline complexity justifies it (>5 phases with branching)."),
            ("L-09", "Redis Pub/Sub for inter-agent events",
             "To Do",
             "Enable event-driven architecture: e.g. transcription_complete event triggers "
             "content generation without tight coupling. "
             "Prerequisite for parallel multi-venture operation at scale."),
            ("L-10", "Qdrant Long-Term Memory",
             "To Do",
             "Per-venture namespaced memory for research history, brand guidelines, "
             "recurring client preferences. "
             "Implement when a venture needs cross-session context."),
        ],
    },
]

# ── Product Roadmap ideas (PRM project) ───────────────────────────────────────

ROADMAP_IDEAS = [
    {
        "roadmap_id": "L-06",
        "summary":    "Etsy Digital Image Shop",
        "priority":   "Low",
        "description": (
            "Automated Etsy shop selling AI-generated digital wall art. "
            "Gemini Imagen 4 artwork + mockup generation is live and tested. "
            "BLOCKED: Etsy API key pending approval. "
            "Resume Sprint 1 (product pipeline) once Etsy API access confirmed."
        ),
        "labels": ["venture", "venture-etsy", "on-hold"],
    },
    {
        "roadmap_id": "L-05",
        "summary":    "Content Channels — Faceless Video (Venture B)",
        "priority":   "Low",
        "description": (
            "Faceless YouTube/TikTok/Instagram channel system. "
            "Channel = config entry, not new codebase. "
            "First channel: 'Project Post-Mortem' (tech failure investigations, true-crime style). "
            "Needs: Veo/Runway API access, ElevenLabs, TikTok Content Posting API (1-4 wk approval), "
            "Instagram Graph API (1-2 wk)."
        ),
        "labels": ["venture", "venture-content_channels"],
    },
    {
        "roadmap_id": "M-15",
        "summary":    "Copywriting Services (Jasper Integration)",
        "priority":   "Medium",
        "description": (
            "Standalone copywriting service powered by Jasper AI for long-form brand copy: "
            "landing pages, email sequences, ad copy, product descriptions. "
            "Research Jasper API tier requirements before committing."
        ),
        "labels": ["venture"],
    },
    {
        "roadmap_id": "L-04",
        "summary":    "GEO / AI Search Optimisation Service",
        "priority":   "Low",
        "description": (
            "Standalone service: audit any site for AI search visibility "
            "(ChatGPT, Claude, Perplexity, Gemini). "
            "Based on zubair-trabzada/geo-seo-claude repo — same author as ai-marketing-claude. "
            "Research and evaluate before committing."
        ),
        "labels": ["venture"],
    },
]


# ─── Seed logic ───────────────────────────────────────────────────────────────

def _label_for(roadmap_id: str) -> str:
    return f"roadmap_id-{roadmap_id}"


def _exists(roadmap_id: str, project: str) -> dict | None:
    """Return existing issue if already seeded, else None."""
    label = _label_for(roadmap_id)
    issues = search_issues(f'project = "{project}" AND labels = "{label}"', max_results=1)
    return issues[0] if issues else None


def _transition(issue_key: str, target: str, dry_run: bool) -> None:
    if target == "To Do":
        return  # default status — no transition needed
    if dry_run:
        print(f"        [dry-run] would transition -> {target}")
        return
    result = transition_issue(issue_key, target)
    if "error" in result:
        print(f"        ! transition '{target}' failed: {result['error']}")
    else:
        print(f"        -> transitioned to {target}")


def seed_features(target_feature: str | None, dry_run: bool) -> None:
    created = skipped = errors = 0

    for feat in FEATURES:
        fname = feat["summary"]
        if target_feature and target_feature.lower() not in fname.lower():
            continue

        print(f"\n  Feature: {fname}")

        # ── Create or find the Feature ──
        existing_feat = _exists(feat["roadmap_id"], feat["project"])
        if existing_feat:
            feat_key = existing_feat["issue_key"]
            print(f"    [skip] already exists: {feat_key}")
            skipped += 1
        else:
            labels = feat.get("labels", []) + [_label_for(feat["roadmap_id"])]
            print(f"    [create] Feature in {feat['project']}")
            if not dry_run:
                result = create_issue(
                    project_key=feat["project"],
                    summary=feat["summary"],
                    issue_type=feat["type"],
                    description=feat.get("description"),
                    labels=labels,
                    priority=feat.get("priority", "Medium"),
                )
                if "error" in result:
                    print(f"    ! ERROR: {result['error']}")
                    errors += 1
                    continue
                feat_key = result["issue_key"]
                print(f"    -> created {feat_key}  {result['url']}")
                created += 1
                # Features start In Progress unless all stories are done
                all_done = all(s[2] == "Done" for s in feat.get("stories", []))
                target_status = "Done" if all_done else "In Progress"
                _transition(feat_key, target_status, dry_run)
                time.sleep(0.5)
            else:
                print(f"    [dry-run] would create Feature")
                feat_key = "DRY-RUN"
                created += 1

        # ── Create Stories under this Feature ──
        for story_data in feat.get("stories", []):
            rid, s_summary, s_status, s_desc = story_data
            story_label = _label_for(rid)

            existing_story = _exists(rid, feat["project"])
            if existing_story:
                print(f"      Story [{rid}] skip — {existing_story['issue_key']} already exists")
                skipped += 1
                continue

            print(f"      Story [{rid}] {s_summary[:55]}  ({s_status})")
            if dry_run:
                print(f"        [dry-run] would create Story under {feat_key}")
                created += 1
                continue

            story_labels = [story_label, "story"]
            result = create_issue(
                project_key=feat["project"],
                summary=f"[{rid}] {s_summary}",
                issue_type="Story",
                description=s_desc,
                parent_key=feat_key if feat_key != "DRY-RUN" else None,
                labels=story_labels,
            )
            if "error" in result:
                # parent link might be rejected — retry without parent
                print(f"        ! with parent failed: {result['error'][:80]}")
                print(f"        Retrying without parent link...")
                result = create_issue(
                    project_key=feat["project"],
                    summary=f"[{rid}] {s_summary}",
                    issue_type="Story",
                    description=s_desc,
                    labels=story_labels,
                )
                if "error" in result:
                    print(f"        ! ERROR: {result['error'][:80]}")
                    errors += 1
                    continue

            story_key = result["issue_key"]
            print(f"        -> {story_key}  {result['url']}")
            created += 1
            _transition(story_key, s_status, dry_run)
            time.sleep(0.4)

    return created, skipped, errors


def seed_roadmap_ideas(dry_run: bool) -> tuple[int, int, int]:
    created = skipped = errors = 0
    print("\n  Product Roadmap Ideas (PRM):")

    for idea in ROADMAP_IDEAS:
        rid = idea["roadmap_id"]
        existing = _exists(rid, "PRM")
        if existing:
            print(f"    [{rid}] skip — {existing['issue_key']} already exists")
            skipped += 1
            continue

        print(f"    [{rid}] {idea['summary']}")
        if dry_run:
            print(f"      [dry-run] would create Idea in PRM")
            created += 1
            continue

        labels = idea.get("labels", []) + [_label_for(rid)]
        result = create_issue(
            project_key="PRM",
            summary=idea["summary"],
            issue_type="Idea",
            description=idea.get("description"),
            labels=labels,
            priority=PRIORITY_MAP.get(idea.get("priority", "medium").lower(), "Medium"),
        )
        if "error" in result:
            print(f"      ! ERROR: {result['error']}")
            errors += 1
            continue

        print(f"      -> {result['issue_key']}  {result['url']}")
        created += 1
        time.sleep(0.4)

    return created, skipped, errors


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed Jira from ROADMAP.md data")
    parser.add_argument("--dry-run",  action="store_true", help="Preview without creating issues")
    parser.add_argument("--feature",  metavar="NAME",      help="Seed only this feature (substring match)")
    parser.add_argument("--ideas-only", action="store_true", help="Only seed Product Roadmap ideas")
    parser.add_argument("--features-only", action="store_true", help="Only seed AI Infra features")
    args = parser.parse_args()

    print(f"\nJira Seed Script")
    print(f"  Domain: {__import__('os').environ.get('JIRA_DOMAIN', '?')}")
    print(f"  Mode:   {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 50)

    total_created = total_skipped = total_errors = 0

    if not args.ideas_only:
        print("\n[AI Infra — AII]")
        c, s, e = seed_features(args.feature, args.dry_run)
        total_created += c; total_skipped += s; total_errors += e

    if not args.features_only and not args.feature:
        print("\n[Product Roadmap — PRM]")
        c, s, e = seed_roadmap_ideas(args.dry_run)
        total_created += c; total_skipped += s; total_errors += e

    print(f"\n{'=' * 50}")
    print(f"Result: {total_created} created, {total_skipped} skipped, {total_errors} errors")
    if args.dry_run:
        print("(dry-run — no issues were created)")
    print()


if __name__ == "__main__":
    main()
