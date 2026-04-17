"""
Tool wrapper: JWT security analysis (pure Python — no binary required)
Phase 4 — Professional and Agency tiers.

Probes the target and common auth endpoint paths for JWT tokens in Set-Cookie
headers, response bodies, and Authorization headers. For each JWT found, checks:
  - alg:none / algorithm confusion
  - HS256/HS512 with abnormally short signature (likely weak/empty secret)
  - Missing exp claim (token never expires)
  - Already expired token still being served
  - Sensitive data in plaintext payload (password, secret, api_key, …)

Does NOT attempt secret brute-force or active forgery — analysis only.
"""

from __future__ import annotations

import base64
import json
import re
import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]*")

# Paths to probe for JWT tokens — ordered from most to least likely
_AUTH_PATHS = [
    "",
    "/",
    "/api",
    "/api/auth",
    "/api/token",
    "/api/login",
    "/api/me",
    "/api/user",
    "/api/v1/auth",
    "/api/v1/me",
    "/auth/token",
    "/login",
    "/api/refresh",
]

# Payload claim names that should never appear in a client-readable JWT
_SENSITIVE_CLAIMS = frozenset({
    "password", "passwd", "secret", "api_key", "apikey",
    "private_key", "access_token", "refresh_token", "client_secret",
    "encryption_key",
})


def tool_available() -> bool:
    return True  # pure Python — always available


def run_jwt_scan(
    target_url: str,
    scope_domain: str,
    timeout: int = 60,
) -> list[dict]:
    """
    Scan the target for JWT tokens and audit their security properties.

    Args:
        target_url:   Primary target URL.
        scope_domain: Validated scope domain — only in-scope URLs are probed.
        timeout:      Total scan timeout in seconds (shared across all probes).

    Returns:
        List of normalised finding dicts.
    """
    from aiplatform.skills.security.scope_validator import is_in_scope

    seen_tokens: set[str] = set()
    findings: list[dict] = []

    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (compatible; EchoForge-SecurityAudit/1.0)"
    )

    base = target_url.rstrip("/")
    per_req = max(6, timeout // len(_AUTH_PATHS))

    for path in _AUTH_PATHS:
        url = base + path if path else base
        if not is_in_scope(url, scope_domain):
            continue
        try:
            resp = session.get(
                url, timeout=per_req, allow_redirects=True, verify=False
            )
        except Exception:
            continue

        _extract_and_analyse(resp, url, "response_body", seen_tokens, findings)

        for cookie in resp.cookies:
            for match in _JWT_RE.findall(cookie.value or ""):
                if match not in seen_tokens:
                    seen_tokens.add(match)
                    findings.extend(
                        _analyse_jwt(match, url, f"cookie:{cookie.name}")
                    )

        for hdr, val in resp.headers.items():
            for match in _JWT_RE.findall(val):
                if match not in seen_tokens:
                    seen_tokens.add(match)
                    findings.extend(
                        _analyse_jwt(match, url, f"header:{hdr}")
                    )

    return findings


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_and_analyse(
    resp: requests.Response,
    url: str,
    source: str,
    seen: set[str],
    findings: list[dict],
) -> None:
    for match in _JWT_RE.findall(resp.text):
        if match not in seen:
            seen.add(match)
            findings.extend(_analyse_jwt(match, url, source))


def _b64_decode(part: str) -> dict:
    padded = part + "=" * (-len(part) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return {}


def _analyse_jwt(token: str, url: str, source: str) -> list[dict]:
    parts = token.split(".")
    if len(parts) != 3:
        return []

    header = _b64_decode(parts[0])
    payload = _b64_decode(parts[1])
    if not header or not payload:
        return []

    alg = str(header.get("alg", "")).upper()
    out: list[dict] = []

    # 1. alg:none — signature bypass
    if alg in ("NONE", ""):
        out.append({
            "tool": "jwt_scan",
            "title": "JWT 'alg:none' — signature verification bypassed",
            "severity": "Critical",
            "category": "Authentication",
            "description": (
                "A JWT token uses the 'none' algorithm, meaning the server "
                "does not verify the token's signature. An attacker can craft "
                "arbitrary tokens with any claims (e.g. admin=true, elevated roles) "
                "without knowing the signing secret."
            ),
            "url": url,
            "evidence": (
                f"Token found in {source}. "
                f"Header alg: {header.get('alg', '(empty)')!r}"
            ),
            "cvss_estimate": 9.8,
            "fix": (
                "Explicitly reject any JWT where alg is 'none' or missing. "
                "Whitelist allowed algorithms server-side (e.g. RS256). "
                "Use a well-maintained JWT library — never implement JWT verification manually."
            ),
            "tags": ["jwt", "auth", "alg-none", "confirmed"],
        })

    # 2. Symmetric algorithm with suspiciously short signature
    if alg in ("HS256", "HS384", "HS512") and len(parts[2]) < 24:
        out.append({
            "tool": "jwt_scan",
            "title": f"JWT {alg} — abnormally short signature (possible empty/weak secret)",
            "severity": "High",
            "category": "Authentication",
            "description": (
                f"A JWT using {alg} has an unusually short signature ({len(parts[2])} chars). "
                "This suggests the token was signed with an empty, null, or trivially weak "
                "secret. An attacker can brute-force the secret offline and forge tokens."
            ),
            "url": url,
            "evidence": (
                f"Token found in {source}. "
                f"Signature length: {len(parts[2])} chars (expected ≥43 for HS256)."
            ),
            "cvss_estimate": 8.5,
            "fix": (
                "Use a cryptographically random secret of at least 256 bits. "
                "Prefer RS256/ES256 (asymmetric) to eliminate shared-secret risk. "
                "Rotate the secret immediately if a weak one is confirmed."
            ),
            "tags": ["jwt", "auth", "weak-secret", "confirmed"],
        })

    # 3. Missing exp claim
    if "exp" not in payload:
        out.append({
            "tool": "jwt_scan",
            "title": "JWT missing 'exp' — token never expires",
            "severity": "Medium",
            "category": "Session Management",
            "description": (
                "The JWT does not include an 'exp' (expiration) claim. "
                "This token remains valid indefinitely. A stolen token cannot be "
                "invalidated without rotating the signing key, which logs out all users."
            ),
            "url": url,
            "evidence": (
                f"Token found in {source}. "
                f"Payload keys: {list(payload.keys())}"
            ),
            "cvss_estimate": 5.0,
            "fix": (
                "Always set an 'exp' claim. "
                "Use short-lived access tokens (15–60 min) paired with refresh tokens. "
                "Implement server-side revocation for logout and security events."
            ),
            "tags": ["jwt", "session", "no-expiry"],
        })

    # 4. Already-expired token still being issued
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time() - 60:
        out.append({
            "tool": "jwt_scan",
            "title": "Expired JWT token served in response",
            "severity": "Low",
            "category": "Session Management",
            "description": (
                "The server returned a JWT token that is already past its expiry date. "
                "This may indicate that expiry enforcement is not implemented server-side, "
                "or that stale tokens are not being cleaned up."
            ),
            "url": url,
            "evidence": (
                f"Token found in {source}. "
                f"exp={int(exp)}, now={int(time.time())} "
                f"(expired {int(time.time() - exp)}s ago)"
            ),
            "cvss_estimate": 2.5,
            "fix": (
                "Reject expired tokens server-side regardless of their signature validity. "
                "Do not issue tokens that are already expired."
            ),
            "tags": ["jwt", "session", "expired-token"],
        })

    # 5. Sensitive claims in plaintext payload
    exposed = [k for k in payload if k.lower() in _SENSITIVE_CLAIMS]
    if exposed:
        out.append({
            "tool": "jwt_scan",
            "title": f"Sensitive data in JWT payload: {exposed}",
            "severity": "Medium",
            "category": "Information Disclosure",
            "description": (
                "The JWT payload contains claims that should not be stored in a "
                "client-readable token. JWT payloads are base64-encoded — not encrypted. "
                "Any client, proxy, or log that captures the token can read these values."
            ),
            "url": url,
            "evidence": (
                f"Token found in {source}. "
                f"Sensitive claim keys: {exposed}"
            ),
            "cvss_estimate": 4.0,
            "fix": (
                "Remove sensitive values from JWT payloads. "
                "Store secrets server-side and reference them by opaque ID. "
                "If sensitive data must be transmitted, use JWE (encrypted JWT)."
            ),
            "tags": ["jwt", "information-disclosure"],
        })

    return out
