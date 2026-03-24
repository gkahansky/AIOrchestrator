#!/usr/bin/env python3
"""
Manual trigger for Marketing Audit pipeline — Sprint 1.

Usage:
    python scripts/run_marketing_audit.py \\
        --url https://example.com \\
        --tier full \\
        [--brand-name "Example Co"] \\
        [--competitors https://comp1.com https://comp2.com] \\
        [--client-email client@example.com] \\
        [--order-id my-custom-id]

Resume after review approval:
    python scripts/run_marketing_audit.py --resume --order-id <order_id> [--approve]

Generate a sample report without scraping (for testing PDF output):
    python scripts/run_marketing_audit.py --demo --tier full
"""

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add src/ to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ventures.marketing_audit.pipeline import run_order, _load_json


def main():
    parser = argparse.ArgumentParser(description="Marketing Audit pipeline — manual trigger")

    parser.add_argument("--url", help="Website URL to audit")
    parser.add_argument("--tier", choices=["snapshot", "full", "premium"], default="full")
    parser.add_argument("--brand-name", default="", help="Brand name override (auto-detected if omitted)")
    parser.add_argument("--competitors", nargs="*", default=[], help="Competitor URLs (space-separated)")
    parser.add_argument("--client-email", default="")
    parser.add_argument("--order-id", help="Order ID (auto-generated if not supplied)")

    parser.add_argument(
        "--report-type",
        choices=["both", "full", "sample"],
        default="both",
        help="both (default): full + sample/censored PDF. full: full only. sample: censored only.",
    )

    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--approve", action="store_true", help="Mark as approved before resuming")
    parser.add_argument("--demo", action="store_true", help="Run with sample data (no scraping)")

    parser.add_argument("--output-dir", default="./output/marketing_audit")

    args = parser.parse_args()

    if args.demo:
        _run_demo(args)
    elif args.resume:
        _resume_order(args)
    else:
        _new_order(args)


def _new_order(args):
    if not args.url:
        print("ERROR: --url is required.", file=sys.stderr)
        sys.exit(1)

    url = args.url
    if not url.startswith("http"):
        url = "https://" + url

    order_id = args.order_id or f"audit-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    order = {
        "order_id": order_id,
        "url": url,
        "tier": args.tier,
        "brand_name": args.brand_name or "",
        "competitor_urls": args.competitors,
        "client_email": args.client_email,
        "report_type": args.report_type,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }

    print(f"\nMarketing Audit — New Order")
    print(f"  Order ID:    {order_id}")
    print(f"  URL:         {url}")
    print(f"  Tier:        {args.tier.upper()}")
    print(f"  Report type: {args.report_type}")
    if args.competitors:
        print(f"  Competitors: {', '.join(args.competitors)}")
    print()

    run_order(order, output_dir=args.output_dir)


def _resume_order(args):
    if not args.order_id:
        print("ERROR: --order-id required to resume.", file=sys.stderr)
        sys.exit(1)

    order_path = Path(args.output_dir) / args.order_id / "order.json"
    if not order_path.exists():
        print(f"ERROR: Order not found: {order_path}", file=sys.stderr)
        sys.exit(1)

    order = _load_json(order_path)

    if args.approve:
        order["status"] = "approved"
        order_path.write_text(json.dumps(order, indent=2, default=str), encoding="utf-8")
        print(f"Order {args.order_id} marked approved.")

    print(f"\nResuming order {args.order_id} (status: {order['status']})")
    run_order(order, output_dir=args.output_dir)


def _run_demo(args):
    """Run against sample data to test PDF generation without scraping."""
    order_id = f"demo-{datetime.utcnow().strftime('%H%M%S')}"
    output_dir = Path(args.output_dir) / order_id
    output_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    scripts_path = _find_scripts_path()
    if scripts_path and scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)

    # Minimal sample report_data matching generate_pdf_report.py schema
    import os
    from datetime import datetime as dt
    sample = {
        "url": "https://heyeye.studio",
        "date": dt.now().strftime("%B %d, %Y"),
        "brand_name": "Heyeye Studio",
        "business_type": "Agency",
        "tier": args.tier,
        "overall_score": 68,
        "executive_summary": (
            "Heyeye Studio presents a clean, professional identity that communicates "
            "AI-powered marketing services clearly. The site scores well on brand trust "
            "and visual design, but has significant opportunities to improve conversion "
            "rate, SEO discoverability, and competitive positioning.\n\n"
            "The top priority is adding explicit social proof (case studies, testimonials) "
            "and improving the homepage CTA copy to be more outcome-focused."
        ),
        "categories": {
            "Content & Messaging":    {"score": 72, "weight": "25%", "key_finding": "Value prop is clear but lacks specificity", "details": ""},
            "Conversion Optimization": {"score": 58, "weight": "20%", "key_finding": "Single CTA with generic copy", "details": ""},
            "SEO & Discoverability":  {"score": 65, "weight": "20%", "key_finding": "Missing meta descriptions on service pages", "details": ""},
            "Competitive Positioning": {"score": 60, "weight": "15%", "key_finding": "No comparison page or clear differentiators listed", "details": ""},
            "Brand & Trust":          {"score": 80, "weight": "10%", "key_finding": "Strong visual identity", "details": ""},
            "Growth & Strategy":      {"score": 55, "weight": "10%", "key_finding": "No visible email capture or lead magnet", "details": ""},
        },
        "findings": [
            {"severity": "High", "finding": "No client testimonials visible on homepage"},
            {"severity": "High", "finding": "Primary CTA says 'Contact Us' — not outcome-driven"},
            {"severity": "Medium", "finding": "Missing meta descriptions on 3 key pages"},
            {"severity": "Low", "finding": "Blog section has no internal links to service pages"},
        ],
        "quick_wins": [
            "Add 3 client testimonials with name, role, and specific result to homepage",
            "Change CTA from 'Contact Us' to 'Get Your Free Marketing Audit'",
            "Write meta descriptions for all service pages (max 155 chars each)",
        ],
        "medium_term": [
            "Build a case study page with 3 detailed client results",
            "Create a lead magnet (e.g. '10-Point Marketing Audit Checklist')",
        ],
        "strategic": [
            "Develop a comparison page: 'Heyeye vs. traditional agency'",
            "Launch a referral program for existing clients",
        ],
        "copy_examples": [],
        "competitors": [],
        "roadmap": "",
        "cost_usd": 0.0,
    }

    from ventures.marketing_audit.pipeline import _generate_pdf, _build_markdown, _score_grade
    from ventures.marketing_audit.sample_report import generate_sample_pdf, generate_sample_markdown

    report_type = args.report_type
    want_full   = report_type in ("both", "full")
    want_sample = report_type in ("both", "sample")

    print(f"\nDemo mode — generating reports (type={report_type})...")

    score = sample["overall_score"]
    print(f"  Score: {score}/100 (Grade {_score_grade(score)})")

    if want_full:
        pdf_path = output_dir / f"{order_id}-audit.pdf"
        md_path = output_dir / f"{order_id}-audit.md"
        _generate_pdf(sample, str(pdf_path))
        md_path.write_text(_build_markdown(sample), encoding="utf-8")
        print(f"  Full PDF:   {pdf_path}")
        print(f"  Full MD:    {md_path}")

    if want_sample:
        sample_pdf_path = output_dir / f"{order_id}-audit-sample.pdf"
        sample_md_path = output_dir / f"{order_id}-audit-sample.md"
        generate_sample_pdf(sample, str(sample_pdf_path))
        sample_md_path.write_text(generate_sample_markdown(sample), encoding="utf-8")
        print(f"  Sample PDF: {sample_pdf_path}")
        print(f"  Sample MD:  {sample_md_path}")


def _find_scripts_path() -> str:
    import os
    env = os.environ.get("AI_MARKETING_CLAUDE_PATH", "")
    if env:
        return str(Path(env) / "scripts")
    candidate = Path(__file__).parent.parent.parent / "ai-marketing-claude" / "scripts"
    return str(candidate) if candidate.exists() else ""


if __name__ == "__main__":
    main()
