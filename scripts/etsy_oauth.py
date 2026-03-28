"""
Etsy OAuth2 — one-time token exchange.

Reads ETSY_API_KEY (Keystring) from .env, opens the Etsy consent page in your
browser, catches the redirect on a local server, and prints the access_token +
refresh_token to paste into .env.

Etsy uses OAuth2 with PKCE (no client_secret needed for the token exchange).

BEFORE RUNNING:
  1. Go to https://www.etsy.com/developers/your-apps → your app → edit
  2. Add this exact redirect URI under "Callback URLs":
         http://localhost:3003/callback
  3. Save the app, then run this script.

Usage:
    python scripts/etsy_oauth.py

The script will:
  - Open https://www.etsy.com/oauth/connect in your browser
  - Start a local server on port 3003 to catch the callback
  - Exchange the code for tokens
  - Print the tokens + offer to write them directly to .env
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv, set_key
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".ENV")

# ─── Config ───────────────────────────────────────────────────────────────────

API_KEY      = os.environ.get("ETSY_API_KEY", "")
REDIRECT_URI = "http://localhost:3003/callback"
AUTH_URL     = "https://www.etsy.com/oauth/connect"
TOKEN_URL    = "https://api.etsy.com/v3/public/oauth/token"

# Scopes needed for the Etsy pipeline (Phase 6)
SCOPES = " ".join([
    "listings_w",   # create + update listings
    "listings_r",   # read listings
    "shops_r",      # read shop info (needed for get_shop_listings)
])

ENV_PATH = Path(__file__).parent.parent / ".ENV"

# ─── PKCE helpers ─────────────────────────────────────────────────────────────

def _generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge)."""
    verifier  = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ─── Local callback server ────────────────────────────────────────────────────

_callback_result: dict = {}
_server_ready    = threading.Event()

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/callback":
            code  = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]

            if error:
                _callback_result["error"] = error
                body = b"<h2>Authorization denied.</h2><p>You can close this tab.</p>"
            elif code:
                _callback_result["code"]  = code
                _callback_result["state"] = state
                body = b"<h2>Authorization granted!</h2><p>Return to your terminal. You can close this tab.</p>"
            else:
                _callback_result["error"] = "no_code"
                body = b"<h2>Unexpected response.</h2><p>No code received.</p>"

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        # Signal the main thread to stop waiting
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *args):
        pass  # Suppress access logs


def _start_server(port: int = 3003):
    server = http.server.HTTPServer(("localhost", port), _CallbackHandler)
    _server_ready.set()
    server.serve_forever()


# ─── Token exchange ───────────────────────────────────────────────────────────

def _exchange_code(code: str, verifier: str) -> dict:
    """POST the code + verifier to get access_token + refresh_token."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "authorization_code",
            "client_id":     API_KEY,
            "redirect_uri":  REDIRECT_URI,
            "code":          code,
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    return resp.json()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not API_KEY:
        print("ERROR: ETSY_API_KEY not set in .env — add your Keystring first.")
        sys.exit(1)

    print("\nEtsy OAuth2 — token exchange")
    print("=" * 50)

    # PKCE
    verifier, challenge = _generate_pkce()
    state = secrets.token_hex(16)

    # Build auth URL
    params = urllib.parse.urlencode({
        "response_type":         "code",
        "client_id":             API_KEY,
        "redirect_uri":          REDIRECT_URI,
        "scope":                 SCOPES,
        "state":                 state,
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"{AUTH_URL}?{params}"

    # Start local server in background
    t = threading.Thread(target=_start_server, daemon=True)
    t.start()
    _server_ready.wait()

    print(f"\nOpening browser for Etsy authorisation...")
    print(f"If it doesn't open automatically, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for callback on http://localhost:3003/callback ...")
    t.join(timeout=120)

    if not _callback_result:
        print("\nERROR: Timed out waiting for callback (2 min). Try again.")
        sys.exit(1)

    if "error" in _callback_result:
        print(f"\nERROR: Etsy returned an error: {_callback_result['error']}")
        sys.exit(1)

    # Verify state
    if _callback_result.get("state") != state:
        print("\nERROR: State mismatch — possible CSRF. Do not use these tokens.")
        sys.exit(1)

    code = _callback_result["code"]
    print(f"\nAuthorisation code received. Exchanging for tokens...")

    token_data = _exchange_code(code, verifier)

    if "error" in token_data:
        print(f"\nERROR: Token exchange failed: {token_data}")
        sys.exit(1)

    access_token  = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in    = token_data.get("expires_in", "?")
    token_type    = token_data.get("token_type", "Bearer")

    print("\n" + "=" * 50)
    print("SUCCESS — tokens received")
    print("=" * 50)
    print(f"\nAccess token expires in: {expires_in}s (~{int(expires_in)//3600}h)")
    print(f"\nETSY_ACCESS_TOKEN={access_token}")
    print(f"ETSY_REFRESH_TOKEN={refresh_token}")

    # Offer to write to .env automatically
    print()
    answer = input("Write tokens to .env automatically? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        set_key(str(ENV_PATH), "ETSY_ACCESS_TOKEN",  access_token,  quote_mode="never")
        set_key(str(ENV_PATH), "ETSY_REFRESH_TOKEN", refresh_token, quote_mode="never")
        print(f"\nTokens written to {ENV_PATH}")
        print("You can now run: python scripts/run_phase6.py --slug <your-slug>")
    else:
        print("\nCopy the tokens above into your .env file manually.")

    print()


if __name__ == "__main__":
    main()
