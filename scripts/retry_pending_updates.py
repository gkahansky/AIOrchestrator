#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

"""
Retry any failed sync operations from logs/pending_updates.json.

Items are added to pending_updates.json whenever update_task.py fails
to update ClickUp, ROADMAP.md, or a venture CLAUDE.md.

Usage:
    python scripts/retry_pending_updates.py             # retry all
    python scripts/retry_pending_updates.py --dry-run   # show what would be retried
    python scripts/retry_pending_updates.py --id H-02   # retry one item
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from aiplatform.skills.comms.sync_task_status import (
    sync_task_status,
    get_pending_updates,
    mark_pending_resolved,
    PENDING_UPDATES_PATH,
)
import json


def main():
    parser = argparse.ArgumentParser(description="Retry failed sync operations")
    parser.add_argument("--dry-run", action="store_true", help="Show pending items without retrying")
    parser.add_argument("--id",      metavar="ROADMAP_ID", help="Retry only this roadmap ID")
    args = parser.parse_args()

    items = get_pending_updates()

    if not items:
        print("\nNo pending updates — all systems in sync.\n")
        return

    if args.id:
        items = [i for i in items if i["roadmap_id"] == args.id]
        if not items:
            print(f"\nNo pending updates for {args.id}.\n")
            return

    print(f"\nRetry Pending Updates ({len(items)} items)")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}\n")

    resolved = []
    still_failing = []

    for item in items:
        rid     = item["roadmap_id"]
        status  = item["status"]
        note    = item["note"]
        venture = item.get("venture", "platform")
        failed  = item.get("failed", [])

        print(f"  {rid} — retrying {failed} (status={status})")

        if args.dry_run:
            print(f"    [dry-run] would retry: {failed}")
            continue

        result = sync_task_status(
            roadmap_id=rid,
            new_status=status,
            note=note,
            venture=venture,
            push_to_github=False,    # never auto-push on retry
        )

        # Check if the previously-failed systems now succeeded
        newly_resolved = [s for s in failed if s in result.get("updated", [])]
        still_failed   = [s for s in failed if s in result.get("failed", [])]

        if not still_failed:
            resolved.append(rid)
            # Remove from pending queue
            _remove_pending(rid, failed)
            print(f"    ✓ Resolved — removed from queue")
        else:
            still_failing.append(rid)
            print(f"    ✗ Still failing: {still_failed}")

    if not args.dry_run:
        print(f"\nResult: {len(resolved)} resolved, {len(still_failing)} still failing.\n")
        if still_failing:
            print(f"Items still pending: {still_failing}")
            print(f"Check logs/pending_updates.json for details.\n")


def _remove_pending(roadmap_id: str, failed_systems: list[str]) -> None:
    if not PENDING_UPDATES_PATH.exists():
        return
    existing = json.loads(PENDING_UPDATES_PATH.read_text(encoding="utf-8"))
    updated = [
        e for e in existing
        if not (e["roadmap_id"] == roadmap_id and set(e.get("failed", [])) == set(failed_systems))
    ]
    PENDING_UPDATES_PATH.write_text(json.dumps(updated, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
