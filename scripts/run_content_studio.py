#!/usr/bin/env python3
# Force UTF-8 output so Unicode characters (✓ ⚠ etc.) render on all terminals.
import sys, io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

"""
Manual trigger for Content Studio pipeline — Sprint 1 & 2.

New order:
    python scripts/run_content_studio.py \\
        --audio /path/to/episode.mp3 \\
        --tier standard \\
        --show-name "My Podcast" \\
        --episode-title "Ep 42: Growing a SaaS" \\
        --host-name "Jane Smith" \\
        --niche business \\
        --audience "early-stage founders" \\
        --client-email client@example.com \\
        [--order-id my-custom-id]

Resume a paused order (after manual approval):
    python scripts/run_content_studio.py --resume --order-id <order_id>

Demo mode — generate PDFs only from canned content (no audio required):
    python scripts/run_content_studio.py --demo \\
        --tier premium \\
        --show-name "The SaaS Founders Pod" \\
        --episode-title "Ep 1: Finding Product-Market Fit"

Generate PDFs only from an existing completed order:
    python scripts/run_content_studio.py --pdf-only --order-id <order_id>
"""

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add src/ to sys.path so venture + platform imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ventures.content_studio.pipeline import run_order, work_dir_for, _load_json


DEMO_TRANSCRIPT = """
Welcome to the SaaS Founders Pod. I'm your host, and today we're talking about finding
product-market fit — the single hardest thing in building a software company.

My guest today spent three years pivoting before landing on a product that grew from
zero to one million ARR in 18 months. We cover the signals that told them they'd found
it, how to know when you haven't found it yet, and the tactical decisions that accelerated
their growth once the fit was clear.

[00:02:15] The founding story
[00:08:45] The three failed pivots
[00:17:20] The moment they knew
[00:25:00] From product-market fit to growth
[00:38:30] Hiring your first 10 people after fit
[00:51:00] Advice for founders still searching
"""

DEMO_CONTENT = {
    "show_notes": (
        "In this episode we explore what product-market fit really means for early-stage "
        "SaaS founders — beyond the buzzword.\n\n"
        "Our guest shares the story of three failed product pivots before landing on the "
        "version of their product that resonated. They describe the specific retention and "
        "engagement signals that told them they'd finally found fit, and contrast those "
        "signals with the false positives that had misled them in earlier attempts.\n\n"
        "We also cover the tactical decisions made in the 90 days after achieving fit — "
        "the hires, the pricing changes, and the channel bets that accelerated growth from "
        "$0 to $1M ARR in under 18 months."
    ),
    "timestamps": (
        "[00:02:15] The founding story — how the company started\n"
        "[00:08:45] Three failed pivots: what went wrong and what was learned\n"
        "[00:17:20] The signals that confirmed product-market fit\n"
        "[00:25:00] Translating fit into growth: first 90-day playbook\n"
        "[00:38:30] Hiring your first 10 people once fit is confirmed\n"
        "[00:51:00] Advice for founders still searching for fit"
    ),
    "guest_bio": (
        "Our guest is the co-founder and CEO of a B2B SaaS company serving operations "
        "teams at mid-market logistics firms. Before this company they built and sold two "
        "smaller software products. They write about B2B growth at their personal blog and "
        "are a limited partner in two early-stage funds focused on vertical SaaS."
    ),
    "transcript": (
        "Host: Welcome to the show. Tell us how the company started.\n\n"
        "Guest: Thanks for having me. We started in 2019 with a completely different idea — "
        "we were building scheduling software for fitness studios. Terrible timing and terrible "
        "market. We ran out of money twice and nearly shut down. What saved us was a customer "
        "conversation where someone asked if we could solve a completely different problem "
        "they had in their warehouse operations.\n\n"
        "Host: What did the pivot look like?\n\n"
        "Guest: Painful and slow. We had three months of runway. We killed the old product "
        "and started talking to logistics companies every day. The second pivot was just as "
        "bad — we built something nobody wanted again. The third time we had learned enough "
        "to validate before building. That was the product that worked."
    ),
    "social_captions": (
        "LinkedIn:\n"
        "Three failed pivots. Nearly out of money. Then one customer conversation changed "
        "everything.\n\n"
        "This week on the pod: how one founder went from the brink of shutting down to "
        "$1M ARR in 18 months. The signals that told them they'd found product-market fit — "
        "and the false positives that had fooled them before. 🎙️\n\n"
        "Link in bio.\n\n"
        "---\n\n"
        "Twitter/X:\n"
        "New episode: 3 pivots, almost out of money, then $0→$1M ARR in 18 months.\n\n"
        "The specific signals that told them they'd finally found PMF. Worth a listen.\n\n"
        "---\n\n"
        "Instagram:\n"
        "Product-market fit isn't a moment — it's a slow accumulation of signals you learn "
        "to read. This week's guest explains exactly what those signals looked like for them. "
        "New episode out now. 🎧"
    ),
    "newsletter_excerpt": (
        "This week I sat down with a founder who spent three years in pivot hell before "
        "finding the product that worked. What struck me most wasn't the success story — "
        "it was how clearly they could describe the difference between the signals that "
        "had fooled them (early revenue from the wrong customers, polite praise from "
        "non-buyers) and the signals that told them they'd actually found it (unexpected "
        "inbound, customers angry when the product went down, referrals they didn't ask for).\n\n"
        "If you're a founder still searching for fit, this episode is worth your full "
        "attention. Listen here: [LINK]"
    ),
    "seo_metadata": (
        "Title: Finding Product-Market Fit: From 3 Failed Pivots to $1M ARR | SaaS Founders Pod\n"
        "Description: In this episode, a SaaS founder shares how they survived three failed "
        "product pivots to find product-market fit and grow from zero to $1M ARR in 18 months. "
        "Covers PMF signals, hiring after fit, and the 90-day post-fit playbook.\n"
        "Keywords: product-market fit, SaaS founders, startup pivots, ARR growth, B2B SaaS, "
        "startup advice, founder stories, PMF signals\n"
        "Episode category: Entrepreneurship / SaaS\n"
        "Duration: ~55 minutes"
    ),
}


def main():
    parser = argparse.ArgumentParser(description="Content Studio pipeline — manual trigger")

    # New order args
    parser.add_argument("--audio", help="Path to the podcast audio file")
    parser.add_argument("--tier", choices=["starter", "standard", "premium"], default="standard")
    parser.add_argument("--show-name", default="Unknown Show")
    parser.add_argument("--episode-title", default="Unknown Episode")
    parser.add_argument("--host-name", default="")
    parser.add_argument("--niche", default="general")
    parser.add_argument("--audience", default="general audience")
    parser.add_argument("--client-email", default="")

    # Add-ons
    parser.add_argument(
        "--addons",
        nargs="*",
        default=[],
        metavar="ADDON",
        help=(
            "Add-ons to run after packaging. Space-separated. "
            "Available: brand-voice, promo-copy. "
            "Example: --addons brand-voice promo-copy"
        ),
    )
    parser.add_argument(
        "--extra-transcripts",
        nargs="*",
        default=[],
        metavar="PATH",
        help="Paths to extra episode transcript .txt files (for brand-voice add-on; 2-3 episodes recommended)",
    )

    # Mode flags
    parser.add_argument("--resume", action="store_true", help="Resume a paused order")
    parser.add_argument("--demo", action="store_true",
                        help="Demo mode: generate PDFs from canned content, no audio required")
    parser.add_argument("--pdf-only", action="store_true",
                        help="Re-generate PDFs from an existing completed order")
    parser.add_argument("--order-id", help="Order ID (auto-generated if not supplied)")
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Mark order as approved before resuming (use with --resume)",
    )

    parser.add_argument(
        "--output-dir",
        default="./output/content_studio",
        help="Local working directory for order files",
    )

    args = parser.parse_args()

    if args.demo:
        _demo_mode(args)
    elif args.pdf_only:
        _pdf_only_mode(args)
    elif args.resume:
        _resume_order(args)
    else:
        _new_order(args)


def _new_order(args):
    if not args.audio:
        print("ERROR: --audio is required for a new order. Use --demo for a demo run.", file=sys.stderr)
        sys.exit(1)

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"ERROR: Audio file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    order_id = args.order_id or f"cs-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    order = {
        "order_id":          order_id,
        "audio_path":        str(audio_path.resolve()),
        "tier":              args.tier,
        "show_name":         args.show_name,
        "episode_title":     args.episode_title,
        "host_name":         args.host_name,
        "niche":             args.niche,
        "audience":          args.audience,
        "client_email":      args.client_email,
        "add_ons":           args.addons,
        "extra_transcripts": args.extra_transcripts,
        "status":            "pending",
        "created_at":        datetime.utcnow().isoformat(),
    }

    print(f"\nContent Studio — New Order")
    print(f"  Order ID:  {order_id}")
    print(f"  Show:      {args.show_name}")
    print(f"  Episode:   {args.episode_title}")
    print(f"  Tier:      {args.tier.upper()}")
    print(f"  Audio:     {audio_path.name}")
    if args.addons:
        print(f"  Add-ons:   {', '.join(args.addons)}")
    print()

    run_order(order, output_dir=args.output_dir)


def _resume_order(args):
    if not args.order_id:
        print("ERROR: --order-id is required to resume an order.", file=sys.stderr)
        sys.exit(1)

    order_path = Path(args.output_dir) / args.order_id / "order.json"
    if not order_path.exists():
        print(f"ERROR: Order file not found: {order_path}", file=sys.stderr)
        sys.exit(1)

    order = _load_json(order_path)

    if args.approve:
        if order["status"] != "review_pending":
            print(f"WARNING: Order status is '{order['status']}', not 'review_pending'. Approving anyway.")
        order["status"] = "approved"
        order_path.write_text(json.dumps(order, indent=2, default=str), encoding="utf-8")
        print(f"Order {args.order_id} marked as approved.")

    print(f"\nContent Studio — Resuming Order {args.order_id} (status: {order['status']})")
    run_order(order, output_dir=args.output_dir)


def _demo_mode(args):
    """
    Generate full and sample PDFs from canned content — no audio file required.
    Useful for testing PDF layout and for outreach demo materials.
    """
    from ventures.content_studio.content_pdf import generate_full_pdf, generate_sample_pdf

    order_id = args.order_id or f"demo-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    work_dir = Path(args.output_dir) / order_id
    work_dir.mkdir(parents=True, exist_ok=True)

    order = {
        "order_id": order_id,
        "tier": args.tier,
        "show_name": args.show_name,
        "episode_title": args.episode_title,
        "host_name": args.host_name,
        "niche": args.niche,
        "audience": args.audience,
        "client_email": args.client_email,
        "status": "demo",
        "created_at": datetime.utcnow().isoformat(),
    }

    # Use all demo sections regardless of tier (demo shows full value)
    content = DEMO_CONTENT.copy()

    print(f"\nContent Studio — Demo Mode")
    print(f"  Order ID: {order_id}")
    print(f"  Show:     {args.show_name}")
    print(f"  Episode:  {args.episode_title}")
    print(f"  Tier:     {args.tier.upper()}")
    print()

    full_path = work_dir / f"{order_id}-full.pdf"
    sample_path = work_dir / f"{order_id}-sample.pdf"

    generate_full_pdf(order, content, full_path)
    print(f"  OK Full PDF:   {full_path}")

    generate_sample_pdf(order, content, sample_path)
    print(f"  OK Sample PDF: {sample_path}")
    print()


def _pdf_only_mode(args):
    """Re-generate PDFs from an existing completed order's content.json."""
    from ventures.content_studio.content_pdf import generate_full_pdf, generate_sample_pdf

    if not args.order_id:
        print("ERROR: --order-id is required for --pdf-only.", file=sys.stderr)
        sys.exit(1)

    work_dir = Path(args.output_dir) / args.order_id
    order_path = work_dir / "order.json"
    content_path = work_dir / "content.json"

    if not order_path.exists():
        print(f"ERROR: Order file not found: {order_path}", file=sys.stderr)
        sys.exit(1)
    if not content_path.exists():
        print(f"ERROR: Content file not found: {content_path}", file=sys.stderr)
        sys.exit(1)

    order = _load_json(order_path)
    content = _load_json(content_path)

    full_path = work_dir / f"{args.order_id}-full.pdf"
    sample_path = work_dir / f"{args.order_id}-sample.pdf"

    print(f"\nContent Studio -- Regenerating PDFs for {args.order_id}")
    generate_full_pdf(order, content, full_path)
    print(f"  OK Full PDF:   {full_path}")
    generate_sample_pdf(order, content, sample_path)
    print(f"  OK Sample PDF: {sample_path}")
    print()


if __name__ == "__main__":
    main()
