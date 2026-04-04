"""
Gmail OAuth setup script — adds Gmail scope to the existing Google token.

Run this ONCE locally to extend the Google OAuth token to include Gmail access.
The resulting token is then base64-encoded and stored in Railway as GOOGLE_DRIVE_TOKEN_JSON
(same env var as Drive — the token now covers both scopes).

Usage:
    python scripts/setup_gmail_oauth.py

Requirements:
    - google-auth-oauthlib installed  (pip install google-auth-oauthlib)
    - google_oauth_client_web.json in project root  (OAuth 2.0 Web Client credentials)
      Download from: Google Cloud Console → APIs & Services → Credentials → your OAuth client
    - Gmail API enabled in your Google Cloud project
      Enable at: https://console.cloud.google.com/apis/library/gmail.googleapis.com

What this script does:
    1. Reads your existing google_token.json (Drive credentials)
    2. Re-runs the OAuth flow requesting Drive + Gmail scopes
    3. Saves the new token to google_token.json
    4. Prints the base64-encoded token for pasting into Railway GOOGLE_DRIVE_TOKEN_JSON
"""

import base64
import json
import os
import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.modify",
]

TOKEN_PATH  = Path(os.environ.get("GOOGLE_TOKEN_PATH", "./google_token.json"))
CLIENT_FILE = Path("google_oauth_client_desktop.json")


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        print("ERROR: google-auth-oauthlib not installed.")
        print("Run: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        sys.exit(1)

    if not CLIENT_FILE.exists():
        print(f"ERROR: {CLIENT_FILE} not found.")
        print("Download your OAuth 2.0 Web Client JSON from Google Cloud Console:")
        print("  APIs & Services → Credentials → your OAuth 2.0 Client → Download JSON")
        sys.exit(1)

    creds = None

    # Try to load existing token and refresh it with new scopes
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            if creds and creds.valid:
                existing_scopes = set(creds.scopes or [])
                needed = {s.rstrip("/") for s in SCOPES}
                if needed.issubset({s.rstrip("/") for s in existing_scopes}):
                    print("Existing token already has all required scopes.")
                    _print_token(TOKEN_PATH)
                    return
        except Exception:
            pass  # Token invalid or scope mismatch — re-auth below

    print("Starting OAuth flow — a browser window will open.")
    print(f"Requesting scopes: {SCOPES}\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    # Save updated token
    TOKEN_PATH.write_text(creds.to_json())
    print(f"\nToken saved to {TOKEN_PATH}")

    _print_token(TOKEN_PATH)


def _print_token(token_path: Path) -> None:
    token_b64 = base64.b64encode(token_path.read_bytes()).decode()
    print("\n" + "=" * 60)
    print("COPY THIS VALUE INTO RAILWAY → GOOGLE_DRIVE_TOKEN_JSON:")
    print("=" * 60)
    print(token_b64)
    print("=" * 60)
    print("\nThis replaces the existing GOOGLE_DRIVE_TOKEN_JSON value.")
    print("Both Drive and Gmail will use this token.")


if __name__ == "__main__":
    main()
