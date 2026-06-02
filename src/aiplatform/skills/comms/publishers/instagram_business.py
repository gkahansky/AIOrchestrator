"""Instagram Business publisher.

Native path: Meta Graph API two-step (or three-step for carousels).
  - Single image: POST /{ig_user_id}/media (with image_url) → /media_publish.
  - Carousel:     N x POST /media (is_carousel_item=true) → POST /media (CAROUSEL, children=...) → /media_publish.
  - Video/Reel:   POST /media with video_url + media_type=REELS → /media_publish.

IG requires every image / video to be a publicly reachable URL — there is no
binary upload endpoint. Callers must supply public URLs in `req.media_urls`,
OR supply local paths that the content engine has separately exposed at a
public URL (see /assets/{id}/file). If neither is available, falls back to
assisted-send.

`config.account_id` is the **IG user id**, not the FB page id (they differ).
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests

from aiplatform.skills.comms.publishers import _assisted
from aiplatform.skills.comms.publishers.base import PublishRequest, PublishResult


_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_MAX_STATUS_POLLS = 12   # 12 × 5s = 1 min max wait for media containers


def _build_deep_link(req: PublishRequest) -> str:
    return "https://business.facebook.com/creatorstudio/"


def publish(req: PublishRequest, config: dict | None = None) -> PublishResult:
    config     = config or {}
    token      = config.get("access_token") or os.environ.get("META_IG_ACCESS_TOKEN")
    ig_user_id = config.get("account_id")

    if not token or not ig_user_id:
        return _assisted.run(req, "instagram_business", _build_deep_link)

    image_urls = _image_urls(req.media_urls, req.media_paths)
    video_url  = _video_url(req.media_urls, req.media_paths)

    if not image_urls and not video_url:
        return _assisted.run(req, "instagram_business", _build_deep_link)

    caption = _compose_body(req)
    try:
        if video_url:
            container_id = _create_reel_container(ig_user_id, token, video_url, caption)
        elif len(image_urls) == 1:
            container_id = _create_image_container(ig_user_id, token, image_urls[0], caption, is_child=False)
        else:
            child_ids = [
                _create_image_container(ig_user_id, token, url, "", is_child=True)
                for url in image_urls
            ]
            container_id = _create_carousel_container(ig_user_id, token, child_ids, caption)
    except requests.RequestException as exc:
        return PublishResult(status="failed", provider="meta_graph",
                             error=f"container error: {exc}")
    except RuntimeError as exc:
        return PublishResult(status="failed", provider="meta_graph", error=str(exc))

    # Reels need to finish processing before publish; poll status_code briefly.
    if video_url:
        ready = _wait_container_ready(token, container_id)
        if not ready:
            return PublishResult(
                status="failed", provider="meta_graph",
                error=f"reel container {container_id} did not become FINISHED",
            )

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
    permalink = _permalink(token, post_id)
    return PublishResult(
        status="success",
        external_post_id=post_id,
        external_url=permalink or (f"https://www.instagram.com/p/{post_id}/" if post_id else ""),
        provider="meta_graph",
        response={"container_id": container_id, **data},
    )


# ── Container builders ────────────────────────────────────────────────────────

def _create_image_container(ig_user_id: str, token: str, image_url: str,
                            caption: str, *, is_child: bool) -> str:
    data: dict[str, Any] = {"image_url": image_url, "access_token": token}
    if is_child:
        data["is_carousel_item"] = "true"
    else:
        data["caption"] = caption
    resp = requests.post(f"{_GRAPH_BASE}/{ig_user_id}/media", data=data, timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"ig image container {resp.status_code}: {resp.text[:400]}")
    cid = (resp.json() or {}).get("id")
    if not cid:
        raise RuntimeError("ig image container missing id")
    return cid


def _create_carousel_container(ig_user_id: str, token: str,
                                child_ids: list[str], caption: str) -> str:
    resp = requests.post(
        f"{_GRAPH_BASE}/{ig_user_id}/media",
        data={
            "media_type":   "CAROUSEL",
            "children":     ",".join(child_ids),
            "caption":      caption,
            "access_token": token,
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"ig carousel container {resp.status_code}: {resp.text[:400]}")
    cid = (resp.json() or {}).get("id")
    if not cid:
        raise RuntimeError("ig carousel container missing id")
    return cid


def _create_reel_container(ig_user_id: str, token: str, video_url: str, caption: str) -> str:
    resp = requests.post(
        f"{_GRAPH_BASE}/{ig_user_id}/media",
        data={
            "media_type":   "REELS",
            "video_url":    video_url,
            "caption":      caption,
            "access_token": token,
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"ig reel container {resp.status_code}: {resp.text[:400]}")
    cid = (resp.json() or {}).get("id")
    if not cid:
        raise RuntimeError("ig reel container missing id")
    return cid


def _wait_container_ready(token: str, container_id: str) -> bool:
    for _ in range(_MAX_STATUS_POLLS):
        try:
            resp = requests.get(
                f"{_GRAPH_BASE}/{container_id}",
                params={"fields": "status_code", "access_token": token},
                timeout=15,
            )
        except requests.RequestException:
            time.sleep(5)
            continue
        if resp.status_code >= 300:
            return False
        status = (resp.json() or {}).get("status_code", "")
        if status == "FINISHED":
            return True
        if status in {"ERROR", "EXPIRED"}:
            return False
        time.sleep(5)
    return False


def _permalink(token: str, post_id: str) -> str:
    if not post_id:
        return ""
    try:
        resp = requests.get(
            f"{_GRAPH_BASE}/{post_id}",
            params={"fields": "permalink", "access_token": token},
            timeout=15,
        )
        if resp.status_code < 300:
            return (resp.json() or {}).get("permalink", "")
    except requests.RequestException:
        pass
    return ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _image_urls(urls: list[str], paths: list[str]) -> list[str]:
    out = [u for u in (urls or []) if u]
    for p in paths or []:
        if p and p.lower().startswith(("http://", "https://")):
            lower = p.lower()
            if any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
                out.append(p)
    return out


def _video_url(urls: list[str], paths: list[str]) -> str:
    for u in urls or []:
        if u and any(u.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm")):
            return u
    for p in paths or []:
        if p and p.lower().startswith(("http://", "https://")):
            if any(p.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm")):
                return p
    return ""


def _compose_body(req: PublishRequest) -> str:
    body = (req.body or "").rstrip()
    tags = req.hashtags or []
    if tags:
        body = f"{body}\n\n" + " ".join(t if t.startswith("#") else f"#{t}" for t in tags)
    return body[:2200]
