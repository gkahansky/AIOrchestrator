"""
Etsy OAuth2 — one-time token exchange.

Two modes:

  AUTO (default) — starts a local server to catch the redirect automatically.
    Requires registering http://localhost:3003/callback in your Etsy app.

  MANUAL (--manual) — you copy the redirect URL from the browser address bar.
    Use this if your Etsy app only has a "Website URL" field, or if you cannot
    register localhost as a callback. Set ETSY_WEBSITE_URL in .env to whatever
    website URL is registered on your app, or pass --redirect-uri.

Usage:
    python scripts/etsy_oauth.py                          # auto mode
    python scripts/etsy_oauth.py --manual                 # manual copy-paste mode
    python scripts/etsy_oauth.py --manual --redirect-uri https://yoursite.com
"""

import argparse
import base64
import hashlib
import http.server
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

API_KEY           = os.environ.get("ETSY_API_KEY", "")
AUTH_URL          = "https://www.etsy.com/oauth/connect"
TOKEN_URL         = "https://api.etsy.com/v3/public/oauth/token"
DEFAULT_LOCAL_URI = "http://localhost:3003/callback"

SCOPES = " ".join([
    "listings_w",
    "listings_r",
    "shops_r",
])

ENV_PATH = Path(__file__).parent.parent / ".ENV"


# ─── PKCE ─────────────────────────────────────────────────────────────────────

def _generate_pkce() -> tuple[str, str]:
    verifier  = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ─── Local callback server (auto mode) ────────────────────────────────────────

_callback_result: dict = {}
_server_ready = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/callback":
            code  = params.get("code",  [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]
            if error:
                _callback_result["error"] = error
                body = b"<h2>Authorization denied.</h2><p>You can close this tab.</p>"
            elif code:
                _callback_result["code"]  = code
                _callback_result["state"] = state
                body = b"<h2>Done! Return to your terminal.</h2><p>You can close this tab.</p>"
            else:
                _callback_result["error"] = "no_code"
                body = b"<h2>Unexpected response - no code.</h2>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *args):
        pass


def _start_server(port: int = 3003):
    server = http.server.HTTPServer(("localhost", port), _CallbackHandler)
    _server_ready.set()
    server.serve_forever()


# ─── Token exchange ───────────────────────────────────────────────────────────

def _exchange_code(code: str, verifier: str, redirect_uri: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "authorization_code",
            "client_id":     API_KEY,
            "redirect_uri":  redirect_uri,
            "code":          code,
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    return resp.json()


def _finish(token_data: dict) -> None:
    if "error" in token_data:
        print(f"\nERROR: Token exchange failed: {token_data}")
        sys.exit(1)

    access_token  = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in    = token_data.get("expires_in", 3600)

    print("\n" + "=" * 50)
    print("SUCCESS")
    print("=" * 50)
    print(f"\nAccess token expires in: {int(expires_in)//3600}h")
    print(f"\nETSY_ACCESS_TOKEN={access_token}")
    print(f"ETSY_REFRESH_TOKEN={refresh_token}")

    print()
    answer = input("Write tokens to .env automatically? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        set_key(str(ENV_PATH), "ETSY_ACCESS_TOKEN",  access_token,  quote_mode="never")
        set_key(str(ENV_PATH), "ETSY_REFRESH_TOKEN", refresh_token, quote_mode="never")
        print(f"\nTokens written to .env")
        print("You can now run: python scripts/run_phase6.py --slug <your-slug>")
    else:
        print("\nCopy the two lines above into your .env file.")
    print()


# ─── Modes ────────────────────────────────────────────────────────────────────

def run_auto(verifier: str, auth_url: str) -> None:
    """Auto mode: local server catches the redirect."""
    redirect_uri = DEFAULT_LOCAL_URI

    print(f"\nThis requires the following URL registered in your Etsy app:")
    print(f"\n    {redirect_uri}\n")
    print("  etsy.com/developers/your-apps → your app → Edit → Callback URLs")
    print("  (This is a separate field from Website URL)\n")
    input("Press Enter once it's registered and saved...")

    t = threading.Thread(target=_start_server, daemon=True)
    t.start()
    _server_ready.wait()

    print(f"\nOpening browser...")
    print(f"If it doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)
    print("Waiting for callback... (2 min timeout)")
    t.join(timeout=120)

    if not _callback_result:
        print("\nERROR: Timed out. Try --manual mode instead.")
        sys.exit(1)
    if "error" in _callback_result:
        print(f"\nERROR: {_callback_result['error']}")
        sys.exit(1)

    token_data = _exchange_code(_callback_result["code"], verifier, redirect_uri)
    _finish(token_data)


def run_manual(verifier: str, auth_url: str, redirect_uri: str, state: str) -> None:
    """
    Manual mode: user clicks Allow on Etsy, Etsy redirects to their registered URL,
    browser shows an error page — that's fine. They copy the URL from the address bar.
    """
    print()
    print("=" * 60)
    print("STEP 1 — Make sure you are logged into Etsy in your browser")
    print("         Go to etsy.com and log in first if you haven't.")
    print("=" * 60)
    input("\nPress Enter when you are logged into Etsy...")

    print()
    print("=" * 60)
    print("STEP 2 — Open the authorisation URL below in your browser.")
    print("         The script will try to open it automatically.")
    print("=" * 60)
    print(f"\n  {auth_url}\n")
    webbrowser.open(auth_url)

    print("You should now see an Etsy page saying:")
    print('  "[Your app name] would like to access your Etsy account"')
    print("with an ALLOW ACCESS button.")
    print()
    print("If you see a login page instead — log in, then the consent page will appear.")
    print("If you see 'redirect URL not permitted' — the wrong website URL was entered.")
    print()
    input("Press Enter once you can see the ALLOW ACCESS button on Etsy...")

    print()
    print("=" * 60)
    print("STEP 3 — Click ALLOW ACCESS on the Etsy page.")
    print("=" * 60)
    print()
    print(f"Etsy will redirect your browser to: {redirect_uri}")
    print("That page will probably show an error or 404 — THAT IS FINE.")
    print()
    print("IMPORTANT: Look at your browser ADDRESS BAR after the redirect.")
    print(f"The URL will start with:  {redirect_uri}")
    print(f"and will contain:        ?code=XXXXXXXXXX&state=XXXXXXXXXX")
    print()
    print("DO NOT paste the etsy.com URL — paste the URL starting with your website.")
    print()

    raw = input("Paste the full URL from your browser address bar: ").strip()

    if "etsy.com" in raw:
        print()
        print("ERROR: That is the Etsy authorization URL — not the redirect URL.")
        print("       You need to paste the URL your browser shows AFTER clicking Allow Access.")
        print(f"       It should start with: {redirect_uri}")
        sys.exit(1)

    parsed = urllib.parse.urlparse(raw)
    params = urllib.parse.parse_qs(parsed.query)

    code      = params.get("code",  [None])[0]
    error     = params.get("error", [None])[0]
    got_state = params.get("state", [None])[0]

    if error:
        print(f"\nERROR: Etsy returned: {error}")
        sys.exit(1)
    if not code:
        print("\nERROR: No 'code' found in the URL.")
        print(f"       The URL should contain ?code=XXXX and start with {redirect_uri}")
        sys.exit(1)
    if got_state != state:
        print("\nERROR: State mismatch. Start over — run the script again.")
        sys.exit(1)

    print("\nExchanging code for tokens...")
    token_data = _exchange_code(code, verifier, redirect_uri)
    _finish(token_data)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manual",       action="store_true",
                        help="Copy-paste mode — no localhost server needed")
    parser.add_argument("--redirect-uri", default=None,
                        help="Override redirect URI (manual mode only)")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: ETSY_API_KEY not set in .env — add your Keystring first.")
        sys.exit(1)

    verifier, challenge = _generate_pkce()
    state = secrets.token_hex(16)

    if args.manual:
        redirect_uri = (
            args.redirect_uri
            or os.environ.get("ETSY_WEBSITE_URL", "")
        )
        if not redirect_uri:
            redirect_uri = input(
                "Enter the website URL registered on your Etsy app\n"
                "(e.g. https://yoursite.com): "
            ).strip()

        params = urllib.parse.urlencode({
            "response_type":         "code",
            "client_id":             API_KEY,
            "redirect_uri":          redirect_uri,
            "scope":                 SCOPES,
            "state":                 state,
            "code_challenge":        challenge,
            "code_challenge_method": "S256",
        })
        auth_url = f"{AUTH_URL}?{params}"
        run_manual(verifier, auth_url, redirect_uri, state)

    else:
        redirect_uri = DEFAULT_LOCAL_URI
        params = urllib.parse.urlencode({
            "response_type":         "code",
            "client_id":             API_KEY,
            "redirect_uri":          redirect_uri,
            "scope":                 SCOPES,
            "state":                 state,
            "code_challenge":        challenge,
            "code_challenge_method": "S256",
        })
        auth_url = f"{AUTH_URL}?{params}"
        run_auto(verifier, auth_url)


if __name__ == "__main__":
    main()
