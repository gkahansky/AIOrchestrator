"""
API authentication — simple Bearer token for internal/admin use.

The token is set via the API_SECRET_KEY environment variable.
Phase 3 (React frontend) will use this same token via a login endpoint.
"""

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)

_SECRET = os.environ.get("API_SECRET_KEY", "")


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency — raises 401 if token is missing or invalid."""
    if not _SECRET:
        # No secret configured — auth is disabled (dev / staging without secret)
        return "anonymous"

    if credentials is None or credentials.credentials != _SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
