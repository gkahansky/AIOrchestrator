#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
"""
Seed ClickUp from ROADMAP.md — one-time + idempotent re-run.

Parses every item in ROADMAP.md and creates a ClickUp task in the correct Space.
Tasks already matching a `roadmap_id` custom field are skipped (not overwritten).

Usage:
    python scripts/seed_clickup_from_roadmap.py
    python scripts/seed_clickup_from_roadmap.py --dry-run   # preview without creating
    python scripts/seed_clickup_from_roadmap.py --space "Podcast Notes"  # one space only

Space assignment (first match wins):
    H-09 / M-09, or "dashboard"/"management app" → Platform  (Management Console merged)
    type=System                                   → Platform
    "etsy" in description                         → Etsy
    "marketing_audit"/"marketing audit"           → Marketing Audit
    "podcast"/"content_studio"/"podcast_notes"    → Podcast Notes
    "content_channel"                             → Content Channels
    default                                       → Platform

Status mapping: idea→Backlog, planned→Planned, in-progress→In Progress,
                done→Done, on-hold→On Hold, pending→Planned
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from aiplatform.skills.comms.update_project_board import (
    create_task, find_task_by_roadmap_id, get_list_custom_fields
)

ROADMAP_PATH = Path(__file__).parent.parent / "ROADMAP.md"

LISTS = {
    "Platform":         os.getenv("CLICKUP_LIST_PLATFORM",        "901816916122"),
    "Etsy":             os.getenv("CLICKUP_LIST_ETSY",             "901816916147"),
    "Marketing Audit":  os.getenv("CLICKUP_LIST_MARKETING_AUDIT",  "901816916048"),
    "Podcast Notes":    os.getenv("CLICKUP_LIST_PODCAST_NOTES",    "901816916125"),
    "Content Channels": os.getenv("CLICKUP_LIST_CONTENT_CHANNELS", "901816916113"),
}

# ClickUp Free default statuses: "to do" / "in progress" / "complete"
# Custom statuses require a paid ClickUp plan.
STATUS_MAP = {
    "idea":        "to do",
    "planned":     "to do",
    "in-progress": "in progress",
    "done":        "complete",
    "on-hold":     "to do",
    "pending":     "to do",
}

VENTURE_MAP = {
    "Platform":         "Platform",
    "Etsy":             "Etsy",
    "Marketing Audit":  "Marketing Audit",
    "Podcast Notes":    "Podcast Notes",
    "Content Channels": "Content Channels",
}


# ─── ROADMAP.md parser ────────────────────────────────────────────────────────

def parse_roadmap(path: Path) -> list[dict]:
    """
    Parse ROADMAP.md and return a flat list of items.
    Each item: {id, name, type, status, description, priority, section}
    """
    text = path.read_text(encoding="utf-8")
    items = []

    # Priority section headers
    priority_map = {
        "🔴 Urgent": "Urgent",
        "🟠 High":   "High",
        "🟡 Medium": "Medium",
        "🔵 Low":    "Low",
        "✅ Done":   "Done-section",
    }

    current_priority = "Medium"
    in_table = False
    header_cols: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()

        # Detect section header
        for marker, priority in priority_map.items():
            if marker in stripped and stripped.startswith("##"):
                current_priority = priority
                in_table = False
                header_cols = []
                break

        # Detect table header row
        if stripped.startswith("|") and not stripped.startswith("| #") and "---" in stripped:
            in_table = True
            continue

        if stripped.startswith("| #") or stripped.startswith("| Roadmap"):
            # Header row
            header_cols = [c.strip() for c in stripped.split("|")[1:-1]]
            in_table = True
            continue

        # Table data row
        if in_table and stripped.startswith("|") and "---" not in stripped:
            cols = [c.strip() for c in stripped.split("|")[1:-1]]
            if not cols or not cols[0]:
                continue

            row = dict(zip(header_cols, cols))
            item_id = row.get("#", "").strip()
            # Skip header rows and the template placeholder row at the bottom
            if not item_id or item_id == "#" or item_id == "X-##":
                continue

            # Strip backtick wrapping from status
            raw_status = re.sub(r"`", "", row.get("Status", row.get("Completed", "planned"))).strip().lower()
            # Map "done-section" items (the ✅ Done table)
            if current_priority == "Done-section":
                raw_status = "done"

            item_type = re.sub(r"`", "", row.get("Type", "System")).strip()
            description = row.get("Description", row.get("Notes", "")).strip()
            name = row.get("Name", row.get("Task Name", "")).strip()

            items.append({
                "id":          item_id,
                "name":        name,
                "type":        item_type,
                "status":      raw_status,
                "description": description,
                "priority":    current_priority if current_priority != "Done-section" else "Low",
                "section":     current_priority,
            })

    return items


# ─── Space assignment ─────────────────────────────────────────────────────────

def assign_space(item: dict) -> str:
    """Map a ROADMAP item to a ClickUp space name."""
    roadmap_id = item.get("id", "")
    desc = (item.get("description") or "").lower()
    name = (item.get("name") or "").lower()
    combined = name + " " + desc

    # Management Console items → Platform (5-space free-tier limit)
    if roadmap_id in ("H-09", "M-09"):
        return "Platform"
    if "management console" in combined or "management app" in combined or "dashboard" in combined:
        return "Platform"

    # System items → Platform (unless venture-specific below)
    if item.get("type") == "System":
        return "Platform"

    # Venture-specific matching (check name + description)
    if "etsy" in combined:
        return "Etsy"
    if "marketing_audit" in combined or "marketing audit" in combined:
        return "Marketing Audit"
    if any(k in combined for k in ("podcast", "content_studio", "podcast_notes", "show notes", "episode")):
        return "Podcast Notes"
    if "content_channel" in combined or "content channels" in combined:
        return "Content Channels"

    return "Platform"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed ClickUp from ROADMAP.md")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating tasks")
    parser.add_argument("--space", help="Only seed this space (e.g. 'Podcast Notes')")
    args = parser.parse_args()
    dry = args.dry_run

    api_key = os.environ.get("CLICKUP_API_KEY", "")
    if not api_key:
        print("ERROR: CLICKUP_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print(f"\nSeed ClickUp from ROADMAP.md")
    print(f"Mode: {'DRY RUN (no changes)' if dry else 'LIVE'}")
    if args.space:
        print(f"Filter: space='{args.space}'")
    print()

    items = parse_roadmap(ROADMAP_PATH)
    print(f"Parsed {len(items)} items from ROADMAP.md\n")

    # Check custom fields are set up on each list
    field_check_done = set()

    created = 0
    skipped = 0
    errors = 0

    for item in items:
        space = assign_space(item)
        if args.space and space != args.space:
            continue

        list_id = LISTS.get(space)
        if not list_id:
            print(f"  ✗ {item['id']}: no list_id for space '{space}'")
            errors += 1
            continue

        # Verify custom fields are available (once per list)
        if list_id not in field_check_done and not dry:
            fields = get_list_custom_fields(list_id, api_key)
            field_names = {f["name"] for f in fields}
            if "roadmap_id" not in field_names:
                print(f"  ⚠  List {list_id} ({space}) missing 'roadmap_id' custom field.")
                print(f"     Run: python scripts/setup_clickup_workspace.py")
            field_check_done.add(list_id)

        # Check if task already exists
        existing = None if dry else find_task_by_roadmap_id(list_id, item["id"], api_key)
        if existing:
            print(f"  — {item['id']:6s} [{space}] already exists → skip")
            skipped += 1
            continue

        clickup_status = STATUS_MAP.get(item["status"], "Backlog")
        # Venture field value — use Management Console label for those items
        is_mgmt_console = item["id"] in ("H-09", "M-09") or "management" in (item.get("description") or "").lower()
        venture_value = "Management Console" if is_mgmt_console else VENTURE_MAP.get(space, space)

        cf = {
            "roadmap_id": item["id"],
            "type":       item.get("type", "System"),
            "venture":    venture_value,
        }

        if dry:
            print(f"  + {item['id']:6s} [{space:17s}] {clickup_status:15s} — {item['name'][:60]}")
        else:
            result = create_task(
                list_id=list_id,
                name=f"[{item['id']}] {item['name']}",
                status=clickup_status,
                description=item.get("description", ""),
                custom_fields=cf,
                api_key=api_key,
            )
            if "error" in result:
                print(f"  ✗ {item['id']:6s} [{space}]: {result['error']}")
                errors += 1
            else:
                print(f"  ✓ {item['id']:6s} [{space:17s}] {clickup_status:15s} — {item['name'][:55]}")
                created += 1
            time.sleep(0.35)   # stay well under 100 req/min

    print(f"\nDone: {created} created, {skipped} skipped, {errors} errors.\n")
    if dry:
        print("Re-run without --dry-run to create tasks.")


if __name__ == "__main__":
    main()
