#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

"""
Generate a Fiverr gig content package for a venture.

Calls the generate_fiverr_gig skill with venture-specific service definitions,
then saves the output JSON to output/gigs/{venture}/.

Note: Fiverr has no public API for gig creation. Review the JSON output and
use it to manually create or update your Fiverr gig.

Usage:
    python scripts/run_gig_generator.py --venture podcast_notes
    python scripts/run_gig_generator.py --venture marketing_audit
    python scripts/run_gig_generator.py --venture podcast_notes --output-dir /tmp/gigs
"""

import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from aiplatform.skills.marketplace.generate_fiverr_gig import generate_gig
from aiplatform.skills.media.generate_image import generate_image


# ─── Venture service definitions ──────────────────────────────────────────────
# These are venture-specific. In future, move to ventures/{name}/config.py
# and import here. For now, keep inline to keep the skill venture-agnostic.

VENTURE_CONFIGS: dict[str, dict] = {
    "podcast_notes": {
        "service_name": "Podcast Show Notes, Transcription & Marketing Kit",
        "service_description": (
            "Professional show notes, full transcript, LinkedIn post, newsletter teaser, "
            "and audiogram caption — all generated from your episode audio and delivered "
            "within 24–48 hours. AI-powered with human quality review before every delivery."
        ),
        "packages": [
            {
                "name": "Basic",
                "price_usd": 30,
                "delivery_days": 1,
                "revisions": 1,
                "includes": [
                    "Up to 30 mins audio/video length",
                    "Show notes (600–800 words)",
                    "3 key takeaways",
                    "Episode summary paragraph",
                ],
            },
            {
                "name": "Standard",
                "price_usd": 80,
                "delivery_days": 2,
                "revisions": 2,
                "includes": [
                    "Up to 60 mins audio/video length",
                    "Full show notes (1000–1500 words)",
                    "Complete transcript",
                    "Chapter timestamps included",
                    "Relevant links included",
                    "LinkedIn post & Newsletter teaser",
                    "Audiogram caption",
                ],
            },
            {
                "name": "Premium",
                "price_usd": 150,
                "delivery_days": 2,
                "revisions": 3,
                "includes": [
                    "Up to 90 mins audio/video length",
                    "Everything in Standard",
                    "Brand voice guide (first episode)",
                    "4 promotional copy pieces",
                    "SEO-optimised title variants (3)",
                    "Guest bio section",
                    "Google Docs delivery",
                ],
            },
        ],
        "target_audience": (
            "Independent podcasters and podcast production teams who want professional "
            "written content without spending hours writing it themselves after every episode."
        ),
        "key_benefits": [
            "Save 4–6 hours per episode on writing and editing",
            "Consistent, professional quality across every episode",
            "SEO-optimised show notes that help new listeners find your show",
            "Ready-to-post social copy — no editing needed",
            "Delivered in Google Docs for easy sharing with your team or sponsor",
        ],
        "keywords": [
            "Podcasts",
            "transcript",
            "notes",
            "internet marketing",
            "SEO optimization"
        ],
    },

    "marketing_audit": {
        "service_name": "Website Marketing Audit — Scored PDF Report with Action Plan",
        "service_description": (
            "Comprehensive AI-powered marketing audit of any public website. "
            "Scored across 6 dimensions — content, conversion, SEO, competitive positioning, "
            "brand trust, and growth strategy — with a prioritised action plan. "
            "Delivered as a professional branded PDF report."
        ),
        "packages": [
            {
                "name": "Snapshot",
                "price_usd": 50,
                "delivery_days": 1,
                "revisions": 0,
                "includes": [
                    "Overall marketing score (0–100)",
                    "Top 5 priority actions",
                    "5–10 page branded PDF report",
                ],
            },
            {
                "name": "Full Audit",
                "price_usd": 150,
                "delivery_days": 2,
                "revisions": 1,
                "includes": [
                    "6-dimension scored audit",
                    "14+ detailed findings",
                    "2 competitor comparisons",
                    "Before/after copy rewrite examples",
                    "10–15 page branded PDF report",
                ],
            },
            {
                "name": "Audit + Strategy",
                "price_usd": 250,
                "delivery_days": 3,
                "revisions": 2,
                "includes": [
                    "Everything in Full Audit",
                    "Complete WCAG Accessibility Scan",
                    "30-day implementation roadmap",
                    "3 competitor comparisons",
                    "15–20 page branded PDF report",
                ],
            },
        ],
        "target_audience": (
            "Small business owners and marketing managers who want an expert outside "
            "perspective on exactly why their website isn't converting — and what to fix first."
        ),
        "key_benefits": [
            "Pinpoint exactly why your website isn't converting visitors into customers",
            "Scored across 6 marketing dimensions with clear benchmarks",
            "Prioritised action plan — know what to fix first for maximum ROI",
            "Competitor snapshot shows how you compare to market leaders",
            "Professional PDF report you can share with your team or agency",
        ],
        "keywords": [
            "website audit",
            "marketing audit",
            "website analysis",
            "conversion audit",
            "SEO audit",
            "landing page review",
            "website critique",
            "CRO audit",
            "marketing review",
        ],
    },
    "security_audit": {
        "service_name": "Web Application Security Audit & Vulnerability Report",
        "service_description": (
            "Automated black-box security assessment that identifies real, confirmed exploitable "
            "vulnerabilities in your web application. Covers OSINT recon, surface mapping, "
            "vulnerability scanning, and active exploit testing (Professional/Agency). "
            "Delivered as a professional PDF report with CVSS-scored findings, attack chain "
            "narratives, and a prioritised remediation roadmap."
        ),
        "packages": [
            {
                "name": "Starter",
                "price_usd": 49,
                "delivery_days": 1,
                "revisions": 0,
                "includes": [
                    "Single domain, up to 50 endpoints",
                    "Passive OSINT recon (subdomains, leaks, CVEs)",
                    "Active surface mapping (ports, tech stack, exposed paths)",
                    "Automated vulnerability scan (9,000+ nuclei templates)",
                    "5–10 page PDF report with CVSS-scored findings",
                    "Prioritised remediation checklist",
                ],
            },
            {
                "name": "Professional",
                "price_usd": 149,
                "delivery_days": 1,
                "revisions": 1,
                "includes": [
                    "Single domain, unlimited endpoints",
                    "All Starter phases",
                    "Active exploit testing (SQLi, XSS, SSRF, LFI, JWT, open redirect)",
                    "Optional authenticated session testing",
                    "Attack chain narrative with PoC evidence",
                    "10–15 page PDF report",
                    "30-day remediation roadmap",
                ],
            },
            {
                "name": "Agency",
                "price_usd": 349,
                "delivery_days": 1,
                "revisions": 1,
                "includes": [
                    "Up to 5 subdomains scanned",
                    "All Professional phases",
                    "White-label branded PDF report",
                    "Critical finding alert email on discovery",
                    "15–25 page executive + technical PDF",
                    "Priority turnaround (<3 hours)",
                ],
            },
        ],
        "target_audience": (
            "SaaS founders, startup CTOs, and SMB owners who need a credible security assessment "
            "before a product launch, investor due diligence, or compliance audit — without paying "
            "$5,000+ for a traditional penetration test."
        ),
        "key_benefits": [
            "Real confirmed exploits — not just a scanner output dump",
            "CVSS-scored findings with attack chain narratives your dev team can act on",
            "Covers OWASP Top 10 plus modern attack vectors (JWT flaws, SSRF, SSTI)",
            "Delivered in hours, not weeks — no scheduling, no NDAs required",
            "Professional PDF report you can share with investors, clients, or compliance teams",
        ],
        "keywords": [
            "security audit",
            "web security audit",
            "penetration test",
            "vulnerability assessment",
            "OWASP audit",
            "security scan",
            "pentest report",
            "website security",
            "vulnerability report",
        ],
    },

    "accessibility_audit": {
        "service_name": "WCAG Website Accessibility Audit \& VPAT Report",
        "service_description": (
            "Comprehensive automated WCAG 2.1 AA/AAA accessibility audit for your website. "
            "Identify critical compliance risks before they become legal liabilities. "
            "Scans for contrast, ARIA parity, structure, keyboard navigation, and more. "
            "Delivered as a detailed, prioritized PDF action plan for your developers."
        ),
        "packages": [
            {
                "name": "Single Page Scan",
                "price_usd": 40,
                "delivery_days": 1,
                "revisions": 0,
                "includes": [
                    "Home page or critical landing page",
                    "Automated WCAG 2.1 AA scan",
                    "Prioritized developer fix-list PDF",
                ],
            },
            {
                "name": "Standard Audit",
                "price_usd": 120,
                "delivery_days": 2,
                "revisions": 1,
                "includes": [
                    "Up to 5 key user journeys/pages",
                    "Automated WCAG 2.1 AA/AAA check",
                    "Detailed PDF report",
                    "Color contrast analysis",
                ],
            },
            {
                "name": "Premium + Strategy",
                "price_usd": 250,
                "delivery_days": 3,
                "revisions": 2,
                "includes": [
                    "Complete site scan (up to 15 pages)",
                    "Automated WCAG 2.1 AA/AAA check",
                    "Strategic risk assessment",
                    "Prioritized 30-day remediation roadmap",
                ],
            },
        ],
        "target_audience": (
            "Business owners, agencies, and developers needing to ensure public-facing "
            "websites meet ADA/WCAG compliance before scaling traffic or facing liability."
        ),
        "key_benefits": [
            "Identify hidden accessibility flaws that block disabled users",
            "Clear technical instructions for developers to fix violations",
            "Reduce risk of ADA compliance lawsuits",
            "Improve overall SEO and site usability",
            "Executive-friendly scorecard and detailed technical breakdown",
        ],
        "keywords": [
            "accessibility audit",
            "WCAG audit",
            "ADA compliance",
            "website audit",
            "ARIA check",
            "web accessibility",
            "accessibility report",
        ],
    },
}


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a Fiverr gig content package for a venture"
    )
    parser.add_argument(
        "--venture", required=True, choices=list(VENTURE_CONFIGS.keys()),
        help="Venture to generate gig for"
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Override output directory (default: output/gigs/{venture}/)"
    )
    args = parser.parse_args()

    config = VENTURE_CONFIGS[args.venture]

    print(f"\nFiverr Gig Generator")
    print(f"  Venture:  {args.venture}")
    print(f"  Service:  {config['service_name']}")
    print(f"  Packages: {', '.join(p['name'] + ' ($' + str(p['price_usd']) + ')' for p in config['packages'])}")
    print()

    result = generate_gig(
        service_name=config["service_name"],
        service_description=config["service_description"],
        packages=config["packages"],
        target_audience=config["target_audience"],
        key_benefits=config["key_benefits"],
        keywords=config["keywords"],
        venture_name=args.venture,
        output_dir=args.output_dir,
    )

    print(f"  Classification: {result.get('category')} > {result.get('subcategory')} ({result.get('service_type')})")
    print(f"  Gig title:    {result['gig_title']}")
    print(f"  Tags:         {', '.join(result['tags'])}")
    print(f"  Description:  {len(result['gig_description'])} chars")
    print()
    print(f"  Packages:")
    for p in result["packages"]:
        print(f"    {p['name']:10s} ${p['price']:>3}  {p['delivery_days']}d  {p['revisions']}rev  — {p['title'][:25]} — {p['description'][:30]}")
    print()
    print(f"  FAQ ({len(result['faq'])} items):")
    for item in result["faq"]:
        print(f"    Q: {item['question'][:70]}")
    print()
    print(f"  Requirements ({len(result.get('requirements', []))} items):")
    for req in result.get("requirements", []):
        print(f"    - [{req.get('type')}] {'(Mandatory)' if req.get('is_mandatory') else '(Optional)'} {req.get('requirement')}")
    print()

    if "image_prompt" in result and result["image_prompt"]:
        print(f"  Generating cover image (16:9)...")
        print(f"    Prompt: {result['image_prompt'][:70]}...")
        try:
            image_result = generate_image(
                prompt=result["image_prompt"],
                aspect_ratio="16:9",
                quality_tier="standard",
                output_dir=Path(result["output_path"]).parent,
                filename=f"{Path(result['output_path']).stem}-cover"
            )
            print(f"  Cover image saved to: {image_result['image_path']}")
        except Exception as e:
            print(f"  Image generation failed: {e}")
    else:
        print("  No image_prompt returned, skipping image generation.")

    print()
    print(f"  Saved to: {result['output_path']}")
    print()
    print("  NOTE: Fiverr has no public gig creation API.")
    print("        Review the JSON above and use it to create/update your gig manually.")
    print()


if __name__ == "__main__":
    main()
