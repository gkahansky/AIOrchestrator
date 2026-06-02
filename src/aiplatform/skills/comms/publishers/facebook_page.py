"""Facebook Page publisher.

Native path: Meta Graph API.
  - Text post:     POST /{page_id}/feed.
  - Single image:  POST /{page_id}/photos with `source` multipart (or `url`).
  - Multi-image:   N x POST /photos with published=false → POST /feed with attached_media.

Requires a Page access token in `config.access_token` and the page ID in
`config.account_id`. Falls back to assisted-send.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from aiplatform.skills.comms.publishers import _assisted
from aiplatform.skills.comms.publishers.base import PublishRequest, PublishResult


_GRAPH_BASE = "https://graph.facebook.com/v19.0"


def _build_deep_link(req: PublishRequest) -> str:
    return "https://www.facebook.com/business/help/composer"


def publish(req: PublishRequest, config: dict | None = None) -> PublishResult:
    config  = config or {}
    token   = config.get("access_token") or os.environ.get("META_PAGE_ACCESS_TOKEN")
    page_id = config.get("account_id")

    if not token or not page_id:
        return _assisted.run(req, "facebook_page", _build_deep_link)

    body = _compose_body(req)
    image_paths = _image_inputs(req.media_paths, req.media_urls)

    try:
        if not image_paths:
            return _post_text(page_id, token, body)
        if len(image_paths) == 1:
            return _post_single_photo(page_id, token, body, image_paths[0])
        return _post_carousel(page_id, token, body, image_paths)
    except requests.RequestException as exc:
        return PublishResult(status="failed", provider="meta_graph",
                             error=f"request error: {exc}")


# ── Modes ─────────────────────────────────────────────────────────────────────

def _post_text(page_id: str, token: str, body: str) -> PublishResult:
    resp = requests.post(
        f"{_GRAPH_BASE}/{page_id}/feed",
        data={"message": body, "access_token": token},
        timeout=30,
    )
    return _result(resp, base_url="https://www.facebook.com")


def _post_single_photo(page_id: str, token: str, body: str, image: dict) -> PublishResult:
    if image["kind"] == "url":
        data = {"url": image["value"], "caption": body, "access_token": token}
        resp = requests.post(f"{_GRAPH_BASE}/{page_id}/photos", data=data, timeout=60)
    else:  # local file
        with open(image["value"], "rb") as fh:
            resp = requests.post(
                f"{_GRAPH_BASE}/{page_id}/photos",
                data={"caption": body, "access_token": token},
                files={"source": (Path(image["value"]).name, fh.read())},
                timeout=120,
            )
    return _result(resp, base_url="https://www.facebook.com")


def _post_carousel(page_id: str, token: str, body: str, images: list[dict]) -> PublishResult:
    media_ids: list[str] = []
    for image in images:
        if image["kind"] == "url":
            data = {"url": image["value"], "published": "false", "access_token": token}
            up = requests.post(f"{_GRAPH_BASE}/{page_id}/photos", data=data, timeout=60)
        else:
            with open(image["value"], "rb") as fh:
                up = requests.post(
                    f"{_GRAPH_BASE}/{page_id}/photos",
                    data={"published": "false", "access_token": token},
                    files={"source": (Path(image["value"]).name, fh.read())},
                    timeout=120,
                )
        if up.status_code >= 300:
            return PublishResult(
                status="failed", provider="meta_graph",
                error=f"photo upload {up.status_code}: {up.text[:400]}",
            )
        photo_id = (up.json() or {}).get("id")
        if not photo_id:
            return PublishResult(status="failed", provider="meta_graph",
                                 error="photo upload returned no id")
        media_ids.append(photo_id)

    attached = [{"media_fbid": pid} for pid in media_ids]
    feed_resp = requests.post(
        f"{_GRAPH_BASE}/{page_id}/feed",
        data={"message": body, "access_token": token,
              "attached_media": str(attached).replace("'", '"')},
        timeout=30,
    )
    return _result(feed_resp, base_url="https://www.facebook.com",
                   extra={"photo_ids": media_ids})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _image_inputs(local_paths: list[str], urls: list[str]) -> list[dict]:
    out: list[dict] = []
    for p in local_paths or []:
        if not p:
            continue
        lower = p.lower()
        if any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
            kind = "url" if lower.startswith(("http://", "https://")) else "file"
            out.append({"kind": kind, "value": p})
    for u in urls or []:
        if u:
            out.append({"kind": "url", "value": u})
    return out


def _result(resp: requests.Response, base_url: str, extra: dict | None = None) -> PublishResult:
    if resp.status_code >= 300:
        return PublishResult(
            status="failed", provider="meta_graph",
            error=f"facebook {resp.status_code}: {resp.text[:500]}",
            response={"http_status": resp.status_code},
        )
    data = resp.json() if resp.content else {}
    post_id = data.get("post_id") or data.get("id", "")
    return PublishResult(
        status="success",
        external_post_id=post_id,
        external_url=f"{base_url}/{post_id}" if post_id else "",
        provider="meta_graph",
        response={**(extra or {}), **data},
    )


def _compose_body(req: PublishRequest) -> str:
    body = (req.body or "").rstrip()
    tags = req.hashtags or []
    if tags:
        body = f"{body}\n\n" + " ".join(t if t.startswith("#") else f"#{t}" for t in tags)
    return body
