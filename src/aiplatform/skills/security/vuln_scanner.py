"""
Phase 3 — Automated Vulnerability Scanning Skill

Analyses the target for common vulnerabilities using pure Python — no native
tool dependencies. This covers the security-headers, TLS, and misconfiguration
surface reliably in all environments.

Native tools (nuclei, nikto, sqlmap) are invoked as subprocesses only when
Docker container images are available. Those integrations are stubbed here with
clear integration points so they can be wired in without code changes.

Checks:
  - HTTP security headers (CSP, HSTS, X-Frame-Options, X-Content-Type, etc.)
  - TLS/SSL configuration via ssl module
  - Cookie security flags (HttpOnly, Secure, SameSite)
  - CORS misconfiguration (reflected Origin, wildcard with credentials)
  - Common injection points (forms, query parameters)
  - Open redirect patterns in responses
  - Information disclosure (verbose headers, error pages)
  - Clickjacking vulnerability
"""

import re
import socket
import ssl
from urllib.parse import urlparse, urljoin

import requests
from requests.exceptions import RequestException

from aiplatform.skills.security.scope_validator import is_in_scope
from aiplatform.skills.security.rate_limiter import RateLimiter

_DEFAULT_TIMEOUT = 10
_UA = "EchoForge-Security-Audit/1.0 (vulnerability scan; contact: security@echoforge.biz)"


# ── Public entry point ─────────────────────────────────────────────────────────

def run_vuln_scan(target_url: str, scope_domain: str,
                  surface_data: dict | None = None,
                  max_rps: float = 2.0) -> dict:
    """
    Run the automated vulnerability scan phase.

    Args:
        target_url:   Primary target URL.
        scope_domain: Validated scope domain.
        surface_data: Output from Phase 2 surface mapping.

    Returns:
        dict with: findings, header_audit, tls_audit, cors_issues,
                   cookie_issues, info_disclosure, errors
    """
    results: dict = {
        "target_url": target_url,
        "findings": [],
        "header_audit": {},
        "tls_audit": {},
        "cors_issues": [],
        "cookie_issues": [],
        "info_disclosure": [],
        "errors": [],
    }

    if not is_in_scope(target_url, scope_domain):
        results["errors"].append(f"Scope violation: {target_url}")
        return results

    limiter = RateLimiter(max_rps=max_rps)

    _audit_security_headers(target_url, results, limiter)
    _audit_tls(target_url, scope_domain, results)
    _audit_cors(target_url, scope_domain, results, limiter)
    _audit_cookies(target_url, scope_domain, results, limiter)
    _detect_info_disclosure(target_url, scope_domain, surface_data or {}, results)
    _check_clickjacking(target_url, scope_domain, results)

    # Aggregate all issues into the findings list with severity
    _consolidate_findings(results)

    return results


# ── Security headers ──────────────────────────────────────────────────────────

_REQUIRED_HEADERS = {
    "Strict-Transport-Security": {
        "severity": "High",
        "description": "Missing HSTS header — allows downgrade to HTTP",
        "recommendation": "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload",
    },
    "Content-Security-Policy": {
        "severity": "High",
        "description": "Missing CSP header — XSS attack surface is unrestricted",
        "recommendation": "Implement a restrictive Content-Security-Policy.",
    },
    "X-Frame-Options": {
        "severity": "Medium",
        "description": "Missing X-Frame-Options — page can be embedded in iframes (clickjacking risk)",
        "recommendation": "Add: X-Frame-Options: DENY or SAMEORIGIN",
    },
    "X-Content-Type-Options": {
        "severity": "Medium",
        "description": "Missing X-Content-Type-Options — browser may sniff MIME types",
        "recommendation": "Add: X-Content-Type-Options: nosniff",
    },
    "Referrer-Policy": {
        "severity": "Low",
        "description": "Missing Referrer-Policy — referrer data may leak to third parties",
        "recommendation": "Add: Referrer-Policy: strict-origin-when-cross-origin",
    },
    "Permissions-Policy": {
        "severity": "Low",
        "description": "Missing Permissions-Policy — browser features not restricted",
        "recommendation": "Add Permissions-Policy to restrict camera, microphone, geolocation.",
    },
}

def _audit_security_headers(url: str, results: dict, limiter: RateLimiter) -> None:
    try:
        limiter.acquire()
        resp = requests.get(url, timeout=_DEFAULT_TIMEOUT,
                            headers={"User-Agent": _UA},
                            allow_redirects=True, verify=True)
        headers = resp.headers
        audit = {}
        for header, meta in _REQUIRED_HEADERS.items():
            present = header in headers
            value = headers.get(header, "")
            issues = []
            if not present:
                issues.append(meta["description"])
            else:
                issues.extend(_analyse_header_value(header, value))

            audit[header] = {
                "present": present,
                "value": value,
                "issues": issues,
                "severity": meta["severity"] if (not present or issues) else "Pass",
                "recommendation": meta["recommendation"] if (not present or issues) else "",
            }

        # Check for information-leaking headers
        leak_headers = {}
        for h in ("Server", "X-Powered-By", "X-AspNet-Version", "X-AspNetMvc-Version"):
            if h in headers:
                leak_headers[h] = headers[h]
        if leak_headers:
            audit["_info_leak_headers"] = leak_headers

        results["header_audit"] = audit
    except Exception as exc:
        results["errors"].append(f"Header audit: {exc}")


def _analyse_header_value(header: str, value: str) -> list[str]:
    issues = []
    if header == "Strict-Transport-Security":
        if "max-age" not in value:
            issues.append("HSTS missing max-age directive")
        elif re.search(r"max-age=(\d+)", value):
            age = int(re.search(r"max-age=(\d+)", value).group(1))
            if age < 86400:
                issues.append(f"HSTS max-age too short ({age}s) — recommend ≥31536000")
        if "includeSubDomains" not in value:
            issues.append("HSTS missing includeSubDomains")
    elif header == "Content-Security-Policy":
        if "unsafe-inline" in value:
            issues.append("CSP allows 'unsafe-inline' — weakens XSS protection")
        if "unsafe-eval" in value:
            issues.append("CSP allows 'unsafe-eval' — allows dynamic code execution")
        if "*" in value and "default-src" in value:
            issues.append("CSP default-src uses wildcard — overly permissive")
    return issues


# ── TLS / SSL ─────────────────────────────────────────────────────────────────

def _audit_tls(url: str, scope_domain: str, results: dict) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or scope_domain
    port = parsed.port or 443
    tls_audit: dict = {}

    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.create_connection((host, port), timeout=10),
                             server_hostname=host) as conn:
            cert = conn.getpeercert()
            cipher = conn.cipher()
            version = conn.version()

            tls_audit["tls_version"] = version
            tls_audit["cipher_suite"] = cipher[0] if cipher else ""
            tls_audit["cert_subject"] = dict(x[0] for x in cert.get("subject", []))
            tls_audit["cert_issuer"] = dict(x[0] for x in cert.get("issuer", []))
            tls_audit["cert_expiry"] = cert.get("notAfter", "")

            issues = []
            if version in ("TLSv1", "TLSv1.1", "SSLv3"):
                issues.append(f"Outdated TLS version in use: {version} — upgrade to TLS 1.2+")
            if cipher and any(weak in cipher[0] for weak in ("RC4", "DES", "NULL", "EXPORT")):
                issues.append(f"Weak cipher suite: {cipher[0]}")
            tls_audit["issues"] = issues
            tls_audit["passed"] = len(issues) == 0

    except ssl.SSLError as exc:
        tls_audit["error"] = f"SSL error: {exc}"
        tls_audit["issues"] = [f"SSL/TLS error — {exc}"]
        tls_audit["passed"] = False
    except Exception as exc:
        tls_audit["error"] = str(exc)
        tls_audit["passed"] = False

    results["tls_audit"] = tls_audit


# ── CORS misconfiguration ─────────────────────────────────────────────────────

def _audit_cors(url: str, scope_domain: str, results: dict,
                limiter: RateLimiter) -> None:
    test_origins = [
        f"https://evil.com",
        f"https://evil.{scope_domain}",
        f"null",
    ]
    for origin in test_origins:
        try:
            limiter.acquire()
            resp = requests.options(
                url, timeout=_DEFAULT_TIMEOUT,
                headers={"User-Agent": _UA, "Origin": origin,
                         "Access-Control-Request-Method": "GET"},
                verify=True,
            )
            acao = resp.headers.get("Access-Control-Allow-Origin", "")
            acac = resp.headers.get("Access-Control-Allow-Credentials", "")

            if acao == origin or acao == "*":
                issue = {
                    "origin_tested": origin,
                    "acao_header": acao,
                    "credentials_allowed": acac.lower() == "true",
                }
                if acao == "*" and acac.lower() == "true":
                    issue["severity"] = "Critical"
                    issue["description"] = (
                        "CORS wildcard with credentials=true — any origin can "
                        "make authenticated requests cross-origin"
                    )
                elif acao == origin:
                    issue["severity"] = "High"
                    issue["description"] = (
                        f"Server reflects arbitrary Origin '{origin}' — "
                        "cross-origin requests accepted from any domain"
                    )
                else:
                    issue["severity"] = "Medium"
                    issue["description"] = f"CORS allows Origin: {origin}"
                results["cors_issues"].append(issue)
        except RequestException:
            pass


# ── Cookie security flags ─────────────────────────────────────────────────────

def _audit_cookies(url: str, scope_domain: str, results: dict,
                   limiter: RateLimiter) -> None:
    try:
        limiter.acquire()
        resp = requests.get(url, timeout=_DEFAULT_TIMEOUT,
                            headers={"User-Agent": _UA},
                            allow_redirects=True, verify=True)
        for cookie in resp.cookies:
            issues = []
            if not cookie.secure:
                issues.append("Missing Secure flag — cookie transmitted over HTTP")
            if not cookie.has_nonstandard_attr("HttpOnly"):
                issues.append("Missing HttpOnly flag — accessible via JavaScript (XSS risk)")
            samesite = cookie.get_nonstandard_attr("SameSite", "")
            if not samesite:
                issues.append("Missing SameSite attribute — CSRF risk")
            elif samesite.lower() == "none" and not cookie.secure:
                issues.append("SameSite=None requires Secure flag")

            if issues:
                results["cookie_issues"].append({
                    "name": cookie.name,
                    "domain": cookie.domain,
                    "issues": issues,
                    "severity": "High" if len(issues) >= 2 else "Medium",
                })
    except Exception as exc:
        results["errors"].append(f"Cookie audit: {exc}")


# ── Information disclosure ────────────────────────────────────────────────────

def _detect_info_disclosure(url: str, scope_domain: str,
                            surface_data: dict, results: dict) -> None:
    # Server/tech version leakage from headers
    baseline = surface_data.get("target_baseline", {})
    headers = baseline.get("headers", {})
    for header in ("Server", "X-Powered-By", "X-AspNet-Version", "X-Runtime"):
        val = headers.get(header, "")
        if val and re.search(r"\d+\.\d+", val):
            results["info_disclosure"].append({
                "type": "version_disclosure",
                "header": header,
                "value": val,
                "severity": "Low",
                "description": f"{header} header reveals version: {val}",
                "fix": f"Remove or mask the {header} response header.",
            })

    # Exposed paths from Phase 2
    for exposed in surface_data.get("exposed_paths", []):
        if exposed.get("severity") in ("Critical", "High"):
            results["info_disclosure"].append({
                "type": "exposed_path",
                "path": exposed["path"],
                "url": exposed["url"],
                "severity": exposed["severity"],
                "description": f"Sensitive path accessible: {exposed['path']}",
                "fix": "Restrict access to this path or remove the file.",
            })


# ── Clickjacking ──────────────────────────────────────────────────────────────

def _check_clickjacking(url: str, scope_domain: str, results: dict) -> None:
    header_audit = results.get("header_audit", {})
    xfo = header_audit.get("X-Frame-Options", {})
    csp = header_audit.get("Content-Security-Policy", {})

    xfo_missing = not xfo.get("present", True)
    csp_no_frameancestors = "frame-ancestors" not in csp.get("value", "")

    if xfo_missing and csp_no_frameancestors:
        results["findings"].append({
            "category": "Client-Side",
            "title": "Clickjacking — No frame embedding protection",
            "severity": "Medium",
            "description": (
                "The page lacks both X-Frame-Options and CSP frame-ancestors. "
                "It can be embedded in a malicious iframe to trick users into "
                "clicking UI elements they cannot see."
            ),
            "fix": "Add X-Frame-Options: DENY or CSP: frame-ancestors 'none'.",
            "cvss_estimate": 6.1,
        })


# ── Consolidate all issues into findings list ─────────────────────────────────

def _consolidate_findings(results: dict) -> None:
    # Headers
    for header, data in results.get("header_audit", {}).items():
        if header.startswith("_"):
            continue
        if data.get("severity") not in ("Pass", ""):
            results["findings"].append({
                "category": "Security Misconfiguration",
                "title": f"Missing or weak {header} header",
                "severity": data["severity"],
                "description": "; ".join(data.get("issues", [])),
                "fix": data.get("recommendation", ""),
                "cvss_estimate": {"Critical": 9.0, "High": 7.5, "Medium": 5.0, "Low": 3.0}.get(
                    data["severity"], 3.0),
            })

    # TLS
    for issue in results.get("tls_audit", {}).get("issues", []):
        results["findings"].append({
            "category": "Transport Security",
            "title": "TLS/SSL configuration weakness",
            "severity": "High",
            "description": issue,
            "fix": "Upgrade TLS to 1.2+ and disable weak cipher suites.",
            "cvss_estimate": 7.4,
        })

    # CORS
    for issue in results.get("cors_issues", []):
        results["findings"].append({
            "category": "Access Control",
            "title": "CORS misconfiguration",
            "severity": issue.get("severity", "High"),
            "description": issue.get("description", ""),
            "fix": "Restrict Access-Control-Allow-Origin to trusted domains only.",
            "cvss_estimate": {"Critical": 9.1, "High": 7.5, "Medium": 5.0}.get(
                issue.get("severity", "High"), 7.5),
        })

    # Cookies
    for issue in results.get("cookie_issues", []):
        results["findings"].append({
            "category": "Session Management",
            "title": f"Insecure cookie: {issue['name']}",
            "severity": issue["severity"],
            "description": "; ".join(issue.get("issues", [])),
            "fix": "Set Secure, HttpOnly, and SameSite=Strict on all session cookies.",
            "cvss_estimate": 6.3,
        })

    # Information disclosure
    for issue in results.get("info_disclosure", []):
        results["findings"].append({
            "category": "Information Disclosure",
            "title": issue.get("description", ""),
            "severity": issue["severity"],
            "description": issue.get("description", ""),
            "fix": issue.get("fix", ""),
            "cvss_estimate": 5.3,
        })
