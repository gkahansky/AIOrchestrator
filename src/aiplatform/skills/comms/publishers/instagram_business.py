"""Instagram Business publisher.

Native path: Meta Graph API two-step container flow:
  1. `POST /{ig_user_id}/media` with image_url / video_url + caption → container id
  2. `POST /{ig_user_id}/media_publish` with creation_id → published post

The IG Business account must be linked to a Facebook Page; the same Meta
OAuth token covers both. `social_accounts.account_id` holds the IG user ID
(NOT the Page ID).

Assisted fallback: deep link to Creator Studio.
"""
from __future__ import annotations

import os
from typing import Any

import requests

from aiplatform.skills.comms.publishers import _assisted
from aiplatform.skills.comms.publishers.base import PublishRequest, PublishResult


_GRAPH_BASE = "https://graph.facebook.com/v19.0"


def _build_deep_link(req: PublishRequest) -> str:
    return "https://business.facebook.com/creatorstudio/"


def publish(req: PublishRequest, config: dict | None = None) -> PublishResult:
    config     = config or {}
    token      = config.get("access_token") or os.environ.get("META_IG_ACCESS_TOKEN")
    ig_user_id = config.get("account_id")

    if not token or not ig_user_id:
        return _assisted.run(req, "instagram_business", _build_deep_link)

    # IG requires a publicly-reachable image_url / video_url — we don't yet
    # have a hosted-media step here, so for text+image we need a URL on
    # media_urls. Falls back to assisted-send when no URL is available.
    media_url = (req.media_urls or [None])[0]
    if not media_url:
        return _assisted.run(req, "instagram_business", _build_deep_link)

    caption = _compose_body(req)

    try:
        container = requests.post(
            f"{_GRAPH_BASE}/{ig_user_id}/media",
            data={
                "image_url":    media_url,
                "caption":      caption,
                "access_token": token,
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        return PublishResult(status="failed", provider="meta_graph",
                             error=f"container error: {exc}")

    if container.status_code >= 300:
        return PublishResult(
            status="failed", provider="meta_graph",
            error=f"ig container {container.status_code}: {container.text[:500]}",
        )
    container_id = (container.json() or {}).get("id")
    if not container_id:
        return PublishResult(status="failed", provider="meta_graph",
                             error="container response missing id")

    try:
        publish_resp = requests.post(
            f"{_GRAPH_BASE}/{ig_user_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=30,
        )
    except requests.RequestException as exc:
        return PublishResult(status="failed", provider="meta_graph",
                             error=f"publish error: {exc}")

    if publish_resp.status_code >= 300:
        return PublishResult(
            status="failed", provider="meta_graph",
            error=f"ig publish {publish_resp.status_code}: {publish_resp.text[:500]}",
        )

    data = publish_resp.json() if publish_resp.content else {}
    post_id = data.get("id", "")
    return PublishResult(
        status="success",
        external_post_id=post_id,
        external_url=f"https://www.instagram.com/p/{post_id}/" if post_id else "",
        provider="meta_graph",
        response={"container_id": container_id, **data},
    )


def _compose_body(req: PublishRequest) -> str:
    body = (req.body or "").rstrip()
    tags = req.hashtags or []
    if tags:
        body = f"{body}\n\n" + " ".join(t if t.startswith("#") else f"#{t}" for t in tags)
    return body[:2200]  # IG hard caption limit
