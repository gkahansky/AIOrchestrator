"""
Google OAuth authentication endpoint.

POST /api/auth/google
  Body: { "credential": "<Google ID token>" }
  Returns: { "token": "<JWT session token>", "email": "...", "expires_in": 86400 }

The credential is the raw Google ID token from the Google Identity Services
(GIS) JavaScript library's CredentialResponse.credential field.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from aiplatform.webapp.auth import (
    ALLOWED_EMAIL,
    GOOGLE_CLIENT_ID,
    JWT_EXPIRY_HOURS,
    _auth_disabled,
    create_session_token,
    verify_google_credential,
)

router = APIRouter()


class GoogleAuthRequest(BaseModel):
    credential: str


class GoogleAuthResponse(BaseModel):
    token: str
    email: str
    expires_in: int  # seconds


@router.post("/google", response_model=GoogleAuthResponse)
def google_login(req: GoogleAuthRequest) -> GoogleAuthResponse:
    """
    Exchange a Google ID token for a platform JWT session token.

    Only the email address matching ALLOWED_EMAIL is permitted.
    """
    if _auth_disabled:
        # Dev mode — return a dummy token so the frontend still works
        return GoogleAuthResponse(
            token="dev-mode",
            email="dev@local",
            expires_in=JWT_EXPIRY_HOURS * 3600,
        )

    claims = verify_google_credential(req.credential)
    email: str = claims.get("email", "")

    if not email or email.lower() != ALLOWED_EMAIL.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This Google account is not authorised to access this platform.",
        )

    token = create_session_token(email)
    return GoogleAuthResponse(
        token=token,
        email=email,
        expires_in=JWT_EXPIRY_HOURS * 3600,
    )


@router.get("/config")
def auth_config() -> dict:
    """
    Return public OAuth configuration for the frontend.
    Called before the login page renders to get the Google Client ID.
    This endpoint is intentionally unauthenticated.
    """
    return {
        "google_client_id": GOOGLE_CLIENT_ID,
        "auth_enabled": not _auth_disabled,
    }
