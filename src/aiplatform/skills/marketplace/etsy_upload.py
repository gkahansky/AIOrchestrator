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

_BASE       = "https://openapi.etsy.com/v3/application"
_TOKEN_URL  = "https://api.etsy.com/v3/public/oauth/token"

# In-process cache so we refresh at most once per interpreter session
_token_cache: dict = {}   # {"access_token": str, "expires_at": float}


def _ensure_fresh_token() -> str:
    """
    Return a valid access token, refreshing automatically if expired or close to expiry.
    Writes the new token back to the environment (and .env file if dotenv is present)
    so subsequent calls within the same process see the updated value.
    """
    now = time.time()
    cached = _token_cache.get("access_token", "")
    expires_at = _token_cache.get("expires_at", 0.0)

    # Use cached token if it has > 60 s left
    if cached and now < expires_at - 60:
        return cached

    # Attempt refresh
    api_key       = os.environ.get("ETSY_API_KEY", "")
    refresh_token = os.environ.get("ETSY_REFRESH_TOKEN", "")

    if not api_key or not refresh_token:
        # Fall back to whatever is in the environment
        return os.environ.get("ETSY_ACCESS_TOKEN", "")

    try:
        resp = requests.post(
            _TOKEN_URL,
            data={
                "grant_type":    "refresh_token",
                "client_id":     api_key,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200 and "access_token" in data:
            new_token         = data["access_token"]
            new_refresh       = data.get("refresh_token", refresh_token)
            expires_in        = int(data.get("expires_in", 3600))

            # Update in-process cache
            _token_cache["access_token"] = new_token
            _token_cache["expires_at"]   = now + expires_in

            # Propagate to environment so other calls in this process use it
            os.environ["ETSY_ACCESS_TOKEN"]  = new_token
            os.environ["ETSY_REFRESH_TOKEN"] = new_refresh

            # Persist to .env file if python-dotenv is available
            try:
                from dotenv import set_key as _set_key
                env_path = Path(__file__).parent
                # Walk up to find .ENV
                for _ in range(6):
                    candidate = env_path / ".ENV"
                    if candidate.exists():
                        _set_key(str(candidate), "ETSY_ACCESS_TOKEN",  new_token,   quote_mode="never")
                        _set_key(str(candidate), "ETSY_REFRESH_TOKEN", new_refresh, quote_mode="never")
                        break
                    env_path = env_path.parent
            except Exception:
                pass  # dotenv not available — env vars already updated above

            log.debug("Etsy token refreshed, expires in %ds", expires_in)
            return new_token
        else:
            log.warning("Etsy token refresh failed (%s): %s", resp.status_code, data)
    except Exception as exc:
        log.warning("Etsy token refresh error: %s", exc)

    # If refresh failed, return whatever token is currently in env
    return os.environ.get("ETSY_ACCESS_TOKEN", "")

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

    payload = {
        "title":           title[:140],
        "description":     description[:2000],
        "price":           round(price_usd, 2),
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
    resp = _get(f"/shops/{sid}/listings", params={"state": state, "limit": limit})
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
    token      = _ensure_fresh_token()
    api_key    = os.environ.get("ETSY_API_KEY", "")
    api_secret = os.environ.get("ETSY_API_SECRET", "")
    if not token:
        raise ValueError("ETSY_ACCESS_TOKEN not set and token refresh failed.")
    # Etsy requires keystring:sharedsecret in x-api-key header
    x_api_key = f"{api_key}:{api_secret}" if api_secret else api_key
    return {"x-api-key": x_api_key, "Authorization": f"Bearer {token}"}


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
            if isinstance(data, dict):
                err = data.get("error", data.get("message", str(data)))
            else:
                err = str(data)  # Etsy sometimes returns a list of validation errors
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
