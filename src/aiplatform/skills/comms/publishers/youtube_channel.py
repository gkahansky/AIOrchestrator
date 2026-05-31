"""YouTube channel publisher.

Native path: YouTube Data API v3 — `videos.insert` with resumable upload.
For text-only "Community" posts the API support is limited; this handler
focuses on video upload (Shorts and long-form). A 9:16 portrait aspect
ratio + `#shorts` in the title triggers Shorts treatment automatically.

Requires an OAuth token with the `youtube.upload` scope in
`social_accounts.access_token`; the channel ID lives in `account_id`.

Assisted fallback: deep link to YouTube Studio.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from aiplatform.skills.comms.publishers import _assisted
from aiplatform.skills.comms.publishers.base import PublishRequest, PublishResult


_UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3/videos"


def _build_deep_link(req: PublishRequest) -> str:
    return "https://studio.youtube.com/channel/UC/videos/upload"


def publish(req: PublishRequest, config: dict | None = None) -> PublishResult:
    config = config or {}
    token  = config.get("access_token") or os.environ.get("YOUTUBE_ACCESS_TOKEN")

    if not token:
        return _assisted.run(req, "youtube_channel", _build_deep_link)

    # Need a local video file to upload.
    video_path = _first_video_path(req.media_paths)
    if not video_path:
        return _assisted.run(req, "youtube_channel", _build_deep_link)

    title = (req.title or req.body[:80] or "EchoForge accessibility tip").strip()
    description = _compose_description(req)

    metadata: dict[str, Any] = {
        "snippet": {
            "title":       title[:100],
            "description": description[:5000],
            "tags":        req.hashtags or [],
            "categoryId":  "27",  # Education
        },
        "status": {
            "privacyStatus":      "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    if req.scheduled_for_iso:
        metadata["status"]["privacyStatus"]  = "private"
        metadata["status"]["publishAt"]      = req.scheduled_for_iso

    # Multipart simple upload. For files >100 MB the resumable protocol
    # is preferred — wire that up once we have a real upload token.
    try:
        with open(video_path, "rb") as fh:
            video_bytes = fh.read()
    except OSError as exc:
        return PublishResult(status="failed", provider="youtube_data",
                             error=f"cannot read video file: {exc}")

    try:
        resp = requests.post(
            f"{_UPLOAD_BASE}?uploadType=multipart&part=snippet,status",
            headers={"Authorization": f"Bearer {token}"},
            files=[
                ("metadata", (None, str(metadata).replace("'", '"'),
                              "application/json; charset=UTF-8")),
                ("video",    (Path(video_path).name, video_bytes, "video/*")),
            ],
            timeout=300,
        )
    except requests.RequestException as exc:
        return PublishResult(status="failed", provider="youtube_data",
                             error=f"upload error: {exc}")

    if resp.status_code >= 300:
        return PublishResult(
            status="failed", provider="youtube_data",
            error=f"youtube {resp.status_code}: {resp.text[:500]}",
        )

    data = resp.json() if resp.content else {}
    video_id = data.get("id", "")
    return PublishResult(
        status="success",
        external_post_id=video_id,
        external_url=f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        provider="youtube_data",
        response=data,
    )


def _first_video_path(media_paths: list[str]) -> str | None:
    for p in media_paths or []:
        if not p:
            continue
        lower = p.lower()
        if any(lower.endswith(ext) for ext in (".mp4", ".mov", ".webm", ".mkv")):
            return p
    return None


def _compose_description(req: PublishRequest) -> str:
    body = (req.body or "").rstrip()
    tags = req.hashtags or []
    if tags:
        body = f"{body}\n\n" + " ".join(t if t.startswith("#") else f"#{t}" for t in tags)
    return body
