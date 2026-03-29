"""
Shared Drive authentication helper.

Priority:
  1. OAuth user token (GOOGLE_TOKEN_PATH) — uses the user's own quota, required for
     uploading to personal My Drive folders from a service account project.
  2. Service account (GOOGLE_CREDENTIALS_PATH) — falls back when no user token exists.
     Works for Shared Drives and read operations, but cannot write to personal My Drive.

Run scripts/setup_google_drive_oauth.py once to generate the user token.
"""

import os
from pathlib import Path

from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]

_OAUTH_CLIENT_PATH_ENV  = "GOOGLE_OAUTH_CLIENT_PATH"   # OAuth client_secret JSON
_TOKEN_PATH_ENV         = "GOOGLE_TOKEN_PATH"           # Saved user token JSON
_SERVICE_ACCOUNT_ENV    = "GOOGLE_CREDENTIALS_PATH"     # Service account JSON


def get_drive_service():
    """Return an authenticated Drive v3 service, preferring user OAuth token."""

    token_path = os.environ.get(_TOKEN_PATH_ENV, "./google_token.json")

    if Path(token_path).exists():
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Persist refreshed token
            Path(token_path).write_text(creds.to_json(), encoding="utf-8")

        return build("drive", "v3", credentials=creds, cache_discovery=False)

    # Fall back to service account
    from google.oauth2 import service_account
    sa_path = os.environ.get(_SERVICE_ACCOUNT_ENV, "./google_credentials.json")
    creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)
