"""LinkedIn Company Page publisher.

Native path: LinkedIn Marketing API — `ugcPosts` for text/article posts,
`assets` two-step upload for images/videos. Requires a Page admin OAuth token
with `w_organization_social` scope, persisted in `social_accounts.access_token`
plus the page's URN in `social_accounts.account_id` (e.g. `urn:li:organization:12345`).

Assisted fallback: returns a deep link to the Company Page's post composer.
"""
from __future__ import annotations

import os
from typing import Any

import requests

from aiplatform.skills.comms.publishers import _assisted
from aiplatform.skills.comms.publishers.base import PublishRequest, PublishResult


_API_BASE = "https://api.linkedin.com"
_API_VERSION = "202405"


def _build_deep_link(req: PublishRequest) -> str:
    return "https://www.linkedin.com/company/me/admin/page-posts/published/"


def publish(req: PublishRequest, config: dict | None = None) -> PublishResult:
    config = config or {}
    token  = config.get("access_token") or os.environ.get("LINKEDIN_ACCESS_TOKEN")
    org_urn = config.get("account_id")  # must be like "urn:li:organization:12345"

    if not token or not org_urn:
        return _assisted.run(req, "linkedin_page", _build_deep_link)

    # Text-only post via UGC posts API. Images/video go through the `assets`
    # upload flow first — wired up in a follow-up once an OAuth token is live.
    payload: dict[str, Any] = {
        "author":     org_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": _compose_body(req)},
                "shareMediaCategory": "NONE",
            },
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    headers = {
        "Authorization":              f"Bearer {token}",
        "Content-Type":               "application/json",
        "X-Restli-Protocol-Version":  "2.0.0",
        "LinkedIn-Version":           _API_VERSION,
    }

    try:
        resp = requests.post(
            f"{_API_BASE}/v2/ugcPosts",
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        return PublishResult(
            status="failed",
            provider="linkedin_api",
            error=f"request error: {exc}",
        )

    if resp.status_code >= 300:
        return PublishResult(
            status="failed",
            provider="linkedin_api",
            error=f"linkedin {resp.status_code}: {resp.text[:500]}",
            response={"http_status": resp.status_code},
        )

    body = resp.json() if resp.content else {}
    post_id = body.get("id") or resp.headers.get("x-restli-id", "")
    return PublishResult(
        status="success",
        external_post_id=post_id,
        external_url=f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else "",
        provider="linkedin_api",
        response=body,
    )


def _compose_body(req: PublishRequest) -> str:
    body = (req.body or "").rstrip()
    tags = (req.hashtags or [])
    if tags:
        # LinkedIn hashtags: hash-prefixed alphanumeric, no spaces.
        tag_str = " ".join(t if t.startswith("#") else f"#{t}" for t in tags)
        body = f"{body}\n\n{tag_str}"
    return body
