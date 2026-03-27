#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

"""
Patch ClickUp task fields:

  1. Venture field  — set the "venture" custom field on every task based on which
                     Space it lives in. Overrides: H-09, M-09 -> "Management Console".

  2. Upwork backlog — move all Upwork-related tasks (H-01, H-03, H-04, M-01, M-02)
                     to "to do" status + update blocked_by field + add a comment.

Usage:
    python scripts/patch_clickup_fields.py                # run both patches
    python scripts/patch_clickup_fields.py --venture-only # venture field only
    python scripts/patch_clickup_fields.py --upwork-only  # upwork backlog only
    python scripts/patch_clickup_fields.py --dry-run      # preview without writing
"""

import argparse
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

import requests

BASE_URL = "https://api.clickup.com/api/v2"

# Space name -> venture dropdown value
SPACE_VENTURE_MAP = {
    "Platform":         "Platform",
    "Etsy":             "Etsy",
    "Marketing Audit":  "Marketing Audit",
    "Podcast Notes":    "Podcast Notes",
    "Content Channels": "Content Channels",
}

# roadmap_id overrides (regardless of space)
ROADMAP_ID_VENTURE_OVERRIDE = {
    "H-09": "Management Console",
    "M-09": "Management Console",
}

UPWORK_ROADMAP_IDS = {"H-01", "H-03", "H-04", "M-01", "M-02"}

UPWORK_BACKLOG_NOTE = (
    "Moved to backlog — Upwork integration deferred. "
    "Focus is on Fiverr-first order flow. Revisit when Fiverr listeners are live."
)


# ─── ClickUp helpers ──────────────────────────────────────────────────────────

def _api_key():
    key = os.environ.get("CLICKUP_API_KEY", "")
    if not key:
        raise ValueError("CLICKUP_API_KEY not set in environment.")
    return key

def _headers():
    return {"Authorization": _api_key(), "Content-Type": "application/json"}

def _get(path, params=None):
    r = requests.get(BASE_URL + path, params=params or {}, headers=_headers(), timeout=15)
    time.sleep(0.2)  # stay well under 100 req/min
    return r.json()

def _put(path, payload):
    r = requests.put(BASE_URL + path, json=payload, headers=_headers(), timeout=15)
    time.sleep(0.2)
    return r.json()

def _post(path, payload):
    r = requests.post(BASE_URL + path, json=payload, headers=_headers(), timeout=15)
    time.sleep(0.2)
    return r.json()


# ─── List resolution ──────────────────────────────────────────────────────────

def _env_lists():
    """Return {list_id: space_name} from env vars."""
    mapping = {
        os.environ.get("CLICKUP_LIST_PLATFORM", ""):         "Platform",
        os.environ.get("CLICKUP_LIST_ETSY", ""):             "Etsy",
        os.environ.get("CLICKUP_LIST_MARKETING_AUDIT", ""):  "Marketing Audit",
        os.environ.get("CLICKUP_LIST_PODCAST_NOTES", ""):    "Podcast Notes",
        os.environ.get("CLICKUP_LIST_CONTENT_CHANNELS", ""): "Content Channels",
    }
    return {lid: name for lid, name in mapping.items() if lid}

def _get_all_tasks(list_id):
    tasks = []
    page = 0
    while True:
        resp = _get(f"/list/{list_id}/task", {"page": page, "include_closed": "true"})
        batch = resp.get("tasks", [])
        tasks.extend(batch)
        if resp.get("last_page") or not batch:
            break
        page += 1
    return tasks

def _get_custom_fields(list_id):
    """Return {field_name: {field_id, type, options: [str]}}."""
    resp = _get(f"/list/{list_id}/field")
    result = {}
    for f in resp.get("fields", []):
        opts = [o.get("name") for o in (f.get("type_config") or {}).get("options", [])]
        result[f.get("name", "")] = {
            "field_id": f.get("id"),
            "type":     f.get("type"),
            "options":  opts,
        }
    return result

def _get_roadmap_id(task):
    """Extract roadmap_id custom field value from a raw ClickUp task."""
    for cf in task.get("custom_fields", []):
        if cf.get("name") == "roadmap_id":
            return cf.get("value") or ""
    return ""

def _resolve_dropdown_value(field_def, value_name):
    """Return the option index for a dropdown field value name."""
    opts = field_def.get("options", [])
    if value_name in opts:
        return opts.index(value_name)
    return None


# ─── Patch 1: Venture field ───────────────────────────────────────────────────

def patch_venture_fields(dry_run=False):
    print("\n[1/2] Venture field patch")
    print(f"      Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    lists = _env_lists()
    if not lists:
        print("  No list IDs found in environment — check .env")
        return

    updated = skipped = errors = 0

    for list_id, space_name in lists.items():
        print(f"  Space: {space_name}  (list {list_id})")

        # Get field definitions for this list
        fields = _get_custom_fields(list_id)
        venture_field = fields.get("venture")
        roadmap_field = fields.get("roadmap_id")

        if not venture_field:
            print(f"    ! 'venture' custom field not found — skipping")
            continue

        tasks = _get_all_tasks(list_id)
        print(f"    {len(tasks)} tasks found")

        for task in tasks:
            task_id   = task.get("id")
            task_name = task.get("name", "")
            rid       = _get_roadmap_id(task)

            # Determine target venture value
            venture = ROADMAP_ID_VENTURE_OVERRIDE.get(rid, SPACE_VENTURE_MAP.get(space_name, "Platform"))

            # Check current value
            current = None
            for cf in task.get("custom_fields", []):
                if cf.get("name") == "venture":
                    raw_val = cf.get("value")
                    if raw_val is not None:
                        opts = (cf.get("type_config") or {}).get("options", [])
                        matched = next(
                            (o.get("name") for o in opts if str(o.get("orderindex")) == str(raw_val)),
                            None
                        )
                        current = matched or str(raw_val)
            if current == venture:
                skipped += 1
                continue

            opt_idx = _resolve_dropdown_value(venture_field, venture)
            if opt_idx is None:
                print(f"    ! [{rid or task_id}] option '{venture}' not in dropdown — skipping")
                errors += 1
                continue

            print(f"    -> [{rid or task_name[:30]}] venture = '{venture}'"
                  + (f"  (was '{current}')" if current else ""))

            if not dry_run:
                resp = _put(f"/task/{task_id}", {
                    "custom_fields": [{"id": venture_field["field_id"], "value": opt_idx}]
                })
                if "err" in resp or "error" in resp:
                    print(f"       ERROR: {resp.get('err') or resp.get('error')}")
                    errors += 1
                    continue
            updated += 1

    print(f"\n  Result: {updated} updated, {skipped} already correct, {errors} errors\n")


# ─── Patch 2: Upwork backlog ──────────────────────────────────────────────────

def patch_upwork_backlog(dry_run=False):
    print("[2/2] Upwork backlog patch")
    print(f"      Targets: {', '.join(sorted(UPWORK_ROADMAP_IDS))}")
    print(f"      Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    lists = _env_lists()
    found = {}   # roadmap_id -> {task_id, name, list_id, current_status}

    # Find all Upwork tasks across all lists
    for list_id, space_name in lists.items():
        fields = _get_custom_fields(list_id)
        blocked_by_field = fields.get("blocked_by")

        tasks = _get_all_tasks(list_id)
        for task in tasks:
            rid = _get_roadmap_id(task)
            if rid in UPWORK_ROADMAP_IDS and rid not in found:
                status_obj = task.get("status", {})
                status = status_obj.get("status") if isinstance(status_obj, dict) else str(status_obj)
                found[rid] = {
                    "task_id":            task.get("id"),
                    "name":               task.get("name", ""),
                    "list_id":            list_id,
                    "space_name":         space_name,
                    "current_status":     status,
                    "blocked_by_field_id": blocked_by_field["field_id"] if blocked_by_field else None,
                }

    missing = UPWORK_ROADMAP_IDS - set(found.keys())
    if missing:
        print(f"  ! Tasks not found in ClickUp: {', '.join(sorted(missing))}")

    if not found:
        print("  No Upwork tasks found — nothing to patch.")
        return

    updated = skipped = errors = 0

    for rid, info in sorted(found.items()):
        print(f"  [{rid}] {info['name'][:55]}")
        print(f"        Space: {info['space_name']}  |  Status: {info['current_status']}")

        if dry_run:
            print(f"        [dry-run] would set blocked_by + add comment")
            continue

        task_id = info["task_id"]
        payload = {}

        # Update blocked_by field if available
        if info["blocked_by_field_id"]:
            payload["custom_fields"] = [{
                "id":    info["blocked_by_field_id"],
                "value": "Backlog — Upwork integration deferred (Fiverr-first strategy)",
            }]

        if payload:
            resp = _put(f"/task/{task_id}", payload)
            if "err" in resp or "error" in resp:
                print(f"        ERROR updating fields: {resp.get('err') or resp.get('error')}")
                errors += 1
                continue

        # Post comment
        comment_resp = _post(f"/task/{task_id}/comment", {"comment_text": UPWORK_BACKLOG_NOTE})
        if "err" in comment_resp or "error" in comment_resp:
            print(f"        ERROR posting comment: {comment_resp.get('err') or comment_resp.get('error')}")

        print(f"        -> blocked_by set + comment posted")
        updated += 1

    if not dry_run:
        print(f"\n  Result: {updated} patched, {skipped} skipped, {errors} errors\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Patch ClickUp custom fields")
    parser.add_argument("--dry-run",      action="store_true", help="Preview without writing")
    parser.add_argument("--venture-only", action="store_true", help="Only run venture field patch")
    parser.add_argument("--upwork-only",  action="store_true", help="Only run Upwork backlog patch")
    args = parser.parse_args()

    run_venture = not args.upwork_only
    run_upwork  = not args.venture_only

    print("\nClickUp Field Patcher")
    print("=" * 40)

    if run_venture:
        patch_venture_fields(dry_run=args.dry_run)
    if run_upwork:
        patch_upwork_backlog(dry_run=args.dry_run)

    print("Done.\n")


if __name__ == "__main__":
    main()
