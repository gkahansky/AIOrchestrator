"""
Etsy OAuth2 — refresh access token using the stored refresh token.

Etsy access tokens expire in 3600 seconds (1 hour).
Run this script before any Phase 6 run to get a fresh token.

Usage:
    python scripts/etsy_refresh_token.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv, set_key
import requests

ENV_PATH = Path(__file__).parent.parent / ".ENV"
load_dotenv(dotenv_path=ENV_PATH)

TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"


def refresh() -> dict:
    keystring     = os.environ.get("ETSY_API_KEY", "")
    refresh_token = os.environ.get("ETSY_REFRESH_TOKEN", "")

    if not keystring:
        return {"error": "ETSY_API_KEY not set"}
    if not refresh_token:
        return {"error": "ETSY_REFRESH_TOKEN not set"}

    print(f"Refreshing token (keystring length={len(keystring)}, refresh_token length={len(refresh_token)})")

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "refresh_token",
            "client_id":     keystring,
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    print(f"Status: {resp.status_code}")
    data = resp.json()

    if resp.status_code != 200 or "access_token" not in data:
        return {"error": data.get("error", str(data)), "raw": data}

    return {
        "access_token":  data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),  # may be rotated
        "expires_in":    data.get("expires_in", 3600),
    }


def main():
    result = refresh()

    if "error" in result:
        print(f"\nERROR: {result['error']}")
        if "raw" in result:
            print(f"Raw response: {result['raw']}")
        sys.exit(1)

    print(f"\nNew token expires in: {int(result['expires_in']) // 60} minutes")
    print(f"ETSY_ACCESS_TOKEN (first 20 chars): {result['access_token'][:20]}...")

    answer = input("\nWrite new tokens to .env? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        set_key(str(ENV_PATH), "ETSY_ACCESS_TOKEN",  result["access_token"],  quote_mode="never")
        set_key(str(ENV_PATH), "ETSY_REFRESH_TOKEN", result["refresh_token"], quote_mode="never")
        print("Tokens written to .env")
        print("\nNow run: python scripts/etsy_diag.py  (to verify auth)")
    else:
        print(f"\nETSY_ACCESS_TOKEN={result['access_token']}")
        print(f"ETSY_REFRESH_TOKEN={result['refresh_token']}")


if __name__ == "__main__":
    main()
