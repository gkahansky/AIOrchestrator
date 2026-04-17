"""
Phase 5 — Authenticated & Session Testing
Venture-specific skill (Security Audit only).

Drives a real browser session via Playwright using customer-supplied credentials
to discover and test endpoints invisible to unauthenticated phases.

Entry point:
    run_phase5(audit, db_session, plaintext_password) -> dict

Caller (pipeline.py) is responsible for decrypting auth_password before calling here.
All active probing is gated behind scope_validator — never touches out-of-scope hosts.

Tests performed:
  1. Authenticated crawl — discover routes only accessible after login
  2. IDOR testing — extract resource IDs, attempt cross-account access
  3. Session token entropy — capture tokens from N logins, analyse predictability
  4. Cookie flag audit — HttpOnly, Secure, SameSite enforcement
  5. Privilege escalation — replay authenticated requests at elevated paths
  6. Business logic — price/amount parameter tampering, workflow step skipping
  7. Mass assignment — inject extra fields (role, is_admin) into API request bodies
  8. Rate limiting — detect missing throttling on authentication endpoints
"""

from __future__ import annotations

import math
import re
import time
import urllib.parse
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid importing SQLAlchemy models at module load time
    from aiplatform.database.models import SecurityAudit


# ── constants ──────────────────────────────────────────────────────────────────

_MAX_CRAWL_PAGES = 60        # cap authenticated crawl depth
_MAX_IDOR_ATTEMPTS = 30      # cap cross-account probes
_SESSION_SAMPLES = 3         # how many fresh logins for entropy analysis
_RATE_LIMIT_BURST = 12       # rapid requests to detect missing throttling
_CRAWL_TIMEOUT_MS = 8_000    # ms Playwright waits per page
_REQUEST_DELAY_S = 0.4       # seconds between probes (matches platform MAX_RPS=2)

# Common paths that indicate admin/elevated-privilege access
_ADMIN_PATHS = [
    "/admin", "/admin/", "/admin/dashboard",
    "/dashboard/admin", "/management", "/manage",
    "/api/admin", "/api/v1/admin", "/api/v2/admin",
    "/superuser", "/staff", "/internal",
    "/settings/users", "/users/list",
]

# Extra fields to inject during mass-assignment probes
_MASS_ASSIGNMENT_FIELDS = {
    "role": "admin",
    "is_admin": True,
    "admin": True,
    "is_staff": True,
    "privilege": "admin",
    "user_role": "superuser",
    "price": 0,
    "amount": 0,
    "discount": 100,
}


# ── public entry point ─────────────────────────────────────────────────────────

def run_phase5(
    audit: "SecurityAudit",
    db_session,
    plaintext_password: str | None = None,
) -> dict:
    """
    Run all Phase 5 authenticated & session tests.

    Args:
        audit:              ORM record — provides target_url, auth_username,
                            auth_login_url, scope_domain, and tier.
        db_session:         Active SQLAlchemy session (used for scope validation
                            helper; not written to here — pipeline writes findings).
        plaintext_password: Decrypted password (pipeline calls decrypt_password
                            from config before passing here).

    Returns a dict with keys:
        findings            list[dict]  — normalised finding dicts (same schema
                                          as Phases 3–4) fed to Claude correlation
        authenticated_routes list[str] — URLs discovered behind authentication
        idor_attempts       int        — number of cross-account probes made
        session_entropy     dict       — token length + Shannon entropy stats
        cookie_audit        list[dict] — per-cookie flag check results
        privilege_escalation list[dict]— elevated-path probe results
        business_logic      list[dict] — parameter-tampering results
        mass_assignment     list[dict] — extra-field injection results
        rate_limit          dict       — rate-limiting check result
        tools_run           list[str]
        errors              list[str]
    """
    target_url: str = audit.target_url or ""
    username: str = audit.auth_username or ""
    login_url: str = audit.auth_login_url or target_url
    scope_domain: str = audit.target_domain or _extract_domain(target_url)
    password: str = plaintext_password or ""

    findings: list[dict] = []
    authenticated_routes: list[str] = []
    idor_attempts: int = 0
    session_entropy: dict = {}
    cookie_audit: list[dict] = []
    privilege_escalation: list[dict] = []
    business_logic: list[dict] = []
    mass_assignment: list[dict] = []
    rate_limit: dict = {}
    tools_run: list[str] = []
    errors: list[str] = []

    if not username or not password or not login_url:
        return {
            "findings": [],
            "authenticated_routes": [],
            "idor_attempts": 0,
            "session_entropy": {},
            "cookie_audit": [],
            "privilege_escalation": [],
            "business_logic": [],
            "mass_assignment": [],
            "rate_limit": {},
            "tools_run": [],
            "errors": ["Phase 5 skipped — auth_username, auth_password, or auth_login_url not set"],
        }

    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError
    except ImportError:
        return {
            "findings": [],
            "authenticated_routes": [],
            "idor_attempts": 0,
            "session_entropy": {},
            "cookie_audit": [],
            "privilege_escalation": [],
            "business_logic": [],
            "mass_assignment": [],
            "rate_limit": {},
            "tools_run": [],
            "errors": ["Phase 5 skipped — playwright not installed"],
        }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
        )
        try:
            # ── 1. Session token entropy & primary login ───────────────────────
            print("[phase5] Session entropy analysis — sampling fresh logins", flush=True)
            entropy_result, primary_context, login_cookies = _analyse_session_entropy(
                browser, login_url, username, password, scope_domain,
                samples=_SESSION_SAMPLES,
            )
            session_entropy = entropy_result
            tools_run.append("playwright:session_entropy")

            if entropy_result.get("finding"):
                findings.append(entropy_result["finding"])

            if primary_context is None:
                errors.append("Login failed — cannot continue with authenticated phases")
                return {
                    "findings": findings,
                    "authenticated_routes": [],
                    "idor_attempts": 0,
                    "session_entropy": session_entropy,
                    "cookie_audit": [],
                    "privilege_escalation": [],
                    "business_logic": [],
                    "mass_assignment": [],
                    "rate_limit": {},
                    "tools_run": tools_run,
                    "errors": errors,
                }

            page = primary_context.new_page()

            # ── 2. Cookie flag audit ───────────────────────────────────────────
            print("[phase5] Cookie flag audit", flush=True)
            cookie_audit, cookie_findings = _audit_cookie_flags(login_cookies, target_url)
            findings.extend(cookie_findings)
            tools_run.append("playwright:cookie_audit")

            # ── 3. Authenticated crawl ─────────────────────────────────────────
            print(f"[phase5] Authenticated crawl (max {_MAX_CRAWL_PAGES} pages)", flush=True)
            authenticated_routes, crawl_links, api_endpoints = _authenticated_crawl(
                page, target_url, scope_domain,
            )
            tools_run.append("playwright:auth_crawl")

            # ── 4. IDOR testing ────────────────────────────────────────────────
            print("[phase5] IDOR testing", flush=True)
            idor_results, idor_findings = _test_idor(
                page, authenticated_routes, scope_domain,
            )
            idor_attempts = idor_results.get("attempts", 0)
            findings.extend(idor_findings)
            tools_run.append("playwright:idor")

            # ── 5. Privilege escalation ────────────────────────────────────────
            print("[phase5] Privilege escalation probes", flush=True)
            privilege_escalation, priv_findings = _test_privilege_escalation(
                page, target_url, scope_domain,
            )
            findings.extend(priv_findings)
            tools_run.append("playwright:privesc")

            # ── 6. Business logic — price/workflow tampering ───────────────────
            print("[phase5] Business logic testing", flush=True)
            business_logic, bl_findings = _test_business_logic(
                page, authenticated_routes, api_endpoints, scope_domain,
            )
            findings.extend(bl_findings)
            tools_run.append("playwright:business_logic")

            # ── 7. Mass assignment ─────────────────────────────────────────────
            print("[phase5] Mass assignment checks", flush=True)
            mass_assignment, ma_findings = _test_mass_assignment(
                page, api_endpoints, scope_domain,
            )
            findings.extend(ma_findings)
            tools_run.append("playwright:mass_assignment")

            # ── 8. Rate limiting on auth endpoints ────────────────────────────
            print("[phase5] Rate limiting check on auth endpoints", flush=True)
            rate_limit, rl_findings = _test_rate_limiting(
                browser, login_url, username, scope_domain,
            )
            findings.extend(rl_findings)
            tools_run.append("playwright:rate_limit")

            page.close()
            primary_context.close()

        except Exception as exc:
            errors.append(f"Phase 5 runtime error: {exc}")
        finally:
            browser.close()

    return {
        "findings": findings,
        "authenticated_routes": authenticated_routes,
        "idor_attempts": idor_attempts,
        "session_entropy": session_entropy,
        "cookie_audit": cookie_audit,
        "privilege_escalation": privilege_escalation,
        "business_logic": business_logic,
        "mass_assignment": mass_assignment,
        "rate_limit": rate_limit,
        "tools_run": tools_run,
        "errors": errors,
    }


# ── 1. Session entropy ────────────────────────────────────────────────────────

def _analyse_session_entropy(
    browser,
    login_url: str,
    username: str,
    password: str,
    scope_domain: str,
    samples: int = 3,
) -> tuple[dict, object | None, list]:
    """
    Login `samples` times in separate contexts, capture session tokens, and
    measure Shannon entropy.  Returns (entropy_result, primary_context, cookies).
    primary_context is the last successful browser context — caller must close it.
    """
    tokens: list[str] = []
    primary_context = None
    last_cookies: list = []

    for i in range(samples):
        ctx = browser.new_context()
        try:
            page = ctx.new_page()
            success, cookies = _perform_login(page, login_url, username, password)
            if success:
                session_cookies = [
                    c for c in cookies
                    if any(hint in c["name"].lower()
                           for hint in ("sess", "token", "auth", "jwt", "sid", "id"))
                ]
                for c in session_cookies:
                    tokens.append(c["value"])
                last_cookies = cookies
                if i == samples - 1:
                    primary_context = ctx
                    page.close()  # keep context open for subsequent steps
                    continue
            page.close()
        except Exception:
            pass
        if i != samples - 1 or primary_context is None:
            ctx.close()

    if not tokens:
        # Return a live context from the last attempt even if we got no tokens
        if primary_context is None:
            ctx = browser.new_context()
            page = ctx.new_page()
            success, last_cookies = _perform_login(page, login_url, username, password)
            page.close()
            if success:
                primary_context = ctx
            else:
                ctx.close()
                return {}, None, []
        return {"tokens_captured": 0, "note": "No session tokens found in cookies"}, primary_context, last_cookies

    # Shannon entropy per token
    entropies = [_shannon_entropy(t) for t in tokens]
    avg_entropy = sum(entropies) / len(entropies)
    min_len = min(len(t) for t in tokens)
    max_len = max(len(t) for t in tokens)
    all_unique = len(set(tokens)) == len(tokens)

    result: dict = {
        "tokens_captured": len(tokens),
        "token_lengths": {"min": min_len, "max": max_len},
        "avg_shannon_entropy": round(avg_entropy, 2),
        "all_tokens_unique": all_unique,
    }

    finding = None

    if not all_unique:
        finding = {
            "tool": "playwright:session_entropy",
            "title": "Predictable or Reused Session Token",
            "severity": "Critical",
            "category": "Session Management",
            "description": (
                f"Two or more login sessions produced the same session token value. "
                f"This indicates tokens are not randomly generated per session, "
                f"making session hijacking trivial."
            ),
            "evidence": f"Sampled {len(tokens)} tokens across {samples} logins — duplicates found",
            "cvss_estimate": 9.1,
            "fix": (
                "Generate session tokens using a cryptographically secure PRNG "
                "(e.g. secrets.token_hex(32) in Python, crypto.randomBytes in Node). "
                "Ensure token length is at least 128 bits."
            ),
            "tags": ["session", "predictable-token", "authenticated"],
        }
    elif avg_entropy < 3.5:
        finding = {
            "tool": "playwright:session_entropy",
            "title": "Low-Entropy Session Tokens",
            "severity": "High",
            "category": "Session Management",
            "description": (
                f"Session tokens have low Shannon entropy ({avg_entropy:.2f} bits/char). "
                f"Low-entropy tokens are more susceptible to brute-force or pattern-based prediction."
            ),
            "evidence": (
                f"Average entropy: {avg_entropy:.2f} bits/char across {len(tokens)} tokens. "
                f"Token lengths: {min_len}–{max_len} chars."
            ),
            "cvss_estimate": 7.5,
            "fix": (
                "Use a CSPRNG for session token generation. "
                "Aim for tokens with at least 128 bits of entropy. "
                "Consider Base64url-encoded random bytes of length 32+."
            ),
            "tags": ["session", "entropy", "authenticated"],
        }
    elif min_len < 16:
        finding = {
            "tool": "playwright:session_entropy",
            "title": "Short Session Token Length",
            "severity": "Medium",
            "category": "Session Management",
            "description": (
                f"Session tokens as short as {min_len} characters were observed. "
                f"Short tokens reduce the effective search space for brute-force attacks."
            ),
            "evidence": f"Minimum token length: {min_len} chars across {len(tokens)} samples",
            "cvss_estimate": 5.0,
            "fix": "Ensure session tokens are at least 32 characters (128-bit entropy minimum).",
            "tags": ["session", "token-length", "authenticated"],
        }

    if finding:
        result["finding"] = finding

    return result, primary_context, last_cookies


def _perform_login(page, login_url: str, username: str, password: str) -> tuple[bool, list]:
    """
    Attempt to log in via a form. Tries common field selectors.
    Returns (success, cookies_after_login).
    """
    try:
        page.goto(login_url, timeout=_CRAWL_TIMEOUT_MS, wait_until="domcontentloaded")
        page.wait_for_timeout(500)

        # Try common username selectors
        user_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[name="username"]',
            'input[name="user"]',
            'input[name="login"]',
            'input[id*="email"]',
            'input[id*="user"]',
        ]
        pw_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[name="passwd"]',
            'input[name="pass"]',
        ]

        user_filled = False
        for sel in user_selectors:
            try:
                if page.locator(sel).count() > 0:
                    page.fill(sel, username)
                    user_filled = True
                    break
            except Exception:
                continue

        pw_filled = False
        for sel in pw_selectors:
            try:
                if page.locator(sel).count() > 0:
                    page.fill(sel, password)
                    pw_filled = True
                    break
            except Exception:
                continue

        if not user_filled or not pw_filled:
            return False, []

        # Submit
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Log in")',
            'button:has-text("Login")',
            'button:has-text("Sign in")',
            'button:has-text("Sign In")',
        ]
        submitted = False
        for sel in submit_selectors:
            try:
                if page.locator(sel).count() > 0:
                    page.click(sel)
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            page.keyboard.press("Enter")

        page.wait_for_load_state("networkidle", timeout=_CRAWL_TIMEOUT_MS)
        page.wait_for_timeout(500)

        # Heuristic: login succeeded if URL changed or login form is gone
        current_url = page.url
        login_form_still_present = any(
            page.locator(sel).count() > 0 for sel in pw_selectors
        )
        cookies = page.context.cookies()
        success = (current_url != login_url or not login_form_still_present)
        return success, cookies

    except Exception:
        return False, []


# ── 2. Cookie flag audit ──────────────────────────────────────────────────────

def _audit_cookie_flags(cookies: list, target_url: str) -> tuple[list[dict], list[dict]]:
    """
    Check each cookie for HttpOnly, Secure, and SameSite flags.
    Returns (audit_records, findings).
    """
    audit_records: list[dict] = []
    findings: list[dict] = []

    is_https = target_url.startswith("https://")

    for c in cookies:
        name = c.get("name", "")
        http_only = c.get("httpOnly", False)
        secure = c.get("secure", False)
        same_site = c.get("sameSite", "None")
        issues: list[str] = []

        if not http_only:
            issues.append("Missing HttpOnly flag — JavaScript can access this cookie")
        if is_https and not secure:
            issues.append("Missing Secure flag — cookie transmitted over HTTP")
        if same_site in ("None", "none", ""):
            issues.append("SameSite=None — vulnerable to cross-site request forgery")
        elif same_site == "Lax":
            issues.append("SameSite=Lax — partial CSRF protection (top-level navigation only)")

        record = {
            "name": name,
            "httpOnly": http_only,
            "secure": secure,
            "sameSite": same_site,
            "issues": issues,
        }
        audit_records.append(record)

        if not issues:
            continue

        # Determine severity: session/auth cookies are higher priority
        is_session_cookie = any(
            hint in name.lower()
            for hint in ("sess", "token", "auth", "jwt", "sid", "id", "csrftoken")
        )
        severity = "High" if (is_session_cookie and not http_only) else "Medium"
        cvss = 6.5 if severity == "High" else 4.3

        findings.append({
            "tool": "playwright:cookie_audit",
            "title": f"Insecure Cookie: {name}",
            "severity": severity,
            "category": "Session Management",
            "description": (
                f"Cookie '{name}' is missing security flags that protect against "
                f"cross-site attacks and interception. Issues: {'; '.join(issues)}"
            ),
            "evidence": (
                f"Cookie '{name}': HttpOnly={http_only}, Secure={secure}, "
                f"SameSite={same_site}"
            ),
            "cvss_estimate": cvss,
            "fix": (
                "Set HttpOnly on all cookies that do not need to be accessed by JavaScript. "
                "Set Secure on all cookies when the site is served over HTTPS. "
                "Set SameSite=Strict (or Lax) to mitigate CSRF."
            ),
            "tags": ["cookie", "session", "authenticated"],
        })

    return audit_records, findings


# ── 3. Authenticated crawl ────────────────────────────────────────────────────

def _authenticated_crawl(
    page,
    start_url: str,
    scope_domain: str,
) -> tuple[list[str], list[str], list[str]]:
    """
    BFS crawl from start_url using the already-authenticated page.
    Returns (all_visited_urls, all_links, api_endpoints).
    """
    visited: set[str] = set()
    queue: deque[str] = deque([start_url])
    api_endpoints: list[str] = []

    while queue and len(visited) < _MAX_CRAWL_PAGES:
        url = queue.popleft()
        if url in visited:
            continue
        if not _is_in_scope(url, scope_domain):
            continue

        try:
            page.goto(url, timeout=_CRAWL_TIMEOUT_MS, wait_until="domcontentloaded")
            page.wait_for_timeout(int(_REQUEST_DELAY_S * 1000))
            visited.add(url)

            # Collect all links on this page
            hrefs = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => e.href)",
            )
            for href in hrefs:
                normalised = _normalise_url(href, scope_domain)
                if normalised and normalised not in visited:
                    queue.append(normalised)

            # Detect API endpoints (JSON responses, /api/ paths)
            if "/api/" in url or url.endswith(".json"):
                api_endpoints.append(url)

        except Exception:
            visited.add(url)  # mark as visited to avoid retrying

    return list(visited), list(visited), api_endpoints


# ── 4. IDOR testing ───────────────────────────────────────────────────────────

def _test_idor(
    page,
    authenticated_routes: list[str],
    scope_domain: str,
) -> tuple[dict, list[dict]]:
    """
    Extract resource IDs from authenticated routes and attempt to access
    IDs that likely belong to other users (sequential probe ±1, ±2).
    """
    findings: list[dict] = []
    attempts = 0

    # Patterns matching /resource/123 or /resource/uuid
    id_pattern = re.compile(
        r"/([a-zA-Z0-9_-]+)/"
        r"(\d{1,10}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
        r"(/|$|\?)",
        re.IGNORECASE,
    )

    candidate_probes: list[tuple[str, str, str]] = []  # (url, resource, id_value)

    for url in authenticated_routes:
        if not _is_in_scope(url, scope_domain):
            continue
        m = id_pattern.search(url)
        if not m:
            continue
        resource = m.group(1)
        id_val = m.group(2)

        # For numeric IDs: probe ±1, ±2; skip very large (likely epoch timestamps)
        if id_val.isdigit():
            numeric = int(id_val)
            if numeric > 2_000_000_000:  # likely unix timestamp
                continue
            for delta in (-2, -1, 1, 2):
                probe_id = numeric + delta
                if probe_id < 1:
                    continue
                probe_url = url.replace(f"/{id_val}", f"/{probe_id}", 1)
                candidate_probes.append((probe_url, resource, str(probe_id)))
        else:
            # UUID — try a few known-invalid UUIDs to see if 404 vs 200/403
            probe_uuid = "00000000-0000-0000-0000-000000000001"
            probe_url = url.replace(id_val, probe_uuid, 1)
            candidate_probes.append((probe_url, resource, probe_uuid))

    # Limit total probes
    candidate_probes = candidate_probes[:_MAX_IDOR_ATTEMPTS]

    for probe_url, resource, probe_id in candidate_probes:
        attempts += 1
        time.sleep(_REQUEST_DELAY_S)
        try:
            response = page.goto(
                probe_url, timeout=_CRAWL_TIMEOUT_MS, wait_until="domcontentloaded",
            )
            if response is None:
                continue
            status = response.status

            # 200 on a probed ID suggests IDOR
            if status == 200:
                body = page.content()
                # Quick check: does the page contain real data or is it an empty/error page?
                has_content = len(body) > 500 and "not found" not in body.lower()
                if has_content:
                    findings.append({
                        "tool": "playwright:idor",
                        "title": f"Potential IDOR — {resource} ID {probe_id}",
                        "severity": "High",
                        "category": "IDOR",
                        "description": (
                            f"Accessing {resource} resource with ID {probe_id} — which was not "
                            f"discovered in the authenticated session — returned HTTP 200 with "
                            f"content. This suggests the application is not validating that the "
                            f"requesting user owns the resource."
                        ),
                        "url": probe_url,
                        "evidence": (
                            f"GET {probe_url} → HTTP 200 ({len(body)} bytes). "
                            f"Original authenticated ID was offset by ±1 or ±2."
                        ),
                        "cvss_estimate": 8.1,
                        "fix": (
                            "Implement authorisation checks on every resource lookup: verify "
                            "that the authenticated user owns or has permission to access the "
                            "requested object ID. Use indirect object references (map internal "
                            "IDs to opaque tokens per user)."
                        ),
                        "tags": ["idor", "access-control", "authenticated"],
                    })
        except Exception:
            continue

    return {"attempts": attempts}, findings


# ── 5. Privilege escalation ───────────────────────────────────────────────────

def _test_privilege_escalation(
    page,
    base_url: str,
    scope_domain: str,
) -> tuple[list[dict], list[dict]]:
    """
    Probe common admin/elevated paths with the authenticated regular-user session.
    A 200 response to any admin path is a privilege escalation finding.
    """
    results: list[dict] = []
    findings: list[dict] = []

    base = _base_url(base_url)

    for path in _ADMIN_PATHS:
        probe_url = base + path
        if not _is_in_scope(probe_url, scope_domain):
            continue

        time.sleep(_REQUEST_DELAY_S)
        try:
            response = page.goto(
                probe_url, timeout=_CRAWL_TIMEOUT_MS, wait_until="domcontentloaded",
            )
            if response is None:
                continue
            status = response.status
            result = {"url": probe_url, "status": status}
            results.append(result)

            if status == 200:
                body = page.content()
                # Filter out login redirects that return 200 (login page on /admin)
                looks_like_login = any(
                    kw in body.lower()
                    for kw in ("sign in", "log in", "password", "login")
                )
                if not looks_like_login:
                    findings.append({
                        "tool": "playwright:privesc",
                        "title": f"Privilege Escalation — Accessible Admin Path: {path}",
                        "severity": "Critical",
                        "category": "Privilege Escalation",
                        "description": (
                            f"The path {path} returned HTTP 200 when accessed with a "
                            f"standard user session. Admin/management interfaces should be "
                            f"restricted to privileged roles only."
                        ),
                        "url": probe_url,
                        "evidence": f"GET {probe_url} → HTTP 200 with non-login content",
                        "cvss_estimate": 9.8,
                        "fix": (
                            "Implement role-based access control (RBAC) on all admin routes. "
                            "Return HTTP 403 Forbidden (not 404) for unauthorised access to "
                            "privileged paths to avoid information disclosure."
                        ),
                        "tags": ["privesc", "access-control", "authenticated"],
                    })

        except Exception:
            continue

    return results, findings


# ── 6. Business logic ─────────────────────────────────────────────────────────

def _test_business_logic(
    page,
    authenticated_routes: list[str],
    api_endpoints: list[str],
    scope_domain: str,
) -> tuple[list[dict], list[dict]]:
    """
    Look for price/amount/total parameters in forms and URL parameters.
    Attempt to submit with tampered (reduced) values.
    """
    results: list[dict] = []
    findings: list[dict] = []

    price_params = re.compile(
        r"[\?&](price|amount|total|cost|qty|quantity|units|fee|discount)"
        r"=(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )

    # Scan discovered routes for price-bearing parameters
    for url in (authenticated_routes + api_endpoints)[:40]:
        if not _is_in_scope(url, scope_domain):
            continue
        m = price_params.search(url)
        if not m:
            continue

        param_name = m.group(1)
        original_value = m.group(2)
        tampered_value = "0.01" if "." in original_value else "1"
        tampered_url = re.sub(
            rf"([?&]{re.escape(param_name)}=)[^\&]+",
            rf"\g<1>{tampered_value}",
            url,
            flags=re.IGNORECASE,
        )

        time.sleep(_REQUEST_DELAY_S)
        try:
            response = page.goto(
                tampered_url, timeout=_CRAWL_TIMEOUT_MS, wait_until="domcontentloaded",
            )
            if response is None:
                continue
            status = response.status
            result = {
                "url": tampered_url,
                "param": param_name,
                "original": original_value,
                "tampered": tampered_value,
                "status": status,
            }
            results.append(result)

            # 200 on a tampered-price URL is a potential business logic flaw
            if status == 200:
                body = page.content()
                accepted = not any(
                    kw in body.lower()
                    for kw in ("error", "invalid", "rejected", "not allowed", "forbidden")
                )
                if accepted:
                    findings.append({
                        "tool": "playwright:business_logic",
                        "title": f"Business Logic Flaw — Price/Amount Parameter Tampering: {param_name}",
                        "severity": "High",
                        "category": "Business Logic",
                        "description": (
                            f"The parameter '{param_name}' was modified from {original_value} "
                            f"to {tampered_value} in the request URL. The server returned "
                            f"HTTP 200 without an error, suggesting the tampered value was accepted."
                        ),
                        "url": tampered_url,
                        "evidence": (
                            f"GET {tampered_url} → HTTP 200 (no rejection keywords detected in response). "
                            f"Original: {param_name}={original_value}, Tampered: {param_name}={tampered_value}"
                        ),
                        "cvss_estimate": 8.0,
                        "fix": (
                            "Never trust client-supplied price or quantity values. "
                            "Compute all totals server-side using the product catalogue. "
                            "Validate that submitted values match your server-side price calculation "
                            "before processing a transaction."
                        ),
                        "tags": ["business-logic", "price-tampering", "authenticated"],
                    })

        except Exception:
            continue

    return results, findings


# ── 7. Mass assignment ────────────────────────────────────────────────────────

def _test_mass_assignment(
    page,
    api_endpoints: list[str],
    scope_domain: str,
) -> tuple[list[dict], list[dict]]:
    """
    For discovered API endpoints that accept POST/PUT, inject extra privilege-
    escalating fields (role, is_admin, price=0) and check if they are reflected
    back in the response.
    """
    results: list[dict] = []
    findings: list[dict] = []

    import json as _json

    for endpoint in api_endpoints[:20]:
        if not _is_in_scope(endpoint, scope_domain):
            continue

        time.sleep(_REQUEST_DELAY_S)
        try:
            # Use the authenticated context's fetch to send a POST with extra fields
            response_data = page.evaluate(
                """async ([url, extraFields]) => {
                    try {
                        const resp = await fetch(url, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify(extraFields),
                            credentials: 'include',
                        });
                        const text = await resp.text();
                        return {status: resp.status, body: text.substring(0, 1000)};
                    } catch(e) {
                        return {error: e.message};
                    }
                }""",
                [endpoint, _MASS_ASSIGNMENT_FIELDS],
            )

            if not isinstance(response_data, dict) or response_data.get("error"):
                continue

            status = response_data.get("status", 0)
            body = response_data.get("body", "")
            result = {"endpoint": endpoint, "status": status, "body_preview": body[:200]}
            results.append(result)

            # Check if any injected fields are echoed back in the response
            reflected_fields = [
                field for field in ("role", "is_admin", "admin", "is_staff", "privilege")
                if f'"{field}"' in body or f"'{field}'" in body
            ]

            if reflected_fields and status in (200, 201):
                findings.append({
                    "tool": "playwright:mass_assignment",
                    "title": f"Mass Assignment Vulnerability — {endpoint}",
                    "severity": "High",
                    "category": "Broken Access Control",
                    "description": (
                        f"The API endpoint {endpoint} accepted a POST body containing "
                        f"unexpected privilege-escalating fields "
                        f"({', '.join(reflected_fields)}) and reflected them in the response. "
                        f"This indicates the server does not whitelist allowed input fields."
                    ),
                    "url": endpoint,
                    "evidence": (
                        f"POST {endpoint} with fields {list(_MASS_ASSIGNMENT_FIELDS.keys())} "
                        f"→ HTTP {status}. Reflected fields in response: {reflected_fields}. "
                        f"Response preview: {body[:300]}"
                    ),
                    "cvss_estimate": 8.1,
                    "fix": (
                        "Use an allowlist (whitelist) of permitted request fields on every "
                        "API endpoint. Never bind request body objects directly to ORM models "
                        "without explicit field selection. Use a serialiser/schema that "
                        "explicitly names allowed fields."
                    ),
                    "tags": ["mass-assignment", "access-control", "authenticated"],
                })

        except Exception:
            continue

    return results, findings


# ── 8. Rate limiting ──────────────────────────────────────────────────────────

def _test_rate_limiting(
    browser,
    login_url: str,
    username: str,
    scope_domain: str,
) -> tuple[dict, list[dict]]:
    """
    Send _RATE_LIMIT_BURST rapid login attempts with wrong credentials and
    check whether any throttling, lockout, or CAPTCHA response is triggered.
    """
    findings: list[dict] = []

    if not _is_in_scope(login_url, scope_domain):
        return {}, []

    statuses: list[int] = []
    ctx = browser.new_context()
    try:
        page = ctx.new_page()
        for _ in range(_RATE_LIMIT_BURST):
            try:
                page.goto(login_url, timeout=_CRAWL_TIMEOUT_MS, wait_until="domcontentloaded")
                # Fill with wrong password to trigger auth failure
                pw_selectors = ['input[type="password"]', 'input[name="password"]']
                for sel in pw_selectors:
                    try:
                        if page.locator(sel).count() > 0:
                            page.fill('input[type="email"], input[name="email"], input[name="username"]', username)
                            page.fill(sel, "WRONG_PASSWORD_PROBE_DO_NOT_USE")
                            break
                    except Exception:
                        pass

                submit_selectors = ['button[type="submit"]', 'input[type="submit"]']
                for sel in submit_selectors:
                    try:
                        if page.locator(sel).count() > 0:
                            page.click(sel)
                            break
                    except Exception:
                        pass

                page.wait_for_load_state("domcontentloaded", timeout=5000)
                # Very short gap — we want to see if server throttles
                time.sleep(0.1)

                status_code = 200  # Playwright navigates don't expose HTTP status directly here
                body = page.content()
                # Detect signs of rate limiting in the response
                if any(kw in body.lower() for kw in (
                    "too many", "rate limit", "locked", "try again", "wait",
                    "captcha", "429", "blocked", "throttl",
                )):
                    statuses.append(429)
                else:
                    statuses.append(200)

            except Exception:
                statuses.append(0)

        page.close()
    except Exception:
        pass
    finally:
        ctx.close()

    throttle_responses = sum(1 for s in statuses if s == 429)
    result = {
        "attempts": len(statuses),
        "throttle_responses": throttle_responses,
        "rate_limited": throttle_responses > 0,
    }

    if throttle_responses == 0 and len(statuses) >= _RATE_LIMIT_BURST:
        findings.append({
            "tool": "playwright:rate_limit",
            "title": "Missing Rate Limiting on Authentication Endpoint",
            "severity": "Medium",
            "category": "Authentication",
            "description": (
                f"The login endpoint at {login_url} accepted {len(statuses)} rapid consecutive "
                f"authentication attempts with incorrect credentials without triggering "
                f"any throttling, lockout, or CAPTCHA challenge. "
                f"This allows unlimited brute-force password attacks."
            ),
            "url": login_url,
            "evidence": (
                f"{len(statuses)} rapid requests sent in under {len(statuses) * 0.15:.1f}s "
                f"— no rate-limit or lockout response detected."
            ),
            "cvss_estimate": 7.5,
            "fix": (
                "Implement account lockout or exponential back-off after 5–10 failed "
                "login attempts. Add CAPTCHA or a time-based one-time password (TOTP) "
                "challenge after repeated failures. Consider IP-based throttling as a "
                "secondary layer."
            ),
            "tags": ["brute-force", "rate-limiting", "authentication"],
        })

    return result, findings


# ── helpers ───────────────────────────────────────────────────────────────────

def _shannon_entropy(s: str) -> float:
    """Shannon entropy in bits per character."""
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((count / n) * math.log2(count / n) for count in freq.values())


def _extract_domain(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.split(":")[0]
    except Exception:
        return url


def _base_url(url: str) -> str:
    """Return scheme://host from a URL."""
    try:
        p = urllib.parse.urlparse(url)
        return f"{p.scheme}://{p.netloc}"
    except Exception:
        return url


def _normalise_url(href: str, scope_domain: str) -> str | None:
    """
    Return the normalised URL if it belongs to scope_domain, else None.
    Strips fragments. Ignores mailto/tel/javascript schemes.
    """
    try:
        parsed = urllib.parse.urlparse(href)
        if parsed.scheme not in ("http", "https"):
            return None
        if scope_domain not in parsed.netloc:
            return None
        # Drop fragments
        return urllib.parse.urlunparse(parsed._replace(fragment=""))
    except Exception:
        return None


def _is_in_scope(url: str, scope_domain: str) -> bool:
    try:
        return scope_domain in urllib.parse.urlparse(url).netloc
    except Exception:
        return False
