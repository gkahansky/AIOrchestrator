"""OAuth helpers for the social publishers.

Per-platform: build the consent URL, exchange the auth code for tokens,
refresh expiring tokens. Stateless — handlers receive everything they need
and return typed payloads the router persists into `social_accounts`.

State token: HMAC-signed brand_id + platform + nonce (uses JWT_SECRET).
The router signs at `/oauth/{platform}/start` and verifies at
`/oauth/{platform}/callback` to defeat CSRF and bind the callback to the
brand that initiated it.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import jwt
import requests


# ── State token ───────────────────────────────────────────────────────────────

_STATE_TTL_SECONDS = 600


def _state_secret() -> str:
    return os.environ.get("JWT_SECRET", "")


def sign_state(brand_id: str, platform: str) -> str:
    """Issue an OAuth `state` value. Survives the redirect to the IdP and back."""
    payload = {
        "brand_id": brand_id,
        "platform": platform,
        "nonce":    secrets.token_urlsafe(16),
        "exp":      int(time.time()) + _STATE_TTL_SECONDS,
    }
    return jwt.encode(payload, _state_secret(), algorithm="HS256")


def verify_state(token: str, expected_platform: str) -> dict[str, Any]:
    """Decode + validate. Raises ValueError on bad/expired/wrong-platform tokens."""
    try:
        data = jwt.decode(token, _state_secret(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise ValueError(f"invalid oauth state: {exc}") from exc
    if data.get("platform") != expected_platform:
        raise ValueError("oauth state platform mismatch")
    if not data.get("brand_id"):
        raise ValueError("oauth state missing brand_id")
    return data


# ── Result shape ──────────────────────────────────────────────────────────────

@dataclass
class OAuthTokenResult:
    access_token: str
    refresh_token: str = ""
    expires_at: datetime | None = None
    account_id: str = ""
    account_name: str = ""
    scopes: list[str] | None = None
    raw: dict[str, Any] | None = None


# ── Redirect URI ──────────────────────────────────────────────────────────────

def redirect_uri(platform: str) -> str:
    base = os.environ.get("OAUTH_REDIRECT_BASE_URL", "https://api.planbadmin.com").rstrip("/")
    return f"{base}/api/ventures/content-engine/oauth/{platform}/callback"


# ── LinkedIn ──────────────────────────────────────────────────────────────────

_LI_AUTH = "https://www.linkedin.com/oauth/v2/authorization"
_LI_TOKEN = "https://www.linkedin.com/oauth/v2/accessToken"
_LI_ORGS = "https://api.linkedin.com/v2/organizationAcls"


def linkedin_auth_url(brand_id: str) -> str:
    client_id = os.environ.get("LINKEDIN_CLIENT_ID", "")
    return f"{_LI_AUTH}?" + urlencode({
        "response_type": "code",
        "client_id":     client_id,
        "redirect_uri":  redirect_uri("linkedin"),
        "scope":         "r_organization_social w_organization_social r_basicprofile",
        "state":         sign_state(brand_id, "linkedin"),
    })


def linkedin_exchange_code(code: str) -> OAuthTokenResult:
    client_id     = os.environ.get("LINKEDIN_CLIENT_ID", "")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
    if not (client_id and client_secret):
        raise RuntimeError("LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET not set")

    resp = requests.post(
        _LI_TOKEN,
        data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  redirect_uri("linkedin"),
            "client_id":     client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 5184000)))
    token = data["access_token"]

    # Resolve the first Company Page the user is an admin on, so we can
    # pre-fill account_id with the org URN required by ugcPosts.
    org_urn, org_name = "", ""
    try:
        org_resp = requests.get(
            _LI_ORGS,
            params={"q": "roleAssignee", "role": "ADMINISTRATOR"},
            headers={"Authorization": f"Bearer {token}",
                     "X-Restli-Protocol-Version": "2.0.0"},
            timeout=20,
        )
        if org_resp.status_code < 300:
            elements = (org_resp.json() or {}).get("elements") or []
            if elements:
                org_urn = elements[0].get("organization", "")
                # Friendly name via a second call — best effort.
                if org_urn:
                    name_resp = requests.get(
                        f"https://api.linkedin.com/v2/organizations/{org_urn.split(':')[-1]}",
                        headers={"Authorization": f"Bearer {token}",
                                 "X-Restli-Protocol-Version": "2.0.0"},
                        timeout=20,
                    )
                    if name_resp.status_code < 300:
                        org_name = (name_resp.json() or {}).get("localizedName", "")
    except requests.RequestException:
        pass

    return OAuthTokenResult(
        access_token=token,
        refresh_token=data.get("refresh_token", ""),
        expires_at=expires_at,
        account_id=org_urn,
        account_name=org_name,
        scopes=(data.get("scope") or "").split(),
        raw=data,
    )


# ── Meta (Facebook Page + Instagram Business) ─────────────────────────────────

_META_AUTH = "https://www.facebook.com/v19.0/dialog/oauth"
_META_TOKEN = "https://graph.facebook.com/v19.0/oauth/access_token"
_META_PAGES = "https://graph.facebook.com/v19.0/me/accounts"


def meta_auth_url(brand_id: str) -> str:
    client_id = os.environ.get("META_APP_ID", "")
    return f"{_META_AUTH}?" + urlencode({
        "client_id":     client_id,
        "redirect_uri":  redirect_uri("meta"),
        "response_type": "code",
        "scope":         ",".join([
            "pages_show_list",
            "pages_manage_posts",
            "pages_read_engagement",
            "instagram_basic",
            "instagram_content_publish",
            "business_management",
        ]),
        "state":         sign_state(brand_id, "meta"),
    })


def meta_exchange_code(code: str) -> dict[str, Any]:
    """Exchange code → short-lived user token → long-lived user token.

    Returns the raw Meta response for the long-lived token + the discovered
    pages and IG accounts. The router fans this out into one SocialAccount
    row per (page, IG-account) pair.
    """
    client_id     = os.environ.get("META_APP_ID", "")
    client_secret = os.environ.get("META_APP_SECRET", "")
    if not (client_id and client_secret):
        raise RuntimeError("META_APP_ID / META_APP_SECRET not set")

    resp = requests.get(
        _META_TOKEN,
        params={
            "client_id":     client_id,
            "client_secret": client_secret,
            "code":          code,
            "redirect_uri":  redirect_uri("meta"),
        },
        timeout=30,
    )
    resp.raise_for_status()
    short = resp.json()

    # Exchange for the 60-day long-lived user token.
    longlived_resp = requests.get(
        _META_TOKEN,
        params={
            "grant_type":      "fb_exchange_token",
            "client_id":       client_id,
            "client_secret":   client_secret,
            "fb_exchange_token": short["access_token"],
        },
        timeout=30,
    )
    longlived_resp.raise_for_status()
    longlived = longlived_resp.json()
    user_token = longlived["access_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(longlived.get("expires_in", 5184000)))

    # Discover Pages the user admins. Each Page returns its own (page) token
    # which is what we actually store for publishing.
    pages_resp = requests.get(
        _META_PAGES,
        params={"access_token": user_token,
                "fields": "id,name,access_token,instagram_business_account{id,username}"},
        timeout=30,
    )
    pages_resp.raise_for_status()
    pages = (pages_resp.json() or {}).get("data") or []

    return {
        "user_token":  user_token,
        "expires_at":  expires_at,
        "pages":       pages,
    }


# ── YouTube (Google OAuth) ────────────────────────────────────────────────────

_GOOG_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOG_TOKEN = "https://oauth2.googleapis.com/token"
_YT_CHANNELS = "https://www.googleapis.com/youtube/v3/channels"


def youtube_auth_url(brand_id: str) -> str:
    client_id = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID", "")
    return f"{_GOOG_AUTH}?" + urlencode({
        "client_id":     client_id,
        "redirect_uri":  redirect_uri("youtube"),
        "response_type": "code",
        "scope":         "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube",
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         sign_state(brand_id, "youtube"),
    })


def youtube_exchange_code(code: str) -> OAuthTokenResult:
    client_id     = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET", "")
    if not (client_id and client_secret):
        raise RuntimeError("YOUTUBE_OAUTH_CLIENT_ID / YOUTUBE_OAUTH_CLIENT_SECRET not set")

    resp = requests.post(
        _GOOG_TOKEN,
        data={
            "code":          code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  redirect_uri("youtube"),
            "grant_type":    "authorization_code",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600)))
    token = data["access_token"]

    # Resolve the channel id (so we can pre-fill account_id + name).
    channel_id, channel_name = "", ""
    try:
        ch_resp = requests.get(
            _YT_CHANNELS,
            params={"mine": "true", "part": "id,snippet"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        if ch_resp.status_code < 300:
            items = (ch_resp.json() or {}).get("items") or []
            if items:
                channel_id = items[0].get("id", "")
                channel_name = ((items[0].get("snippet") or {}).get("title") or "")
    except requests.RequestException:
        pass

    return OAuthTokenResult(
        access_token=token,
        refresh_token=data.get("refresh_token", ""),
        expires_at=expires_at,
        account_id=channel_id,
        account_name=channel_name,
        scopes=(data.get("scope") or "").split(),
        raw=data,
    )


def youtube_refresh(refresh_token: str) -> OAuthTokenResult:
    """Exchange a refresh_token for a fresh access_token. YouTube tokens expire hourly."""
    client_id     = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET", "")
    resp = requests.post(
        _GOOG_TOKEN,
        data={
            "client_id":     client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type":    "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return OAuthTokenResult(
        access_token=data["access_token"],
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600))),
        scopes=(data.get("scope") or "").split(),
        raw=data,
    )


# ── Generic ensure-fresh helper ───────────────────────────────────────────────

def ensure_fresh_token(account, *, db) -> str:
    """Refresh `account.access_token` if it's within 5 minutes of expiry.

    Currently only YouTube has a working refresh flow in code; LinkedIn /
    Meta long-lived tokens are valid 60+ days and we re-auth at expiry.
    Returns the (possibly refreshed) access_token.
    """
    if not account or not account.access_token:
        return ""
    if not account.expires_at:
        return account.access_token

    near_expiry = account.expires_at - timedelta(minutes=5)
    if datetime.now(timezone.utc) < near_expiry:
        return account.access_token

    if account.platform == "youtube_channel" and account.refresh_token:
        try:
            fresh = youtube_refresh(account.refresh_token)
            account.access_token = fresh.access_token
            account.expires_at   = fresh.expires_at
            db.commit()
            return fresh.access_token
        except Exception:
            return account.access_token

    return account.access_token
