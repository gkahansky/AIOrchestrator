"""
Shared Drive authentication helper.

Priority:
  1. OAuth user token (GOOGLE_TOKEN_PATH) — uses the user's own quota, required for
     uploading to personal My Drive folders from a service account project.
  2. Service account (GOOGLE_CREDENTIALS_PATH) — falls back when no user token exists.
     Works for Shared Drives and read operations, but cannot write to personal My Drive.

Run scripts/setup_google_drive_oauth.py once to generate the user token.
"""

import logging
import os
from pathlib import Path

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]

_OAUTH_CLIENT_PATH_ENV  = "GOOGLE_OAUTH_CLIENT_PATH"   # OAuth client_secret JSON
_TOKEN_PATH_ENV         = "GOOGLE_TOKEN_PATH"           # Saved user token JSON
_SERVICE_ACCOUNT_ENV    = "GOOGLE_CREDENTIALS_PATH"     # Service account JSON


def get_drive_service():
    """Return an authenticated Drive v3 service, preferring user OAuth token."""

    token_path = os.environ.get(_TOKEN_PATH_ENV, "./google_token.json")
    logger.info("Drive auth: GOOGLE_TOKEN_PATH=%s exists=%s", token_path, Path(token_path).exists())

    if Path(token_path).exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request

            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logger.info("Drive auth: OAuth token loaded, expired=%s has_refresh=%s", creds.expired, bool(creds.refresh_token))

            if creds.expired and creds.refresh_token:
                logger.info("Drive auth: refreshing OAuth token...")
                creds.refresh(Request())
                # Persist refreshed token so next call skips the refresh
                Path(token_path).write_text(creds.to_json(), encoding="utf-8")
                logger.info("Drive auth: OAuth token refreshed and saved")

            logger.info("Drive auth: using OAuth user credentials (personal quota)")
            return build("drive", "v3", credentials=creds, cache_discovery=False)

        except Exception as exc:
            # Log clearly — do NOT silently fall through to service account on refresh errors,
            # as service accounts cannot write to personal My Drive (quota error).
            logger.error("Drive auth: OAuth token failed (%s) — raising, not falling back to service account", exc)
            raise RuntimeError(
                f"Google Drive OAuth authentication failed: {exc}. "
                "Check GOOGLE_DRIVE_TOKEN_JSON and GOOGLE_TOKEN_PATH env vars, "
                "or re-run scripts/setup_google_drive_oauth.py to regenerate the token."
            ) from exc

    # Only reach here if no token file exists at all
    logger.warning(
        "Drive auth: no OAuth token file at %s — falling back to service account. "
        "Service accounts CANNOT write to personal My Drive (quota error). "
        "Set GOOGLE_DRIVE_TOKEN_JSON + GOOGLE_TOKEN_PATH to fix.",
        token_path,
    )
    from google.oauth2 import service_account
    sa_path = os.environ.get(_SERVICE_ACCOUNT_ENV, "./google_credentials.json")
    creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)
