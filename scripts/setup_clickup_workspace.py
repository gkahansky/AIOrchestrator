#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
"""
DEPRECATED — project management has moved to Jira (project AII, aiinfra.atlassian.net).
This script is kept for historical reference only and should not be run.

Original purpose: one-time workspace setup script.
  - Renames "Market Audit" space → "Marketing Audit"
  - Renames all lists from "List" → "Tasks"
  - Configures shared status set on all spaces
  - Creates 5 custom fields on each list
  - Prints .env additions to paste in

Run once after creating the workspace and API key:
    python scripts/setup_clickup_workspace.py
    python scripts/setup_clickup_workspace.py --dry-run   # preview only

NOTE: Management Console space is mapped to Platform (free tier: 5-space limit).
"""

import argparse
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

BASE_URL  = "https://api.clickup.com/api/v2"
TEAM_ID   = "90182561940"
API_KEY   = os.environ.get("CLICKUP_API_KEY", "")

# Known space IDs discovered on 2026-03-26
SPACES = {
    "Marketing Audit":  "901810352640",
    "Content Channels": "901810352669",
    "Platform":         "901810352672",
    "Podcast Notes":    "901810352675",
    "Etsy":             "901810352681",
    # Management Console → Platform (free tier 5-space limit)
}

# Lists to rename: space_name → list_id
LISTS = {
    "Marketing Audit":  "901816916048",
    "Content Channels": "901816916113",
    "Platform":         "901816916122",
    "Podcast Notes":    "901816916125",
    "Etsy":             "901816916147",
}

STATUSES = [
    {"status": "Backlog",              "color": "#808080", "type": "open"},
    {"status": "Planned",              "color": "#87CEEB", "type": "open"},
    {"status": "In Progress",          "color": "#F6C90E", "type": "open"},
    {"status": "Review",               "color": "#4169E1", "type": "open"},
    {"status": "Ready For Deployment", "color": "#0075FF", "type": "open"},
    {"status": "On Hold",              "color": "#FF7800", "type": "open"},
    {"status": "Blocked",              "color": "#FF0000", "type": "open"},
    {"status": "Done",                 "color": "#008000", "type": "done"},
]

CUSTOM_FIELDS = [
    {
        "name": "roadmap_id",
        "type": "text",
        "required": False,
    },
    {
        "name": "type",
        "type": "drop_down",
        "required": False,
        "type_config": {"options": [{"name": "Venture"}, {"name": "System"}]},
    },
    {
        "name": "venture",
        "type": "drop_down",
        "required": False,
        "type_config": {"options": [
            {"name": "Platform"},
            {"name": "Etsy"},
            {"name": "Marketing Audit"},
            {"name": "Podcast Notes"},
            {"name": "Content Channels"},
            {"name": "Management Console"},
        ]},
    },
    {
        "name": "blocked_by",
        "type": "text",
        "required": False,
    },
]


def headers():
    return {"Authorization": API_KEY, "Content-Type": "application/json"}


def get(path, params=None):
    r = requests.get(BASE_URL + path, params=params or {}, headers=headers(), timeout=15)
    return r.json()


def put(path, payload):
    r = requests.put(BASE_URL + path, json=payload, headers=headers(), timeout=15)
    return r.json()


def post(path, payload):
    r = requests.post(BASE_URL + path, json=payload, headers=headers(), timeout=15)
    return r.json()


def step(msg: str, dry: bool):
    prefix = "[DRY RUN] " if dry else "  "
    print(f"{prefix}{msg}")


def main():
    parser = argparse.ArgumentParser(description="ClickUp workspace setup")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making API calls")
    args = parser.parse_args()
    dry = args.dry_run

    if not API_KEY:
        print("ERROR: CLICKUP_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    print(f"\nClickUp Workspace Setup — Team: {TEAM_ID}")
    print(f"Mode: {'DRY RUN (no changes)' if dry else 'LIVE'}\n")

    # ── Step 1: Rename "Market Audit" space ────────────────────────────────────
    print("Step 1 — Rename spaces")
    space_id = SPACES["Marketing Audit"]
    space = get(f"/space/{space_id}")
    current_name = space.get("name", "")
    if current_name == "Marketing Audit":
        print(f"  ✓ Already named 'Marketing Audit' — skip")
    else:
        step(f"Rename space {space_id} '{current_name}' → 'Marketing Audit'", dry)
        if not dry:
            r = put(f"/space/{space_id}", {"name": "Marketing Audit"})
            if "err" in r:
                print(f"  ✗ Failed: {r['err']}")
            else:
                print(f"  ✓ Renamed")

    # ── Step 2: Rename lists ───────────────────────────────────────────────────
    print("\nStep 2 — Rename lists 'List' → 'Tasks'")
    for space_name, list_id in LISTS.items():
        r = get(f"/list/{list_id}")
        current = r.get("name", "")
        if current == "Tasks":
            print(f"  ✓ {space_name}: already 'Tasks'")
        else:
            step(f"{space_name}: rename '{current}' → 'Tasks'", dry)
            if not dry:
                put(f"/list/{list_id}", {"name": "Tasks"})
                time.sleep(0.3)

    # ── Step 3: Statuses ───────────────────────────────────────────────────────
    print("\nStep 3 — Statuses")
    print("  ClickUp Free uses 3 fixed statuses: 'to do' / 'in progress' / 'complete'")
    print("  Custom status sets require a paid ClickUp plan — skipping this step.")
    print("  The seed + sync scripts use these 3 defaults automatically.")

    # ── Step 4: Create custom fields on each list ──────────────────────────────
    print("\nStep 4 — Create custom fields on each list")
    for space_name, list_id in LISTS.items():
        print(f"  {space_name} (list {list_id}):")
        existing_fields = get(f"/list/{list_id}/field").get("fields", [])
        existing_names = {f.get("name") for f in existing_fields}

        for field_def in CUSTOM_FIELDS:
            fname = field_def["name"]
            if fname in existing_names:
                print(f"    ✓ '{fname}' already exists")
                continue
            step(f"Create field '{fname}' ({field_def['type']})", dry)
            if not dry:
                r = post(f"/list/{list_id}/field", field_def)
                if "err" in r:
                    print(f"      ✗ {r.get('err')}")
                else:
                    print(f"      ✓ Created (id={r.get('id', '?')[:8]}...)")
                time.sleep(0.3)

    # ── Step 5: Print .env additions ──────────────────────────────────────────
    print("\nStep 5 — .env values (add these if not already present)\n")
    env_additions = f"""# ClickUp — AI Infra workspace
CLICKUP_TEAM_ID={TEAM_ID}
CLICKUP_LIST_PLATFORM={LISTS['Platform']}
CLICKUP_LIST_ETSY={LISTS['Etsy']}
CLICKUP_LIST_MARKETING_AUDIT={LISTS['Marketing Audit']}
CLICKUP_LIST_PODCAST_NOTES={LISTS['Podcast Notes']}
CLICKUP_LIST_CONTENT_CHANNELS={LISTS['Content Channels']}
# Management Console tasks use CLICKUP_LIST_PLATFORM (free tier: 5-space limit)
"""
    print(env_additions)
    print("Setup complete.\n")
    print("Next: python scripts/seed_clickup_from_roadmap.py --dry-run")


if __name__ == "__main__":
    main()
