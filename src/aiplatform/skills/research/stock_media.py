"""Stock media — Pexels-backed image / video search.

Pexels is free (with API key + attribution) and has good coverage for the
content-engine use case: editorial b-roll for accessibility / business
content. The skill returns lightweight metadata (URL + dimensions + photographer
attribution) the caller can hand to FFmpeg or download locally.

Graceful degradation: returns empty lists when `PEXELS_API_KEY` is absent.
Search itself is free; we still log a notional $0 cost event for telemetry.

Attribution: Pexels' license requires crediting photographer. Callers must
surface `photographer_credit` in published copy or footer.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests


_PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
_PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"


def search_pexels(
    query: str,
    *,
    media: str = "photo",
    per_page: int = 8,
    orientation: str = "landscape",  # landscape | portrait | square
    size: str = "medium",            # large | medium | small
) -> dict[str, Any]:
    """Return Pexels results for `query`. `media` ∈ {photo, video}."""
    api_key = os.environ.get("PEXELS_API_KEY", "")
    if not api_key or not (query or "").strip():
        return {"results": [], "tool_used": "pexels", "cost_usd": 0.0,
                "error": "PEXELS_API_KEY missing or empty query"}

    url = _PEXELS_VIDEO_URL if media == "video" else _PEXELS_PHOTO_URL
    params = {
        "query":       query,
        "per_page":    per_page,
        "orientation": orientation,
        "size":        size,
    }
    try:
        resp = requests.get(
            url,
            params=params,
            headers={"Authorization": api_key},
            timeout=20,
        )
    except requests.RequestException as exc:
        return {"results": [], "tool_used": "pexels", "cost_usd": 0.0,
                "error": f"pexels request error: {exc}"}

    if resp.status_code >= 300:
        return {"results": [], "tool_used": "pexels", "cost_usd": 0.0,
                "error": f"pexels {resp.status_code}: {resp.text[:300]}"}

    data = resp.json() if resp.content else {}
    raw = (data.get("videos") if media == "video" else data.get("photos")) or []

    results = [_normalize_video(r) if media == "video" else _normalize_photo(r)
               for r in raw]
    return {"results": results, "tool_used": "pexels", "cost_usd": 0.0,
            "media": media, "total_results": data.get("total_results", len(results))}


def download_pexels_asset(url: str, output_dir: str | Path = "./output",
                          filename: str | None = None) -> str:
    """Download a Pexels image / video to local disk. Returns the local path.

    Pexels content URLs are direct, no auth header required. Used by the
    scripted explainer assembler so FFmpeg can read the file locally.
    """
    if not url:
        return ""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = filename or url.rsplit("/", 1)[-1].split("?", 1)[0]
    out_path = out_dir / name
    try:
        resp = requests.get(url, timeout=60, stream=True)
        if resp.status_code >= 300:
            return ""
        with open(out_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    fh.write(chunk)
    except requests.RequestException:
        return ""
    return str(out_path)


# ── Normalisers ───────────────────────────────────────────────────────────────

def _normalize_photo(r: dict) -> dict:
    src = r.get("src") or {}
    return {
        "kind":               "photo",
        "id":                 r.get("id"),
        "url":                src.get("large2x") or src.get("large") or src.get("original") or "",
        "preview_url":        src.get("medium", ""),
        "width":              r.get("width"),
        "height":             r.get("height"),
        "alt":                r.get("alt", ""),
        "photographer":       r.get("photographer", ""),
        "photographer_url":   r.get("photographer_url", ""),
        "photographer_credit": f"Photo by {r.get('photographer', 'Pexels')} on Pexels",
    }


def _normalize_video(r: dict) -> dict:
    files = (r.get("video_files") or [])
    # Prefer 1080p mp4; fall back to highest-quality available.
    preferred = next((f for f in files
                      if f.get("file_type") == "video/mp4" and (f.get("height") or 0) <= 1080),
                     None)
    file_url = (preferred or files[0] if files else {}).get("link", "") if files else ""
    return {
        "kind":               "video",
        "id":                 r.get("id"),
        "url":                file_url,
        "preview_url":        (r.get("image") or ""),
        "width":              r.get("width"),
        "height":             r.get("height"),
        "duration_s":         r.get("duration"),
        "photographer":       (r.get("user") or {}).get("name", ""),
        "photographer_url":   (r.get("user") or {}).get("url", ""),
        "photographer_credit":
            f"Video by {(r.get('user') or {}).get('name', 'Pexels')} on Pexels",
    }
