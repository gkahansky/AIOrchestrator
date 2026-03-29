"""
One-time script: authorise Claude Code to write to your personal Google Drive.

Why this is needed:
  The service account (google_credentials.json) cannot write to personal My Drive folders
  because service accounts have no storage quota. This script generates a user OAuth token
  (google_token.json) so uploads are stored under YOUR Drive quota instead.

Steps:
  1. Go to Google Cloud Console → APIs & Services → Credentials
  2. Create an OAuth 2.0 Client ID → Desktop app → Download JSON
  3. Save it as google_oauth_client.json in the project root
  4. Run this script:  python scripts/setup_google_drive_oauth.py
  5. A browser window opens — sign in with your Google account and allow access
  6. google_token.json is written to the project root
  7. Add to .ENV:  GOOGLE_TOKEN_PATH=./google_token.json

After this, drive_write.py and drive_read.py will use your personal token automatically.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".ENV")

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES      = ["https://www.googleapis.com/auth/drive"]
CLIENT_FILE = Path(__file__).parent.parent / "google_oauth_client.json"
TOKEN_FILE  = Path(__file__).parent.parent / "google_token.json"


def main():
    if not CLIENT_FILE.exists():
        print(f"ERROR: OAuth client file not found: {CLIENT_FILE}")
        print()
        print("Steps:")
        print("  1. Go to console.cloud.google.com → APIs & Services → Credentials")
        print("  2. Create OAuth 2.0 Client ID → Application type: Desktop app")
        print("  3. Download the JSON and save it as:")
        print(f"     {CLIENT_FILE}")
        print("  4. Re-run this script")
        sys.exit(1)

    print("Opening browser for Google Drive authorisation...")
    print("Sign in with the Google account that owns your Drive folders.")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    print(f"\nToken saved to: {TOKEN_FILE}")
    print()
    print("Add this to your .ENV file:")
    print(f"  GOOGLE_TOKEN_PATH=./google_token.json")
    print()
    print("Drive uploads will now use your personal Google account quota.")


if __name__ == "__main__":
    main()
