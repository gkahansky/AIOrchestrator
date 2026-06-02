"""LinkedIn Company Page publisher.

Native path: LinkedIn Marketing API.
  - Text post:        POST /v2/ugcPosts with ShareMediaCategory NONE.
  - Single image:     register asset → upload binary → ugcPost with IMAGE category.
  - Carousel (>1 img): same register/upload per image, ugcPost with multiple media.

Requires a Page admin OAuth token with `w_organization_social` scope and the
Company Page URN (e.g. `urn:li:organization:12345`) in `account_id`.

Falls back to assisted-send (deep link to the Page composer) when no token is
configured for the (brand × channel) pair.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from aiplatform.skills.comms.publishers import _assisted
from aiplatform.skills.comms.publishers.base import PublishRequest, PublishResult


_API_BASE = "https://api.linkedin.com"
_API_VERSION = "202405"


def _build_deep_link(req: PublishRequest) -> str:
    return "https://www.linkedin.com/company/me/admin/page-posts/published/"


def publish(req: PublishRequest, config: dict | None = None) -> PublishResult:
    config  = config or {}
    token   = config.get("access_token") or os.environ.get("LINKEDIN_ACCESS_TOKEN")
    org_urn = config.get("account_id")

    if not token or not org_urn:
        return _assisted.run(req, "linkedin_page", _build_deep_link)

    image_paths = _local_image_paths(req.media_paths)

    # 1. Upload images (if any) and collect asset URNs.
    asset_urns: list[str] = []
    for path in image_paths:
        try:
            urn = _register_and_upload_image(token, org_urn, path)
            asset_urns.append(urn)
        except Exception as exc:
            return PublishResult(
                status="failed",
                provider="linkedin_api",
                error=f"image upload failed for {Path(path).name}: {exc}",
            )

    # 2. Compose the UGC post.
    payload: dict[str, Any] = {
        "author":          org_urn,
        "lifecycleState":  "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": _share_content(req, asset_urns),
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
        resp = requests.post(f"{_API_BASE}/v2/ugcPosts",
                             headers=headers, json=payload, timeout=30)
    except requests.RequestException as exc:
        return PublishResult(status="failed", provider="linkedin_api",
                             error=f"request error: {exc}")

    if resp.status_code >= 300:
        return PublishResult(
            status="failed", provider="linkedin_api",
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
        response={"assets": asset_urns, **body},
    )


# ── Assets flow ───────────────────────────────────────────────────────────────

def _register_and_upload_image(token: str, owner: str, image_path: str) -> str:
    """Two-step: registerUpload → PUT bytes to returned URL. Returns the asset URN."""
    register_resp = requests.post(
        f"{_API_BASE}/v2/assets?action=registerUpload",
        headers={
            "Authorization":              f"Bearer {token}",
            "Content-Type":               "application/json",
            "X-Restli-Protocol-Version":  "2.0.0",
        },
        json={
            "registerUploadRequest": {
                "owner":            owner,
                "recipes":          ["urn:li:digitalmediaRecipe:feedshare-image"],
                "serviceRelationships": [{
                    "identifier":             "urn:li:userGeneratedContent",
                    "relationshipType":       "OWNER",
                }],
                "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"],
            },
        },
        timeout=30,
    )
    register_resp.raise_for_status()
    rdata = register_resp.json().get("value", {})
    asset_urn = rdata.get("asset", "")
    upload_url = (
        rdata.get("uploadMechanism", {})
             .get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {})
             .get("uploadUrl", "")
    )
    if not (asset_urn and upload_url):
        raise RuntimeError("registerUpload response missing asset or upload url")

    with open(image_path, "rb") as fh:
        binary = fh.read()

    put_resp = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {token}"},
        data=binary,
        timeout=120,
    )
    put_resp.raise_for_status()
    return asset_urn


# ── Helpers ───────────────────────────────────────────────────────────────────

def _local_image_paths(media_paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in media_paths or []:
        if not p:
            continue
        lower = p.lower()
        if any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
            # Skip URLs — the upload flow needs bytes, not a URL.
            if not lower.startswith(("http://", "https://")):
                out.append(p)
    return out


def _share_content(req: PublishRequest, asset_urns: list[str]) -> dict[str, Any]:
    text = _compose_body(req)
    if not asset_urns:
        return {
            "shareCommentary":     {"text": text},
            "shareMediaCategory":  "NONE",
        }
    media = [{"status": "READY", "media": urn} for urn in asset_urns]
    return {
        "shareCommentary":    {"text": text},
        "shareMediaCategory": "IMAGE",
        "media":              media,
    }


def _compose_body(req: PublishRequest) -> str:
    body = (req.body or "").rstrip()
    tags = req.hashtags or []
    if tags:
        tag_str = " ".join(t if t.startswith("#") else f"#{t}" for t in tags)
        body = f"{body}\n\n{tag_str}"
    return body
