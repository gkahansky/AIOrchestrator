"""
Skill: sync_task_status
Keep Jira, ROADMAP.md, and the relevant venture CLAUDE.md in sync
whenever a task status changes.

Maintains a rolling session log at logs/session_YYYY-MM-DD.md and a
pending-updates queue at logs/pending_updates.json for any sync step
that fails.

When status = "done", stages all changes and pushes to GitHub.

Usage (from pipeline or script):
    from aiplatform.skills.comms.sync_task_status import sync_task_status

    result = sync_task_status(
        roadmap_id="H-02",
        new_status="done",
        note="Fixed competitor table, added dimension details + roadmap to PDF",
        venture="marketing_audit",
    )
    # result: {success, updated, failed, pending, commit_sha}

Status values accepted:
    "in-progress" | "done" | "on-hold" | "blocked" | "planned" | "idea"
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from aiplatform.skills.comms.update_jira_board import (
    find_issue_by_label,
    transition_issue,
    add_comment,
)

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent  # AIOrchestrator/
LOGS_DIR  = REPO_ROOT / "logs"

ROADMAP_PATH = REPO_ROOT / "ROADMAP.md"

PENDING_UPDATES_PATH = LOGS_DIR / "pending_updates.json"

# roadmap_id prefix → default venture slug
_VENTURE_HINTS: dict[str, str] = {}   # populated lazily from ROADMAP.md

# Venture slug → CLAUDE.md path (relative to REPO_ROOT)
VENTURE_CLAUDE_MAP = {
    "marketing_audit": "src/ventures/marketing_audit/CLAUDE.md",
    "content_studio":  "src/ventures/content_studio/CLAUDE.md",
    "podcast_notes":   "src/ventures/podcast_notes/CLAUDE.md",
    "etsy":            "src/ventures/etsy/CLAUDE.md",
    "platform":        "src/aiplatform/CLAUDE.md",
}

# Jira project key for all active development work
JIRA_PROJECT = "AII"

# ROADMAP.md status → Jira transition name
JIRA_STATUS_MAP = {
    "idea":        "To Do",
    "planned":     "To Do",
    "in-progress": "In Progress",
    "done":        "Done",
    "on-hold":     "Pending",
    "blocked":     "Pending",
}

# Status emoji for display
STATUS_EMOJI = {
    "in-progress": "🔄",
    "done":        "✅",
    "on-hold":     "⏸",
    "blocked":     "🚫",
    "planned":     "📋",
    "idea":        "💡",
}

# Managed section marker in CLAUDE.md files
_SECTION_HEADER  = "## Pipeline Status"
_SECTION_MANAGED = "<!-- managed by update_task.py -->"


# ─── Public API ───────────────────────────────────────────────────────────────

def sync_task_status(
    roadmap_id: str,
    new_status: str,
    note: str,
    venture: str | None = None,
    push_to_github: bool | None = None,   # None = auto (True when done)
    api_key: str | None = None,           # unused — kept for call-site compatibility
) -> dict:
    """
    Synchronise a task status across Jira, ROADMAP.md, and venture CLAUDE.md.

    Returns:
        {
            "success":    bool,          # True if all critical steps passed
            "updated":    list[str],     # systems successfully updated
            "failed":     list[str],     # systems that failed
            "pending":    bool,          # True if failures were queued
            "commit_sha": str | None,    # git commit SHA if pushed
        }
    """
    venture = venture or _infer_venture(roadmap_id)
    push = push_to_github if push_to_github is not None else (new_status == "done")
    now  = datetime.now(timezone.utc)

    task_name = _get_task_name_from_roadmap(roadmap_id)
    updated:  list[str] = []
    failed:   list[str] = []
    results:  dict[str, str] = {}  # system → "ok" | "failed: <reason>"

    print(f"\n  Syncing {roadmap_id} → {new_status}")
    print(f"  Task:    {task_name}")
    print(f"  Venture: {venture}")
    print(f"  Note:    {note[:80]}{'...' if len(note) > 80 else ''}")

    # ── 1. Jira ─────────────────────────────────────────────────────────────────
    jira_result = _update_jira(roadmap_id, new_status, note)
    if jira_result.startswith("ok"):
        updated.append("jira")
        results["jira"] = "✓"
        print(f"    ✓ Jira")
    else:
        failed.append("jira")
        results["jira"] = f"✗ {jira_result}"
        print(f"    ✗ Jira: {jira_result}")

    # ── 2. ROADMAP.md ──────────────────────────────────────────────────────────
    rm_result = _update_roadmap(roadmap_id, new_status)
    if rm_result.startswith("ok"):
        updated.append("roadmap")
        results["roadmap"] = "✓"
        print(f"    ✓ ROADMAP.md")
    else:
        failed.append("roadmap")
        results["roadmap"] = f"✗ {rm_result}"
        print(f"    ✗ ROADMAP.md: {rm_result}")

    # ── 3. Venture CLAUDE.md ───────────────────────────────────────────────────
    cm_result = _update_claude_md(roadmap_id, task_name, venture, new_status, note, now)
    if cm_result.startswith("ok"):
        updated.append("claude_md")
        results["claude_md"] = "✓"
        print(f"    ✓ {venture}/CLAUDE.md")
    else:
        failed.append("claude_md")
        results["claude_md"] = f"✗ {cm_result}"
        print(f"    ✗ {venture}/CLAUDE.md: {cm_result}")

    # ── 4. Session log ─────────────────────────────────────────────────────────
    _append_session_log(roadmap_id, task_name, venture, new_status, note, results, now)
    print(f"    ✓ Session log")

    # ── 5. Queue pending failures ──────────────────────────────────────────────
    pending = False
    if failed:
        _queue_pending(roadmap_id, task_name, venture, new_status, note, failed, now)
        pending = True
        print(f"    ⚠  {len(failed)} failure(s) queued in logs/pending_updates.json")

    # ── 6. Git push on done ────────────────────────────────────────────────────
    commit_sha = None
    if push and new_status == "done":
        sha, err = _git_push(roadmap_id, task_name, note)
        if err:
            print(f"    ✗ Git push: {err}")
            failed.append("git")
            results["git"] = f"✗ {err}"
            _queue_pending(roadmap_id, task_name, venture, new_status, note, ["git"], now)
        else:
            commit_sha = sha
            updated.append("git")
            results["git"] = f"✓ {sha}"
            print(f"    ✓ Git push: {sha}")

    success = len(failed) == 0 or (failed == ["jira"] and len(updated) >= 2)
    print(f"\n  Result: {'OK' if success else 'PARTIAL'} — {len(updated)} updated, {len(failed)} failed")

    return {
        "success":    success,
        "updated":    updated,
        "failed":     failed,
        "pending":    pending,
        "commit_sha": commit_sha,
        "results":    results,
    }


# ─── Jira update ──────────────────────────────────────────────────────────────

def _update_jira(roadmap_id: str, new_status: str, note: str) -> str:
    try:
        issue = find_issue_by_label(JIRA_PROJECT, roadmap_id)
        if not issue:
            return f"failed: issue {roadmap_id} not found in Jira project {JIRA_PROJECT}"

        issue_key = issue["issue_key"]
        jira_status = JIRA_STATUS_MAP.get(new_status, "To Do")

        # Only transition if status would actually change
        if issue.get("status", "").lower() != jira_status.lower():
            t_result = transition_issue(issue_key, jira_status)
            if "error" in t_result:
                return f"failed: {t_result['error']}"

        emoji = STATUS_EMOJI.get(new_status, "")
        comment = f"{emoji} **{new_status.upper()}**\n\n{note}"
        c_result = add_comment(issue_key, comment)
        if "error" in c_result:
            return f"failed (comment): {c_result['error']}"

        return "ok"
    except Exception as exc:
        return f"failed: {exc}"


# ─── ROADMAP.md update ────────────────────────────────────────────────────────

_STATUS_RE = re.compile(
    r"(\|\s*" + r"({rid})" + r"\s*\|[^|]+\|[^|]+\|\s*)`([^`]+)`",
)

def _update_roadmap(roadmap_id: str, new_status: str) -> str:
    try:
        text = ROADMAP_PATH.read_text(encoding="utf-8")

        # Match the row for this roadmap_id — status is in the 4th column (backtick-wrapped)
        pattern = re.compile(
            r"(\|\s*" + re.escape(roadmap_id) + r"\s*\|[^|]+\|[^|]+\|\s*)`([^`]+)`"
        )
        m = pattern.search(text)
        if not m:
            return f"failed: {roadmap_id} not found in ROADMAP.md"

        old_status = m.group(2)
        if old_status == new_status:
            return "ok (no change)"

        new_text = text[:m.start(2)] + new_status + text[m.end(2):]
        ROADMAP_PATH.write_text(new_text, encoding="utf-8")
        return f"ok ({old_status} → {new_status})"
    except Exception as exc:
        return f"failed: {exc}"


# ─── Venture CLAUDE.md update ─────────────────────────────────────────────────

def _update_claude_md(
    roadmap_id: str,
    task_name: str,
    venture: str,
    new_status: str,
    note: str,
    now: datetime,
) -> str:
    try:
        rel_path = VENTURE_CLAUDE_MAP.get(venture)
        if not rel_path:
            return f"failed: no CLAUDE.md mapping for venture '{venture}'"

        claude_path = REPO_ROOT / rel_path
        if not claude_path.exists():
            return f"failed: {rel_path} not found"

        text = claude_path.read_text(encoding="utf-8")
        date_str = now.strftime("%Y-%m-%d")
        emoji = STATUS_EMOJI.get(new_status, "")
        short_note = note[:100] + ("..." if len(note) > 100 else "")

        new_row = (
            f"| {roadmap_id} | {task_name[:50]} | {emoji} {new_status} "
            f"| {short_note} | {date_str} |"
        )

        # Does managed section already exist?
        if _SECTION_MANAGED in text:
            # Find the table and update/insert the row for this roadmap_id
            section_start = text.index(_SECTION_MANAGED)
            before = text[:section_start]
            after_marker = text[section_start:]

            # Replace existing row or append
            row_pattern = re.compile(r"^\|\s*" + re.escape(roadmap_id) + r"\s*\|.*$", re.MULTILINE)
            if row_pattern.search(after_marker):
                new_after = row_pattern.sub(new_row, after_marker)
            else:
                # Append before closing blank line of section
                # Find the last table row line in the section
                lines = after_marker.splitlines(keepends=True)
                last_table_idx = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith("|"):
                        last_table_idx = i
                lines.insert(last_table_idx + 1, new_row + "\n")
                new_after = "".join(lines)

            new_text = before + new_after
        else:
            # Append managed section at end of file
            section = (
                f"\n\n{_SECTION_HEADER}\n"
                f"{_SECTION_MANAGED}\n\n"
                f"| Roadmap ID | Task | Status | Note | Updated |\n"
                f"|---|---|---|---|---|\n"
                f"{new_row}\n"
            )
            new_text = text.rstrip() + section

        claude_path.write_text(new_text, encoding="utf-8")
        return "ok"
    except Exception as exc:
        return f"failed: {exc}"


# ─── Session log ──────────────────────────────────────────────────────────────

def _append_session_log(
    roadmap_id: str,
    task_name: str,
    venture: str,
    new_status: str,
    note: str,
    results: dict,
    now: datetime,
) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / f"session_{now.strftime('%Y-%m-%d')}.md"
    time_str = now.strftime("%H:%M UTC")
    emoji = STATUS_EMOJI.get(new_status, "")

    sync_lines = "\n".join(
        f"- {system.replace('_', ' ').title()}: {status}"
        for system, status in results.items()
    )

    entry = (
        f"\n---\n\n"
        f"## [{roadmap_id}] {task_name}\n"
        f"**Time:** {time_str}  \n"
        f"**Status:** {emoji} `{new_status}`  \n"
        f"**Venture:** {venture}  \n"
        f"**Note:** {note}\n\n"
        f"**Sync results:**\n{sync_lines}\n"
    )

    if not log_path.exists():
        header = f"# Session Log — {now.strftime('%Y-%m-%d')}\n"
        log_path.write_text(header, encoding="utf-8")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


# ─── Pending updates queue ────────────────────────────────────────────────────

def _queue_pending(
    roadmap_id: str,
    task_name: str,
    venture: str,
    status: str,
    note: str,
    failed_systems: list[str],
    now: datetime,
) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    existing: list[dict] = []
    if PENDING_UPDATES_PATH.exists():
        try:
            existing = json.loads(PENDING_UPDATES_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    # Remove any existing entry for the same roadmap_id + system combination
    existing = [
        e for e in existing
        if not (e["roadmap_id"] == roadmap_id and set(e["failed"]) == set(failed_systems))
    ]

    existing.append({
        "roadmap_id":   roadmap_id,
        "task_name":    task_name,
        "venture":      venture,
        "status":       status,
        "note":         note,
        "failed":       failed_systems,
        "timestamp":    now.isoformat(),
        "requires_update": True,
    })
    PENDING_UPDATES_PATH.write_text(
        json.dumps(existing, indent=2, default=str), encoding="utf-8"
    )


def mark_pending_resolved(roadmap_id: str, system: str) -> None:
    """Remove a resolved entry from pending_updates.json."""
    if not PENDING_UPDATES_PATH.exists():
        return
    existing = json.loads(PENDING_UPDATES_PATH.read_text(encoding="utf-8"))
    updated = [
        e for e in existing
        if not (e["roadmap_id"] == roadmap_id and system in e.get("failed", []))
    ]
    PENDING_UPDATES_PATH.write_text(json.dumps(updated, indent=2), encoding="utf-8")


def get_pending_updates() -> list[dict]:
    """Return all items in the pending updates queue."""
    if not PENDING_UPDATES_PATH.exists():
        return []
    return json.loads(PENDING_UPDATES_PATH.read_text(encoding="utf-8"))


# ─── Git push ─────────────────────────────────────────────────────────────────

def _git_push(roadmap_id: str, task_name: str, note: str) -> tuple[str | None, str | None]:
    """
    Stage all changes, commit, and push to origin/main.
    Returns (commit_sha, error_message).
    """
    try:
        cwd = str(REPO_ROOT)
        short_note = note[:72] if note else task_name

        # Stage all tracked modifications (never -A — exclude untracked secrets)
        subprocess.run(["git", "add", "-u"], cwd=cwd, check=True, capture_output=True)
        # Also stage new files in src/ and scripts/ and logs/
        for path in ["src/", "scripts/", "logs/ROADMAP.md", "ROADMAP.md"]:
            subprocess.run(["git", "add", path], cwd=cwd, capture_output=True)

        # Check if there's anything to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=cwd, capture_output=True
        )
        if result.returncode == 0:
            return None, "nothing to commit (working tree clean)"

        msg = f"[{roadmap_id}] {task_name[:60]}\n\n{short_note}"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=cwd, check=True, capture_output=True
        )

        push = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=cwd, capture_output=True, text=True
        )
        if push.returncode != 0:
            return None, f"push failed: {push.stderr.strip()}"

        sha_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd, check=True, capture_output=True, text=True
        )
        return sha_result.stdout.strip(), None

    except subprocess.CalledProcessError as exc:
        return None, f"git error: {exc.stderr.decode().strip() if exc.stderr else str(exc)}"
    except Exception as exc:
        return None, str(exc)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_task_name_from_roadmap(roadmap_id: str) -> str:
    """Extract the task name from ROADMAP.md for a given roadmap_id."""
    try:
        text = ROADMAP_PATH.read_text(encoding="utf-8")
        pattern = re.compile(
            r"\|\s*" + re.escape(roadmap_id) + r"\s*\|\s*([^|]+?)\s*\|"
        )
        m = pattern.search(text)
        return m.group(1).strip() if m else roadmap_id
    except Exception:
        return roadmap_id


def _infer_venture(roadmap_id: str) -> str:
    """
    Infer venture from roadmap_id by reading the ROADMAP.md description.
    Falls back to 'platform'.
    """
    try:
        text = ROADMAP_PATH.read_text(encoding="utf-8")
        pattern = re.compile(
            r"\|\s*" + re.escape(roadmap_id) + r"\s*\|[^|]+\|[^|]+\|[^|]+\|\s*([^|]+?)\s*\|"
        )
        m = pattern.search(text)
        desc = m.group(1).lower() if m else ""

        if "etsy" in desc:
            return "etsy"
        if "marketing_audit" in desc or "marketing audit" in desc:
            return "marketing_audit"
        if any(k in desc for k in ("podcast", "content_studio", "episode", "show notes")):
            return "podcast_notes"
        if "content_channel" in desc:
            return "content_channels"
    except Exception:
        pass
    return "platform"
