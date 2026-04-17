"""
Tool wrapper: open redirect, path traversal (LFI), and SSTI detection
Phase 4 — Professional and Agency tiers. Pure Python — no binary required.

Open redirect:
  Tests common redirect parameter names with a benign out-of-scope URL.
  Confirmed by a 3xx response whose Location header matches the injected value.

Path traversal / LFI:
  Tests URL paths and common file parameters with ../../etc/passwd payloads.
  Confirmed by /etc/passwd content (root:x:0:0:) appearing in the response body.

SSTI:
  Injects math expression payloads for Jinja2/Twig, FreeMarker, ERB, and Mako.
  Confirmed when the computed result (49 for 7*7) appears in the response.

All probes are scoped to scope_domain and use a conservative request rate.
"""

from __future__ import annotations

import re

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Open redirect config ──────────────────────────────────────────────────────

# Common redirect parameter names (sorted by prevalence)
_REDIRECT_PARAMS = [
    "next", "redirect", "return", "returnUrl", "returnTo", "redirect_uri",
    "url", "dest", "destination", "redir", "redirect_url", "target",
    "link", "goto", "callback", "continue", "forward",
]

# Benign, unambiguously out-of-scope probe destination
_REDIRECT_PAYLOAD = "//example.com/echoforge-probe"

# ── Path traversal config ─────────────────────────────────────────────────────

_TRAVERSAL_PAYLOADS = [
    "../../../../etc/passwd",
    "../../../etc/passwd",
    "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "....//....//....//etc/passwd",
    "%252e%252e%252fetc%252fpasswd",
]

_TRAVERSAL_PARAMS = ["file", "path", "page", "include", "doc", "load", "view", "template"]

_PASSWD_RE = re.compile(r"root:[x*]:0:0:", re.MULTILINE)

# ── SSTI config ───────────────────────────────────────────────────────────────

# (payload, expected_result, engine_label)
_SSTI_PROBES = [
    ("{{7*7}}", "49", "Jinja2 / Twig"),
    ("${7*7}", "49", "FreeMarker / Spring EL"),
    ("#{7*7}", "49", "Ruby / Mako"),
    ("<%= 7*7 %>", "49", "ERB"),
    ("{{7*'7'}}", "7777777", "Twig"),
]

_REFLECTION_PARAMS = [
    "name", "search", "q", "query", "msg", "message", "text",
    "template", "subject", "page", "content", "input", "username",
]

_PER_REQUEST_TIMEOUT = 8


def tool_available() -> bool:
    return True  # pure Python — always available


def run_ssrf_redirect_scan(
    target_url: str,
    scope_domain: str,
    exposed_paths: list[dict] | None = None,
    timeout: int = 120,
) -> list[dict]:
    """
    Test target for open redirect, path traversal, and SSTI.

    Args:
        target_url:    Primary target URL.
        scope_domain:  Validated scope domain — out-of-scope URLs are skipped.
        exposed_paths: Paths discovered in Phase 2 (optional, used for traversal probing).
        timeout:       Total scan budget in seconds (best-effort, not hard-enforced).

    Returns:
        List of normalised finding dicts.
    """
    from aiplatform.skills.security.scope_validator import is_in_scope

    findings: list[dict] = []
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (compatible; EchoForge-SecurityAudit/1.0)"
    )

    base = target_url.rstrip("/")

    # ── Open redirect ─────────────────────────────────────────────────────────
    for param in _REDIRECT_PARAMS:
        probe = f"{base}?{param}={_REDIRECT_PAYLOAD}"
        if not is_in_scope(probe, scope_domain):
            continue
        try:
            resp = session.get(
                probe, timeout=_PER_REQUEST_TIMEOUT,
                allow_redirects=False, verify=False,
            )
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location", "")
                if "example.com" in location and "echoforge-probe" in location:
                    findings.append({
                        "tool": "redirect_scan",
                        "title": f"Open Redirect — parameter '{param}'",
                        "severity": "Medium",
                        "category": "Open Redirect",
                        "description": (
                            f"The '{param}' query parameter is used as a redirect destination "
                            "without validation. An attacker can craft a URL that appears to "
                            "originate from the legitimate domain but redirects users to an "
                            "attacker-controlled site — enabling phishing and credential theft."
                        ),
                        "url": probe,
                        "evidence": (
                            f"GET {probe}\n"
                            f"→ HTTP {resp.status_code} Location: {location}"
                        ),
                        "cvss_estimate": 6.1,
                        "fix": (
                            "Validate redirect targets against an allowlist of permitted domains. "
                            "Use relative paths for internal redirects. "
                            "Never pass raw user-supplied URLs directly to redirect logic."
                        ),
                        "poc": probe,
                        "tags": ["open-redirect", "redirect", "confirmed"],
                    })
                    break  # One confirmed open redirect per target is sufficient
        except Exception:
            continue

    # ── Path traversal / LFI ──────────────────────────────────────────────────
    traversal_found = False

    # 1. Path segment traversal
    for payload in _TRAVERSAL_PAYLOADS:
        if traversal_found:
            break
        probe = f"{base}/{payload}"
        if not is_in_scope(probe, scope_domain):
            continue
        finding = _check_traversal(session, probe, base)
        if finding:
            findings.append(finding)
            traversal_found = True

    # 2. Query parameter traversal (file=, path=, page=, etc.)
    if not traversal_found:
        for param in _TRAVERSAL_PARAMS:
            if traversal_found:
                break
            for payload in _TRAVERSAL_PAYLOADS[:3]:  # only try first 3 payloads per param
                probe = f"{base}?{param}={payload}"
                if not is_in_scope(probe, scope_domain):
                    continue
                finding = _check_traversal(session, probe, base)
                if finding:
                    findings.append(finding)
                    traversal_found = True
                    break

    # ── SSTI ──────────────────────────────────────────────────────────────────
    ssti_found = False
    for param in _REFLECTION_PARAMS:
        if ssti_found:
            break
        for payload, expected, engine in _SSTI_PROBES:
            probe = f"{base}?{param}={requests.utils.quote(payload)}"
            if not is_in_scope(probe, scope_domain):
                continue
            try:
                resp = session.get(
                    probe, timeout=_PER_REQUEST_TIMEOUT,
                    allow_redirects=True, verify=False,
                )
                if expected in resp.text:
                    # Sanity-check: make sure this isn't a benign coincidence where
                    # the number 49 already appears on the page by testing the same
                    # param without the payload.
                    baseline_url = f"{base}?{param}=hello"
                    baseline_text = ""
                    try:
                        baseline_resp = session.get(
                            baseline_url, timeout=_PER_REQUEST_TIMEOUT,
                            allow_redirects=True, verify=False,
                        )
                        baseline_text = baseline_resp.text
                    except Exception:
                        pass

                    if expected not in baseline_text:
                        findings.append({
                            "tool": "ssti_scan",
                            "title": (
                                f"Server-Side Template Injection (SSTI) — "
                                f"parameter '{param}' ({engine})"
                            ),
                            "severity": "Critical",
                            "category": "Injection",
                            "description": (
                                f"The '{param}' parameter reflects user input through a "
                                f"server-side template engine ({engine}). "
                                f"Injecting '{payload}' produced '{expected}' in the response, "
                                "confirming template code execution. This can be escalated to "
                                "Remote Code Execution (RCE) by injecting OS commands."
                            ),
                            "url": probe,
                            "evidence": (
                                f"GET {probe}\n"
                                f"Response contains computed result '{expected}' "
                                f"(from expression '{payload}').\n"
                                f"Baseline GET {baseline_url} does not contain '{expected}'."
                            ),
                            "cvss_estimate": 9.8,
                            "fix": (
                                "Never pass user-supplied input to a template engine. "
                                f"Use {engine}'s sandboxed evaluation mode if dynamic templates "
                                "are required. Treat all user input as data, not code."
                            ),
                            "poc": probe,
                            "tags": ["ssti", "injection", "rce", "confirmed"],
                        })
                        ssti_found = True
                        break
            except Exception:
                continue

    return findings


def _check_traversal(
    session: requests.Session, probe: str, base_url: str
) -> dict | None:
    """Send a traversal probe and return a finding dict if /etc/passwd is in the response."""
    try:
        resp = session.get(
            probe, timeout=_PER_REQUEST_TIMEOUT,
            allow_redirects=True, verify=False,
        )
        if _PASSWD_RE.search(resp.text):
            return {
                "tool": "redirect_scan",
                "title": "Path Traversal / LFI — /etc/passwd disclosed",
                "severity": "Critical",
                "category": "Injection",
                "description": (
                    "The server is vulnerable to path traversal (Local File Inclusion). "
                    "Traversal sequences in the URL allow reading arbitrary files from the "
                    "server filesystem, including /etc/passwd and potentially application "
                    "secrets, private keys, and environment configuration files."
                ),
                "url": probe,
                "evidence": (
                    f"GET {probe}\n"
                    "Response body contains Linux /etc/passwd content pattern: root:x:0:0:"
                ),
                "cvss_estimate": 9.1,
                "fix": (
                    "Validate and canonicalise all file path inputs server-side. "
                    "Resolve the absolute path and confirm it is within the expected root "
                    "directory before accessing the filesystem. "
                    "Use chroot jails or equivalent OS-level isolation."
                ),
                "poc": probe,
                "tags": ["lfi", "traversal", "path-traversal", "confirmed"],
            }
    except Exception:
        pass
    return None
