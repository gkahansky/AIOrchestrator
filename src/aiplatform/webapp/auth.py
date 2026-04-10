"""
API authentication — Google OAuth + JWT session tokens.

Flow:
  1. Frontend sends Google credential (ID token) to POST /api/auth/google
  2. Backend verifies the token with Google's tokeninfo endpoint
  3. Backend checks the email matches ALLOWED_EMAIL env var
  4. Backend returns a signed JWT (24h expiry)
  5. Frontend stores JWT in localStorage and sends it as Bearer token
  6. require_auth() dependency verifies the JWT on every request

Environment variables required:
  GOOGLE_CLIENT_ID   — from Google Cloud Console OAuth 2.0 credentials
  ALLOWED_EMAIL      — your Gmail address (only this email can log in)
  JWT_SECRET         — random secret for signing session JWTs (generate once)

Dev mode (no env vars set): auth is disabled, all requests pass as "anonymous".
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
ALLOWED_EMAIL    = os.environ.get("ALLOWED_EMAIL", "")  # kept for backward compat
JWT_SECRET       = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM    = "HS256"
JWT_EXPIRY_HOURS = 24

# ALLOWED_EMAILS supports comma-separated list: "a@x.com,b@y.com"
# Falls back to ALLOWED_EMAIL for backward compatibility.
_raw = os.environ.get("ALLOWED_EMAILS", ALLOWED_EMAIL)
ALLOWED_EMAILS: set[str] = {e.strip().lower() for e in _raw.split(",") if e.strip()}

_auth_disabled = not (GOOGLE_CLIENT_ID and ALLOWED_EMAILS and JWT_SECRET)


def create_session_token(email: str) -> str:
    """Issue a signed JWT session token for the authenticated user."""
    payload = {
        "sub":   email,
        "email": email,
        "exp":   datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat":   datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_google_credential(credential: str) -> dict:
    """
    Verify a Google ID token using google-auth.
    Returns the token claims dict if valid, raises HTTPException otherwise.
    """
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        request = google_requests.Request()
        claims = id_token.verify_oauth2_token(
            credential, request, GOOGLE_CLIENT_ID
        )
        return claims
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google credential: {exc}",
        )


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency — raises 401 if JWT is missing or invalid."""
    if _auth_disabled:
        return "anonymous"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        return payload["email"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please sign in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
