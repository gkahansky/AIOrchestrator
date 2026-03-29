"""
Etsy API diagnostic — tests auth with multiple credential combinations.

Helps identify whether x-api-key should be keystring, shared secret, or combined.

Usage:
    python scripts/etsy_diag.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
import requests

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".ENV")

BASE = "https://openapi.etsy.com/v3/application"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

keystring     = os.environ.get("ETSY_API_KEY", "")
secret        = os.environ.get("ETSY_API_SECRET", "")
access_token  = os.environ.get("ETSY_ACCESS_TOKEN", "")
refresh_token = os.environ.get("ETSY_REFRESH_TOKEN", "")
shop_id       = os.environ.get("ETSY_SHOP_ID", "")

print("=== Credential inventory ===")
print(f"ETSY_API_KEY         length={len(keystring):3d}  first4={keystring[:4]!r}")
print(f"ETSY_API_SECRET      length={len(secret):3d}  first4={secret[:4]!r}")
print(f"ETSY_ACCESS_TOKEN    length={len(access_token):3d}")
print(f"ETSY_REFRESH_TOKEN   length={len(refresh_token):3d}")
print(f"ETSY_SHOP_ID         {shop_id!r}")
print()


def test(label: str, headers: dict, url: str = f"{BASE}/openapi-ping") -> None:
    safe = {k: (v[:20] + "...") if len(v) > 20 else v for k, v in headers.items()}
    print(f"--- {label} ---")
    print(f"    headers: {safe}")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"    status: {r.status_code}")
        try:
            print(f"    body:   {r.json()}")
        except Exception:
            print(f"    body:   {r.text[:200]}")
    except Exception as e:
        print(f"    ERROR:  {e}")
    print()


# Test 1 — keystring only (public ping, no OAuth)
test("Keystring only (public ping)", {"x-api-key": keystring})

# Test 2 — secret only as x-api-key
if secret:
    test("Secret as x-api-key", {"x-api-key": secret})

# Test 3 — keystring + Bearer token (authenticated)
if access_token:
    test("Keystring + Bearer (authenticated ping)",
         {"x-api-key": keystring, "Authorization": f"Bearer {access_token}"})

# Test 4 — keystring:secret combined
if secret:
    test("keystring:secret combined", {"x-api-key": f"{keystring}:{secret}"})

# Test 5 — try shop endpoint with current token
if access_token and shop_id:
    test(
        f"GET /shops/{shop_id} (authenticated)",
        {"x-api-key": keystring, "Authorization": f"Bearer {access_token}"},
        url=f"{BASE}/shops/{shop_id}",
    )

# Test 6 — try token refresh
print("=== Token refresh test ===")
if refresh_token and keystring:
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "refresh_token",
            "client_id":     keystring,
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    print(f"Refresh status: {r.status_code}")
    print(f"Refresh body:   {r.json()}")
else:
    print("Skipped — ETSY_REFRESH_TOKEN or ETSY_API_KEY not set")
