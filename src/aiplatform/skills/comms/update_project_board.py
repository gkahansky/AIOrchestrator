"""
Skill: update_project_board
DEPRECATED — superseded by comms/update_jira_board.py.

This module contained the legacy project board integration.
All active code now routes through update_jira_board.py (Jira Cloud REST API v3).

Kept for historical reference only. Do not use in new pipelines.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Optional

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.clickup.com/api/v2"  # legacy — no longer active
RATE_WARN_REMAINING = 20
_REQUEST_COUNT = 0


# ─── Public API ───────────────────────────────────────────────────────────────

def create_task(
    list_id: str,
    name: str,
    status: str,
    description: str | None = None,
    custom_fields: dict | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Capability: project-board-write
    Create a new task in the specified list.

    custom_fields: {field_name: value} — field IDs are resolved automatically.
    Returns {task_id, url, status} on success, {"error": ...} on failure.
    """
    api_key = _resolve_key(api_key)
    payload: dict = {"name": name, "status": status}
    if description:
        payload["description"] = description

    if custom_fields:
        resolved = _resolve_custom_fields(list_id, custom_fields, api_key)
        if resolved:
            payload["custom_fields"] = resolved

    resp = _post(f"/list/{list_id}/task", payload, api_key)
    if "err" in resp or "error" in resp:
        return {"error": resp.get("err") or resp.get("error"), "raw": resp}
    return {
        "task_id": resp.get("id"),
        "url":     resp.get("url"),
        "status":  resp.get("status", {}).get("status") if isinstance(resp.get("status"), dict) else resp.get("status"),
    }


def update_task_status(
    task_id: str,
    status: str,
    api_key: str | None = None,
    comment: str | None = None,
) -> dict:
    """
    Capability: project-board-write
    Update a task's status. Optionally post a comment on the change.
    Returns {task_id, status, updated_at}.
    """
    api_key = _resolve_key(api_key)
    resp = _put(f"/task/{task_id}", {"status": status}, api_key)
    if "err" in resp or "error" in resp:
        return {"error": resp.get("err") or resp.get("error"), "raw": resp}

    if comment:
        add_task_comment(task_id, comment, api_key)

    return {
        "task_id":    task_id,
        "status":     status,
        "updated_at": resp.get("date_updated"),
    }


def add_task_comment(
    task_id: str,
    comment: str,
    api_key: str | None = None,
) -> dict:
    """
    Capability: project-board-write
    Post a comment on a task.
    Returns {comment_id} on success, {"error": ...} on failure.
    """
    api_key = _resolve_key(api_key)
    resp = _post(f"/task/{task_id}/comment", {"comment_text": comment}, api_key)
    if "err" in resp or "error" in resp:
        return {"error": resp.get("err") or resp.get("error"), "raw": resp}
    return {"comment_id": resp.get("id")}


def get_tasks_by_status(
    list_id: str,
    status: str,
    api_key: str | None = None,
) -> list[dict]:
    """
    Capability: project-board-read
    Return all tasks in a list filtered by status.
    Returns [{task_id, name, status, custom_fields, url}].
    """
    api_key = _resolve_key(api_key)
    resp = _get(f"/list/{list_id}/task", {"statuses[]": status}, api_key)
    return [_normalise_task(t) for t in resp.get("tasks", [])]


def get_task(
    task_id: str,
    api_key: str | None = None,
) -> dict:
    """
    Capability: project-board-read
    Return full task detail by ID.
    Returns {task_id, name, status, custom_fields, url}.
    """
    api_key = _resolve_key(api_key)
    resp = _get(f"/task/{task_id}", {}, api_key)
    if "err" in resp or "error" in resp:
        return {"error": resp.get("err") or resp.get("error")}
    return _normalise_task(resp)


def get_all_tasks(
    list_id: str,
    api_key: str | None = None,
) -> list[dict]:
    """
    Capability: project-board-read
    Return all tasks in a list regardless of status.
    Handles pagination automatically.
    Returns [{task_id, name, status, custom_fields, url}].
    """
    api_key = _resolve_key(api_key)
    tasks = []
    page = 0
    while True:
        resp = _get(f"/list/{list_id}/task", {"page": page, "include_closed": "true"}, api_key)
        batch = resp.get("tasks", [])
        tasks.extend(batch)
        if resp.get("last_page") or len(batch) == 0:
            break
        page += 1
    return [_normalise_task(t) for t in tasks]


def get_list_custom_fields(
    list_id: str,
    api_key: str | None = None,
) -> list[dict]:
    """
    Return all custom field definitions for a list.
    [{field_id, name, type, options}]
    """
    api_key = _resolve_key(api_key)
    resp = _get(f"/list/{list_id}/field", {}, api_key)
    fields = []
    for f in resp.get("fields", []):
        options = [o.get("name") for o in (f.get("type_config") or {}).get("options", [])]
        fields.append({
            "field_id": f.get("id"),
            "name":     f.get("name"),
            "type":     f.get("type"),
            "options":  options,
        })
    return fields


def find_task_by_roadmap_id(
    list_id: str,
    roadmap_id: str,
    api_key: str | None = None,
) -> dict | None:
    """
    Search all tasks in a list for one whose `roadmap_id` custom field matches.
    Returns the normalised task dict, or None if not found.
    """
    api_key = _resolve_key(api_key)
    all_tasks = get_all_tasks(list_id, api_key)
    for task in all_tasks:
        cf = task.get("custom_fields", {})
        if cf.get("roadmap_id") == roadmap_id:
            return task
    return None


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _resolve_key(api_key: str | None) -> str:
    key = api_key or ""
    if not key:
        raise ValueError("No api_key provided. This module is deprecated — use update_jira_board.py instead.")
    return key


def _headers(api_key: str) -> dict:
    return {"Authorization": api_key, "Content-Type": "application/json"}


def _get(path: str, params: dict, api_key: str, retry: int = 1) -> dict:
    global _REQUEST_COUNT
    _REQUEST_COUNT += 1
    try:
        r = requests.get(BASE_URL + path, params=params, headers=_headers(api_key), timeout=15)
        _check_rate(r)
        return r.json()
    except Exception as exc:
        if retry > 0:
            time.sleep(5)
            return _get(path, params, api_key, retry - 1)
        log.error("GET %s failed: %s", path, exc)
        return {"error": str(exc)}


def _post(path: str, payload: dict, api_key: str, retry: int = 1) -> dict:
    global _REQUEST_COUNT
    _REQUEST_COUNT += 1
    try:
        r = requests.post(BASE_URL + path, json=payload, headers=_headers(api_key), timeout=15)
        _check_rate(r)
        return r.json()
    except Exception as exc:
        if retry > 0:
            time.sleep(5)
            return _post(path, payload, api_key, retry - 1)
        log.error("POST %s failed: %s", path, exc)
        return {"error": str(exc)}


def _put(path: str, payload: dict, api_key: str, retry: int = 1) -> dict:
    global _REQUEST_COUNT
    _REQUEST_COUNT += 1
    try:
        r = requests.put(BASE_URL + path, json=payload, headers=_headers(api_key), timeout=15)
        _check_rate(r)
        return r.json()
    except Exception as exc:
        if retry > 0:
            time.sleep(5)
            return _put(path, payload, api_key, retry - 1)
        log.error("PUT %s failed: %s", path, exc)
        return {"error": str(exc)}


def _check_rate(response: requests.Response) -> None:
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining and int(remaining) <= RATE_WARN_REMAINING:
        log.warning("Rate limit: %s requests remaining in window", remaining)


def _normalise_task(raw: dict) -> dict:
    """Flatten a raw task response to a clean dict."""
    status = raw.get("status", {})
    status_name = status.get("status") if isinstance(status, dict) else str(status)
    cf_raw = raw.get("custom_fields", [])
    custom_fields = {}
    for field in cf_raw:
        name = field.get("name", "")
        value = field.get("value")
        # Dropdown fields: value is the option ordinal; look up name from type_config
        if field.get("type") == "drop_down" and value is not None:
            options = (field.get("type_config") or {}).get("options", [])
            matched = next((o.get("name") for o in options if str(o.get("orderindex")) == str(value)), None)
            value = matched or value
        custom_fields[name] = value
    return {
        "task_id":       raw.get("id"),
        "name":          raw.get("name"),
        "status":        status_name,
        "custom_fields": custom_fields,
        "url":           raw.get("url"),
        "description":   raw.get("description", ""),
    }


def _resolve_custom_fields(list_id: str, fields: dict, api_key: str) -> list[dict]:
    """
    Convert {field_name: value} to the custom_fields array format.
    Discovers field IDs from the list definition.
    Returns [] if no fields can be resolved.
    """
    definitions = get_list_custom_fields(list_id, api_key)
    id_map = {f["name"]: f for f in definitions}
    result = []
    for name, value in fields.items():
        defn = id_map.get(name)
        if not defn:
            log.warning("Custom field '%s' not found in list %s — skipping", name, list_id)
            continue
        field_id = defn["field_id"]
        field_type = defn.get("type")
        if field_type == "drop_down":
            # value must be the option index (int), resolved from name
            options = (defn.get("options") or [])
            idx = options.index(value) if value in options else None
            if idx is None:
                log.warning("Dropdown option '%s' not found for field '%s'", value, name)
                continue
            result.append({"id": field_id, "value": idx})
        else:
            result.append({"id": field_id, "value": value})
    return result
