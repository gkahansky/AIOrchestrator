#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

"""
Update a task's status across ClickUp, ROADMAP.md, and venture CLAUDE.md.
Also appends to the rolling session log and pushes to GitHub on completion.

Usage:
    python scripts/update_task.py \\
        --id H-02 \\
        --status done \\
        --note "Fixed competitor table word wrap, added dimension details to PDF" \\
        --venture marketing_audit

    python scripts/update_task.py --id M-05 --status in-progress --note "Starting social calendar skill"
    python scripts/update_task.py --id L-06 --status blocked --note "Awaiting Etsy API key approval"

    # Show pending updates that need retry:
    python scripts/update_task.py --show-pending

Status values:
    in-progress | done | on-hold | blocked | planned | idea

Venture values (optional — auto-inferred from ROADMAP.md if omitted):
    marketing_audit | podcast_notes | content_studio | etsy | platform

GitHub push:
    Automatic when --status done. Disable with --no-push.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from aiplatform.skills.comms.sync_task_status import (
    sync_task_status,
    get_pending_updates,
)

VALID_STATUSES = {"in-progress", "done", "on-hold", "blocked", "planned", "idea"}

VALID_VENTURES = {
    "marketing_audit", "podcast_notes", "content_studio", "etsy", "platform", "content_channels"
}


def main():
    parser = argparse.ArgumentParser(
        description="Sync a task status across ClickUp, ROADMAP.md, and venture CLAUDE.md"
    )
    parser.add_argument("--id",       metavar="ROADMAP_ID", help="Roadmap ID, e.g. H-02")
    parser.add_argument("--status",   choices=sorted(VALID_STATUSES), help="New status")
    parser.add_argument("--note",     default="", help="What was done / current state (required for done/in-progress)")
    parser.add_argument("--venture",  choices=sorted(VALID_VENTURES), help="Venture slug (auto-inferred if omitted)")
    parser.add_argument("--no-push",  action="store_true", help="Skip GitHub push even when status=done")
    parser.add_argument("--show-pending", action="store_true", help="Show pending updates queue and exit")

    args = parser.parse_args()

    # ── Show pending ──────────────────────────────────────────────────────────
    if args.show_pending:
        _show_pending()
        return

    # ── Validate ──────────────────────────────────────────────────────────────
    if not args.id:
        parser.error("--id is required")
    if not args.status:
        parser.error("--status is required")
    if args.status in ("done", "in-progress") and not args.note:
        parser.error(f"--note is required when --status={args.status}")

    push = not args.no_push

    print(f"\nupdate_task — {args.id} → {args.status}")

    result = sync_task_status(
        roadmap_id=args.id,
        new_status=args.status,
        note=args.note,
        venture=args.venture,
        push_to_github=push,
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if result["success"]:
        print(f"  OK  Updated: {', '.join(result['updated'])}")
    else:
        print(f"  PARTIAL  Updated: {', '.join(result['updated'])}")
        print(f"  FAILED:  {', '.join(result['failed'])}")

    if result["pending"]:
        print(f"\n  Failures queued in logs/pending_updates.json")
        print(f"  Retry with: python scripts/retry_pending_updates.py")

    if result.get("commit_sha"):
        print(f"\n  Git: pushed (commit {result['commit_sha']})")

    sys.exit(0 if result["success"] else 1)


def _show_pending():
    items = get_pending_updates()
    if not items:
        print("\nNo pending updates. All systems in sync.\n")
        return

    print(f"\nPending updates ({len(items)} items):\n")
    for item in items:
        print(f"  {item['roadmap_id']:8s} [{item['venture']:20s}] status={item['status']:12s} failed={item['failed']}")
        print(f"           note: {item['note'][:70]}")
        print(f"           queued: {item['timestamp'][:19]}")
        print()
    print(f"Run: python scripts/retry_pending_updates.py")


if __name__ == "__main__":
    main()
