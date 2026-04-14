#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
"""
DEPRECATED — project management has moved to Jira (project AII, aiinfra.atlassian.net).
This script is kept for historical reference only and should not be run.

Original purpose: sync task statuses → ROADMAP.md.
Equivalent functionality now lives in scripts/sync_jira_to_roadmap.py (if built).

Usage:
    python scripts/sync_clickup_to_roadmap.py
    python scripts/sync_clickup_to_roadmap.py --dry-run       # show diffs without writing
    python scripts/sync_clickup_to_roadmap.py --roadmap-wins  # ROADMAP.md wins on conflict

Conflict rule:
    ClickUp is the source of truth after initial seeding.
    Use --roadmap-wins only for recovery.

Status mapping (ClickUp → ROADMAP.md):
    Backlog             → idea
    Planned             → planned
    In Progress         → in-progress
    Review              → in-progress
    Ready For Deployment→ in-progress
    Done                → done
    On Hold             → on-hold
    Blocked             → planned   (+ blocker note appended to description)
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from aiplatform.skills.comms.update_project_board import get_all_tasks

ROADMAP_PATH = Path(__file__).parent.parent / "ROADMAP.md"

LISTS = {
    "Platform":         os.getenv("CLICKUP_LIST_PLATFORM",        "901816916122"),
    "Etsy":             os.getenv("CLICKUP_LIST_ETSY",             "901816916147"),
    "Marketing Audit":  os.getenv("CLICKUP_LIST_MARKETING_AUDIT",  "901816916048"),
    "Podcast Notes":    os.getenv("CLICKUP_LIST_PODCAST_NOTES",    "901816916125"),
    "Content Channels": os.getenv("CLICKUP_LIST_CONTENT_CHANNELS", "901816916113"),
}

# ClickUp Free default status → ROADMAP.md status
# ClickUp Free has: "to do" (open), "in progress" (custom), "complete" (closed)
CLICKUP_TO_ROADMAP = {
    "to do":       "planned",
    "in progress": "in-progress",
    "complete":    "done",
    # In case workspace is ever upgraded to custom statuses:
    "backlog":              "idea",
    "planned":              "planned",
    "review":               "in-progress",
    "ready for deployment": "in-progress",
    "done":                 "done",
    "on hold":              "on-hold",
    "blocked":              "planned",
}


# ─── Collect ClickUp state ────────────────────────────────────────────────────

def fetch_all_clickup_tasks(api_key: str) -> dict[str, dict]:
    """
    Return {roadmap_id: {status, name, description}} for every task
    that has a roadmap_id custom field set.
    """
    result = {}
    for space, list_id in LISTS.items():
        print(f"  Fetching {space}...", end=" ", flush=True)
        tasks = get_all_tasks(list_id, api_key)
        count = 0
        for task in tasks:
            rid = (task.get("custom_fields") or {}).get("roadmap_id")
            if rid:
                result[rid] = {
                    "status":      (task.get("status") or "").lower(),
                    "name":        task.get("name", ""),
                    "description": task.get("description", ""),
                    "url":         task.get("url", ""),
                }
                count += 1
        print(f"{count} tasks with roadmap_id")
        time.sleep(0.2)
    return result


# ─── ROADMAP.md parsing + patching ───────────────────────────────────────────

# Priority table regex: matches a data row that starts with | X-## |
_ROW_RE = re.compile(
    r"(\|\s*"               # opening pipe
    r"([A-Z]-\d+)"          # roadmap ID
    r"\s*\|"                # separator
    r"[^|]+"                # name col
    r"\|"                   # separator
    r"[^|]+"                # type col
    r"\|"                   # separator
    r"\s*)`([^`]+)`"        # status col (backtick-wrapped)
    r"(\s*\|.*)"            # rest of row
)

# Done table row regex (different columns: #, Name, Type, Completed, Notes)
_DONE_ROW_RE = re.compile(
    r"(\|\s*([A-Z]-\d+)\s*\|.*)"
)

def patch_roadmap(
    text: str,
    clickup_tasks: dict[str, dict],
    roadmap_wins: bool,
    dry: bool,
) -> tuple[str, int, int, int]:
    """
    Update status backtick values in ROADMAP.md rows to match ClickUp.
    Items newly Done in ClickUp are moved to the ✅ Done table.

    Returns: (new_text, updated_count, moved_to_done_count, unchanged_count)
    """
    lines = text.splitlines(keepends=True)
    updated = 0
    moved = 0
    unchanged = 0
    ids_to_move: list[str] = []   # roadmap IDs whose rows need to move to Done

    new_lines = []
    in_done_table = False

    for line in lines:
        # Track when we enter the Done table
        if "## ✅ Done" in line:
            in_done_table = True

        if in_done_table:
            new_lines.append(line)
            continue

        # Match a regular priority table row
        m = _ROW_RE.match(line.rstrip("\n"))
        if not m:
            new_lines.append(line)
            continue

        roadmap_id = m.group(2)
        current_status = m.group(3).strip()  # e.g. "in-progress"

        cu_task = clickup_tasks.get(roadmap_id)
        if not cu_task:
            new_lines.append(line)
            unchanged += 1
            continue

        cu_raw = cu_task["status"]
        new_status = CLICKUP_TO_ROADMAP.get(cu_raw, current_status)

        if roadmap_wins:
            # ROADMAP.md wins — no change to status, but print what ClickUp says
            if new_status != current_status:
                print(f"  CONFLICT {roadmap_id}: ClickUp={new_status}, ROADMAP={current_status} → keeping ROADMAP (--roadmap-wins)")
            new_lines.append(line)
            unchanged += 1
            continue

        if new_status == current_status:
            new_lines.append(line)
            unchanged += 1
            continue

        # Status changed
        print(f"  ~ {roadmap_id}: `{current_status}` → `{new_status}`")

        if new_status == "done":
            # Mark for moving to Done table — remove from current section
            ids_to_move.append(roadmap_id)
            if not dry:
                continue   # skip appending the row (will be added to Done table)
            else:
                # In dry run, show the change but keep the row
                patched = line.rstrip("\n").replace(
                    f"`{current_status}`", f"`{new_status}`"
                )
                new_lines.append(patched + "\n")
                moved += 1
                continue

        # Normal status update
        if not dry:
            patched = line.rstrip("\n").replace(
                f"`{current_status}`", f"`{new_status}`"
            )
            new_lines.append(patched + "\n")
        else:
            new_lines.append(line)
        updated += 1

    # ── Append moved items to Done table ──────────────────────────────────────
    if ids_to_move and not dry:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        done_rows = []
        # Re-parse original text to get name/type/notes for moved items
        for orig_line in text.splitlines():
            m2 = _ROW_RE.match(orig_line.strip())
            if not m2:
                continue
            rid = m2.group(2)
            if rid not in ids_to_move:
                continue
            # Extract cols
            parts = [c.strip() for c in orig_line.split("|")[1:-1]]
            if len(parts) >= 5:
                name = parts[1]
                item_type = parts[2]
                desc = parts[4][:80] + ("..." if len(parts[4]) > 80 else "")
                done_rows.append(f"| {rid} | {name} | {item_type} | {today} | {desc} |\n")
                moved += 1

        # Insert rows just before the closing of the Done table
        final = []
        for line in new_lines:
            final.append(line)
            if "## ✅ Done" in line:
                # The table header comes a few lines later; insert before end of file
                pass
        # Append to end of Done table (before any trailing whitespace)
        for row in done_rows:
            final.append(row)
        new_lines = final

    return "".join(new_lines), updated, moved, unchanged


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync ClickUp → ROADMAP.md")
    parser.add_argument("--dry-run",      action="store_true", help="Show diffs without writing")
    parser.add_argument("--roadmap-wins", action="store_true", help="ROADMAP.md wins on conflict")
    args = parser.parse_args()
    dry = args.dry_run

    api_key = os.environ.get("CLICKUP_API_KEY", "")
    if not api_key:
        print("ERROR: CLICKUP_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print(f"\nSync ClickUp → ROADMAP.md")
    print(f"Mode: {'DRY RUN' if dry else 'LIVE'}")
    if args.roadmap_wins:
        print("Conflict resolution: ROADMAP.md wins")
    print()

    print("Fetching tasks from ClickUp...")
    tasks = fetch_all_clickup_tasks(api_key)
    print(f"  Total: {len(tasks)} tasks with roadmap_id\n")

    if not tasks:
        print("No tasks found — is the workspace seeded? Run seed_clickup_from_roadmap.py first.")
        return

    text = ROADMAP_PATH.read_text(encoding="utf-8")
    new_text, updated, moved, unchanged = patch_roadmap(
        text, tasks, args.roadmap_wins, dry
    )

    print(f"\nResult: {updated} updated, {moved} moved to Done, {unchanged} unchanged.")

    if dry:
        print("(Dry run — no changes written.)\n")
        return

    if updated > 0 or moved > 0:
        ROADMAP_PATH.write_text(new_text, encoding="utf-8")
        print(f"ROADMAP.md written.\n")
    else:
        print("ROADMAP.md unchanged — already in sync.\n")


if __name__ == "__main__":
    main()
