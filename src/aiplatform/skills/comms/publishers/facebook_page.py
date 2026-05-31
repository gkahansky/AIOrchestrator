"""Facebook Page publisher.

Native path: Meta Graph API — `POST /{page_id}/feed` for text/link posts,
`/photos` for images, `/videos` and `/video_reels` for video. Requires a Page
access token in `social_accounts.access_token` and the page ID in
`social_accounts.account_id`.

Assisted fallback: deep link to the Page's composer.
"""
from __future__ import annotations

import os
from typing import Any

import requests

from aiplatform.skills.comms.publishers import _assisted
from aiplatform.skills.comms.publishers.base import PublishRequest, PublishResult


_GRAPH_BASE = "https://graph.facebook.com/v19.0"


def _build_deep_link(req: PublishRequest) -> str:
    return "https://www.facebook.com/business/help/composer"


def publish(req: PublishRequest, config: dict | None = None) -> PublishResult:
    config   = config or {}
    token    = config.get("access_token") or os.environ.get("META_PAGE_ACCESS_TOKEN")
    page_id  = config.get("account_id")

    if not token or not page_id:
        return _assisted.run(req, "facebook_page", _build_deep_link)

    body = _compose_body(req)
    # Text-only feed post first; image/video paths land in a follow-up.
    payload: dict[str, Any] = {"message": body, "access_token": token}

    try:
        resp = requests.post(
            f"{_GRAPH_BASE}/{page_id}/feed",
            data=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        return PublishResult(
            status="failed",
            provider="meta_graph",
            error=f"request error: {exc}",
        )

    if resp.status_code >= 300:
        return PublishResult(
            status="failed",
            provider="meta_graph",
            error=f"facebook {resp.status_code}: {resp.text[:500]}",
            response={"http_status": resp.status_code},
        )

    data = resp.json() if resp.content else {}
    post_id = data.get("id", "")
    return PublishResult(
        status="success",
        external_post_id=post_id,
        external_url=f"https://www.facebook.com/{post_id}" if post_id else "",
        provider="meta_graph",
        response=data,
    )


def _compose_body(req: PublishRequest) -> str:
    body = (req.body or "").rstrip()
    tags = req.hashtags or []
    if tags:
        body = f"{body}\n\n" + " ".join(t if t.startswith("#") else f"#{t}" for t in tags)
    return body
