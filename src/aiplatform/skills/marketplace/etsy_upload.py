"""
Skill: etsy_upload
Interact with the Etsy Open API v3 — create draft listings, attach images and files.

HARD CONSTRAINT: This skill never sets listing state to "active".
All listings are created as drafts. The human publishes manually via the Etsy dashboard.

Requires env vars:
    ETSY_API_KEY         — Etsy app keystring (from your app's API settings)
    ETSY_ACCESS_TOKEN    — OAuth2 access token
    ETSY_REFRESH_TOKEN   — OAuth2 refresh token (used to renew access token)
    ETSY_SHOP_ID         — Your Etsy shop numeric ID

Etsy Open API v3 docs: https://developers.etsy.com/documentation/
Rate limit: 10 req/s (be conservative, use 0.2s sleep between calls).
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_BASE = "https://openapi.etsy.com/v3/application"

# Digital Prints taxonomy ID in Etsy's taxonomy tree
# Art & Collectibles > Prints > Digital Prints
_DIGITAL_PRINTS_TAXONOMY_ID = 2078


# ─── Public API ───────────────────────────────────────────────────────────────

def create_draft_listing(
    title: str,
    description: str,
    price_usd: float,
    tags: list[str],
    taxonomy_id: int = _DIGITAL_PRINTS_TAXONOMY_ID,
    quantity: int = 999,
    shop_id: str | None = None,
) -> dict:
    """
    Create a new digital product listing as a draft.

    Never sets state=active — agent stops here; human publishes manually.

    Args:
        title:        Listing title (max 140 chars)
        description:  Full listing description (max 2000 chars)
        price_usd:    Price in USD (e.g. 4.99)
        tags:         Exactly 13 Etsy tags (max 20 chars each)
        taxonomy_id:  Etsy taxonomy node ID (default: Digital Prints)
        quantity:     Available quantity (default 999 for digital downloads)
        shop_id:      Override ETSY_SHOP_ID env var

    Returns:
        {listing_id, draft_url, title} on success, {error} on failure.
    """
    sid = shop_id or os.environ.get("ETSY_SHOP_ID", "")
    if not sid:
        return {"error": "ETSY_SHOP_ID not set in environment."}

    # Etsy price format: amount in minor units (cents), divisor 100
    amount = int(round(price_usd * 100))

    payload = {
        "title":           title[:140],
        "description":     description[:2000],
        "price":           {"amount": amount, "divisor": 100, "currency_code": "USD"},
        "quantity":        quantity,
        "who_made":        "i_did",
        "when_made":       "made_to_order",
        "is_digital":      True,
        "type":            "download",
        "state":           "draft",          # ← NEVER "active"
        "taxonomy_id":     taxonomy_id,
        "tags":            tags[:13],
        "is_supply":       False,
    }

    resp = _post(f"/shops/{sid}/listings", payload)
    if "error" in resp:
        return resp

    listing_id = resp.get("listing_id")
    return {
        "listing_id": listing_id,
        "draft_url":  f"https://www.etsy.com/your-shop/tools/listings/{listing_id}",
        "title":      resp.get("title", title),
    }


def upload_listing_image(
    listing_id: int | str,
    image_path: str,
    rank: int = 1,
    overwrite: bool = True,
    shop_id: str | None = None,
) -> dict:
    """
    Attach an image to a listing (must be PNG or JPG, ≤ 10MB, min 2000px on shortest side).

    Args:
        listing_id:  Etsy listing ID
        image_path:  Local path to the image file
        rank:        Display order (1 = main listing image, 2–10 = gallery)
        overwrite:   If True, replace an existing image at this rank
        shop_id:     Override ETSY_SHOP_ID env var

    Returns:
        {listing_image_id, rank, url_fullxfull} on success, {error} on failure.
    """
    sid = shop_id or os.environ.get("ETSY_SHOP_ID", "")
    if not sid:
        return {"error": "ETSY_SHOP_ID not set in environment."}

    path = Path(image_path)
    if not path.exists():
        return {"error": f"Image file not found: {image_path}"}

    try:
        with open(path, "rb") as f:
            files = {"image": (path.name, f, _mime_for(path))}
            data  = {"rank": rank, "overwrite": str(overwrite).lower()}
            resp  = _post_multipart(
                f"/shops/{sid}/listings/{listing_id}/images", data=data, files=files
            )
        if "error" in resp:
            return resp
        return {
            "listing_image_id": resp.get("listing_image_id"),
            "rank":             resp.get("rank"),
            "url_fullxfull":    resp.get("url_fullxfull"),
        }
    except Exception as exc:
        return {"error": str(exc)}


def upload_listing_file(
    listing_id: int | str,
    file_path: str,
    rank: int = 1,
    shop_id: str | None = None,
) -> dict:
    """
    Attach a digital download file to a listing (ZIP ≤ 20MB for Etsy hard limit).

    Args:
        listing_id:  Etsy listing ID
        file_path:   Local path to the ZIP file
        rank:        File rank (1 for primary download)
        shop_id:     Override ETSY_SHOP_ID env var

    Returns:
        {listing_file_id, filename, filesize_bytes} on success, {error} on failure.
    """
    sid = shop_id or os.environ.get("ETSY_SHOP_ID", "")
    if not sid:
        return {"error": "ETSY_SHOP_ID not set in environment."}

    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > 20:
        return {"error": f"ZIP exceeds Etsy 20MB limit: {size_mb:.1f}MB — run create_zip with compression fallback first"}

    try:
        with open(path, "rb") as f:
            files = {"file": (path.name, f, "application/zip")}
            data  = {"rank": rank, "name": path.name}
            resp  = _post_multipart(
                f"/shops/{sid}/listings/{listing_id}/files", data=data, files=files
            )
        if "error" in resp:
            return resp
        return {
            "listing_file_id": resp.get("listing_file_id"),
            "filename":        resp.get("filename"),
            "filesize_bytes":  resp.get("filesize"),
        }
    except Exception as exc:
        return {"error": str(exc)}


def get_listing(
    listing_id: int | str,
    shop_id: str | None = None,
) -> dict:
    """
    Fetch a listing by ID. Used to poll for state changes (draft → active).

    Returns normalised {listing_id, state, title, draft_url} on success, {error} on failure.
    """
    sid = shop_id or os.environ.get("ETSY_SHOP_ID", "")
    resp = _get(f"/listings/{listing_id}")
    if "error" in resp:
        return resp
    return {
        "listing_id": resp.get("listing_id"),
        "state":      resp.get("state"),
        "title":      resp.get("title"),
        "url":        resp.get("url"),
    }


def get_shop_listings(
    state: str = "draft",
    shop_id: str | None = None,
    limit: int = 25,
) -> list[dict]:
    """
    Return listings in a given state ("draft", "active", "inactive", etc.).
    Used to detect when a human has published a draft.
    """
    sid = shop_id or os.environ.get("ETSY_SHOP_ID", "")
    if not sid:
        return []
    resp = _get(f"/shops/{sid}/listings/{state}", params={"limit": limit})
    if isinstance(resp, dict) and "error" in resp:
        log.error("get_shop_listings failed: %s", resp)
        return []
    results = resp if isinstance(resp, list) else resp.get("results", [])
    return [
        {"listing_id": r.get("listing_id"), "state": r.get("state"), "title": r.get("title"), "url": r.get("url")}
        for r in results
    ]


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _auth_headers() -> dict:
    token   = os.environ.get("ETSY_ACCESS_TOKEN", "")
    api_key = os.environ.get("ETSY_API_KEY", "")
    if not token:
        raise ValueError("ETSY_ACCESS_TOKEN not set in environment.")
    headers = {"x-api-key": api_key, "Authorization": f"Bearer {token}"}
    return headers


def _get(path: str, params: dict | None = None) -> dict | list:
    try:
        r = requests.get(
            _BASE + path,
            params=params or {},
            headers=_auth_headers(),
            timeout=20,
        )
        time.sleep(0.2)
        if r.status_code == 404:
            return {"error": f"Not found: {path}"}
        return r.json()
    except Exception as exc:
        log.error("Etsy GET %s failed: %s", path, exc)
        return {"error": str(exc)}


def _post(path: str, payload: dict) -> dict:
    try:
        r = requests.post(
            _BASE + path,
            json=payload,
            headers={**_auth_headers(), "Content-Type": "application/json"},
            timeout=30,
        )
        time.sleep(0.2)
        data = r.json()
        if r.status_code not in (200, 201):
            err = data.get("error", data.get("message", str(data)))
            log.error("Etsy POST %s → %s: %s", path, r.status_code, err)
            return {"error": err, "status_code": r.status_code}
        return data
    except Exception as exc:
        log.error("Etsy POST %s failed: %s", path, exc)
        return {"error": str(exc)}


def _post_multipart(path: str, data: dict, files: dict) -> dict:
    try:
        r = requests.post(
            _BASE + path,
            data=data,
            files=files,
            headers=_auth_headers(),   # No Content-Type — requests sets multipart boundary
            timeout=60,
        )
        time.sleep(0.2)
        resp = r.json()
        if r.status_code not in (200, 201):
            err = resp.get("error", resp.get("message", str(resp)))
            log.error("Etsy multipart POST %s → %s: %s", path, r.status_code, err)
            return {"error": err, "status_code": r.status_code}
        return resp
    except Exception as exc:
        log.error("Etsy multipart POST %s failed: %s", path, exc)
        return {"error": str(exc)}


def _mime_for(path: Path) -> str:
    ext = path.suffix.lower()
    return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "application/octet-stream")
