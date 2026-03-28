"""
Skill: update_jira_board
Interact with the Jira project board — create, update, and read issues.

This skill knows nothing about any venture. All venture-specific logic
(which project to use, what roadmap_id to assign) lives in the caller.

Issue hierarchy:
    Feature  — top-level, one per venture or system capability
    Story    — deliverable piece of functionality under a Feature
    Task     — internal breakdown under a Story
    Bug      — problem in the finished product

Capabilities:
    project-board-write  — create_issue, update_issue_status, add_comment, link_issues
    project-board-read   — get_issue, search_issues, get_project_meta

Jira Cloud REST API v3:
    Base:  https://{JIRA_DOMAIN}/rest/api/3
    Auth:  HTTP Basic — email:api_token (base64)
    Rate:  ~1 req/s on free tier (be conservative)
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)

_REQUEST_COUNT = 0


# ─── Config ───────────────────────────────────────────────────────────────────

def _base_url() -> str:
    domain = os.environ.get("JIRA_DOMAIN", "").rstrip("/")
    if not domain:
        raise ValueError("JIRA_DOMAIN not set in environment.")
    return f"{domain}/rest/api/3"


def _auth_header() -> dict:
    email   = os.environ.get("JIRA_EMAIL", "")
    api_key = os.environ.get("JIRA_API_KEY", "")
    if not email or not api_key:
        raise ValueError("JIRA_EMAIL and JIRA_API_KEY must be set in environment.")
    token = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def create_issue(
    project_key: str,
    summary: str,
    issue_type: str,
    description: str | None = None,
    parent_key: str | None = None,
    labels: list[str] | None = None,
    priority: str | None = None,
) -> dict:
    """
    Capability: project-board-write
    Create a new Jira issue.

    Args:
        project_key:  Jira project key (e.g. "AI", "PR")
        summary:      Issue title
        issue_type:   "Feature", "Story", "Task", "Bug"
        description:  Plain text description (converted to ADF internally)
        parent_key:   Parent issue key for Stories under Features, Tasks under Stories
        labels:       List of label strings (e.g. ["roadmap_id-H-08", "venture-platform"])
        priority:     "Highest", "High", "Medium", "Low", "Lowest"

    Returns:
        {issue_key, issue_id, url} on success, {"error": ...} on failure.
    """
    fields: dict = {
        "project":   {"key": project_key},
        "summary":   summary,
        "issuetype": {"name": issue_type},
    }
    if description:
        fields["description"] = _to_adf(description)
    if parent_key:
        fields["parent"] = {"key": parent_key}
    if labels:
        fields["labels"] = labels
    if priority:
        fields["priority"] = {"name": priority}

    resp = _post("/issue", {"fields": fields})
    if "errorMessages" in resp or "errors" in resp:
        err = resp.get("errorMessages", []) or list(resp.get("errors", {}).values())
        return {"error": "; ".join(str(e) for e in err), "raw": resp}
    return {
        "issue_key": resp.get("key"),
        "issue_id":  resp.get("id"),
        "url":       f"{os.environ.get('JIRA_DOMAIN', '').rstrip('/')}/browse/{resp.get('key')}",
    }


def transition_issue(
    issue_key: str,
    target_status: str,
) -> dict:
    """
    Capability: project-board-write
    Move an issue to the given status by name (e.g. "In Progress", "Done").
    Discovers available transitions at runtime.

    Returns {issue_key, status} on success, {"error": ...} on failure.
    """
    transitions = _get(f"/issue/{issue_key}/transitions")
    available   = transitions.get("transitions", [])
    match       = next(
        (t for t in available if t["name"].lower() == target_status.lower()),
        None,
    )
    if not match:
        names = [t["name"] for t in available]
        return {"error": f"Transition '{target_status}' not found. Available: {names}"}

    resp = _post(f"/issue/{issue_key}/transitions", {"transition": {"id": match["id"]}})
    # Successful transition returns 204 (empty body)
    if isinstance(resp, dict) and ("errorMessages" in resp or "errors" in resp):
        err = resp.get("errorMessages", []) or list(resp.get("errors", {}).values())
        return {"error": "; ".join(str(e) for e in err)}
    return {"issue_key": issue_key, "status": target_status}


def add_comment(
    issue_key: str,
    comment: str,
) -> dict:
    """
    Capability: project-board-write
    Post a plain-text comment on an issue.
    Returns {comment_id} on success, {"error": ...} on failure.
    """
    resp = _post(f"/issue/{issue_key}/comment", {"body": _to_adf(comment)})
    if "errorMessages" in resp or "errors" in resp:
        err = resp.get("errorMessages", []) or list(resp.get("errors", {}).values())
        return {"error": "; ".join(str(e) for e in err)}
    return {"comment_id": resp.get("id")}


def get_issue(issue_key: str) -> dict:
    """
    Capability: project-board-read
    Return full issue detail by key.
    Returns normalised {issue_key, summary, status, issue_type, labels, url}.
    """
    resp = _get(f"/issue/{issue_key}")
    if "errorMessages" in resp or ("errors" in resp and resp.get("errors")):
        return {"error": resp.get("errorMessages") or resp.get("errors")}
    return _normalise_issue(resp)


def search_issues(jql: str, max_results: int = 100) -> list[dict]:
    """
    Capability: project-board-read
    Search issues with a JQL query.
    Returns list of normalised issue dicts.
    """
    resp = _post("/search/jql", {"jql": jql, "maxResults": max_results, "fields": [
        "summary", "status", "issuetype", "labels", "parent", "priority",
    ]})
    if "errorMessages" in resp or "errors" in resp:
        log.error("Jira search failed: %s", resp)
        return []
    return [_normalise_issue(i) for i in resp.get("issues", [])]


def get_project_meta(project_key: str) -> dict:
    """
    Capability: project-board-read
    Return project metadata: available issue types and their IDs.
    Returns {project_key, issue_types: [{id, name}]}.
    """
    resp = _get(f"/project/{project_key}")
    if "errorMessages" in resp or ("errors" in resp and resp.get("errors")):
        return {"error": resp.get("errorMessages") or resp.get("errors")}
    issue_types = [
        {"id": it.get("id"), "name": it.get("name")}
        for it in resp.get("issueTypes", [])
    ]
    return {
        "project_key":  resp.get("key"),
        "project_name": resp.get("name"),
        "project_id":   resp.get("id"),
        "issue_types":  issue_types,
    }


def list_projects() -> list[dict]:
    """
    Capability: project-board-read
    Return all accessible projects.
    Returns [{project_key, project_name, project_id}].
    """
    resp = _get("/project")
    if isinstance(resp, list):
        return [{"project_key": p.get("key"), "project_name": p.get("name"), "project_id": p.get("id")} for p in resp]
    return []


def find_issue_by_label(project_key: str, roadmap_id: str) -> dict | None:
    """
    Find an issue whose labels contain 'roadmap_id-{roadmap_id}'.
    Searches the given project first; if not found, falls back to a global
    label-only search (handles issues created before a project key rename).
    Returns normalised issue dict or None.
    """
    label = f"roadmap_id-{roadmap_id}"
    # Primary: scoped to active project key
    issues = search_issues(f'project = "{project_key}" AND labels = "{label}"', max_results=1)
    if issues:
        return issues[0]
    # Fallback: global search (handles pre-rename SCRUM-* issues)
    issues = search_issues(f'labels = "{label}"', max_results=1)
    return issues[0] if issues else None


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None, retry: int = 1) -> dict | list:
    global _REQUEST_COUNT
    _REQUEST_COUNT += 1
    try:
        r = requests.get(
            _base_url() + path,
            params=params or {},
            headers=_auth_header(),
            timeout=15,
        )
        time.sleep(0.3)  # conservative rate limiting
        if r.status_code == 204:
            return {}
        return r.json()
    except Exception as exc:
        if retry > 0:
            time.sleep(5)
            return _get(path, params, retry - 1)
        log.error("Jira GET %s failed: %s", path, exc)
        return {"error": str(exc)}


def _post(path: str, payload: dict, retry: int = 1) -> dict:
    global _REQUEST_COUNT
    _REQUEST_COUNT += 1
    try:
        r = requests.post(
            _base_url() + path,
            json=payload,
            headers=_auth_header(),
            timeout=15,
        )
        time.sleep(0.3)
        if r.status_code == 204:
            return {}
        return r.json()
    except Exception as exc:
        if retry > 0:
            time.sleep(5)
            return _post(path, payload, retry - 1)
        log.error("Jira POST %s failed: %s", path, exc)
        return {"error": str(exc)}


def _put(path: str, payload: dict, retry: int = 1) -> dict:
    global _REQUEST_COUNT
    _REQUEST_COUNT += 1
    try:
        r = requests.put(
            _base_url() + path,
            json=payload,
            headers=_auth_header(),
            timeout=15,
        )
        time.sleep(0.3)
        if r.status_code in (200, 204):
            return {}
        return r.json()
    except Exception as exc:
        if retry > 0:
            time.sleep(5)
            return _put(path, payload, retry - 1)
        log.error("Jira PUT %s failed: %s", path, exc)
        return {"error": str(exc)}


def _to_adf(text: str) -> dict:
    """Convert plain text to Atlassian Document Format (ADF) paragraph nodes."""
    paragraphs = []
    for line in text.split("\n"):
        if line.strip():
            paragraphs.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": line}],
            })
    return {
        "type":    "doc",
        "version": 1,
        "content": paragraphs or [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _normalise_issue(raw: dict) -> dict:
    """Flatten a raw Jira issue response."""
    fields  = raw.get("fields", {})
    status  = (fields.get("status") or {}).get("name", "")
    itype   = (fields.get("issuetype") or {}).get("name", "")
    parent  = (fields.get("parent") or {}).get("key")
    prio    = (fields.get("priority") or {}).get("name")
    key     = raw.get("key", "")
    domain  = os.environ.get("JIRA_DOMAIN", "").rstrip("/")
    return {
        "issue_key":   key,
        "issue_id":    raw.get("id"),
        "summary":     fields.get("summary", ""),
        "status":      status,
        "issue_type":  itype,
        "labels":      fields.get("labels", []),
        "parent_key":  parent,
        "priority":    prio,
        "url":         f"{domain}/browse/{key}",
    }
