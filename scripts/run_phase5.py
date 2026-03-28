"""
Sprint 4 script — Phase 5: Send human review notification.

Reads Phase 4 result JSON(s) and sends email + Slack with review PDF Drive links.
Optionally polls for approval decisions before exiting.

Usage:
    # Notify for a single packaged listing:
    python scripts/run_phase5.py output/packages/botanical-01/phase4-result.json

    # Notify for multiple listings at once:
    python scripts/run_phase5.py output/packages/*/phase4-result.json

    # Notify + block until all decisions are received (or 12h timeout):
    python scripts/run_phase5.py output/packages/botanical-01/phase4-result.json --poll

Options:
    --email     Override HUMAN_REVIEW_EMAIL (default: read from .env)
    --poll      Block and poll Drive for approval decisions after notifying
    --no-drive  Skip Drive upload of review PDFs
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".ENV")

from ventures.etsy.pipeline import run_phase_5_notify, poll_for_approvals


def main():
    parser = argparse.ArgumentParser(description="Phase 5 — Send Etsy review notification")
    parser.add_argument(
        "phase4_results",
        nargs="+",
        metavar="phase4-result.json",
        help="Path(s) to phase4 result JSON file(s)",
    )
    parser.add_argument("--email",    help="Override review email address")
    parser.add_argument("--poll",     action="store_true", help="Poll for approval decisions after notifying")
    parser.add_argument("--no-drive", action="store_true", help="Skip Drive upload of review PDFs")
    args = parser.parse_args()

    # Load phase4 results
    subjects = []
    for path_str in args.phase4_results:
        for path in Path(".").glob(path_str) if "*" in path_str else [Path(path_str)]:
            if not path.exists():
                print(f"WARNING: {path} not found, skipping")
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            subjects.append(data)
            print(f"Loaded: {data.get('slug', path.stem)}")

    if not subjects:
        print("No valid phase4 results found.")
        sys.exit(1)

    print(f"\nNotifying review for {len(subjects)} listing(s)...")
    result = run_phase_5_notify(
        pending_subjects=subjects,
        review_email=args.email,
    )

    print(f"\nPhase 5 complete:")
    print(f"  Listings notified: {result['notified']}")
    print(f"  Email sent:        {'✓' if result['email_sent'] else '✗'}")
    print(f"  Slack sent:        {'✓' if result['slack_sent'] else '⚠'}")

    if args.poll:
        print(f"\nPolling for approval decisions (Ctrl+C to exit)...")
        decisions = poll_for_approvals(slugs=result["slugs"])
        print(f"\nDecisions received:")
        print(f"  Approved: {decisions['approved']}")
        print(f"  Rejected: {decisions['rejected']}")
        if decisions["still_pending"]:
            print(f"  Still pending: {decisions['still_pending']}")


if __name__ == "__main__":
    main()
