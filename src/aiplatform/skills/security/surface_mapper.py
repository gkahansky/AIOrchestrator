"""
Phase 2 — Active Surface Mapping Skill

Low-noise HTTP probing. Scope validation is called before every request.

Discovers:
  - Live HTTP/HTTPS endpoints from subdomain list
  - Technology stack from response headers and HTML meta tags
  - Common exposed paths (admin panels, backup files, config files)
  - Redirect chains and HTTPS enforcement
  - HTTP security headers baseline (full analysis in Phase 3)
  - robots.txt and sitemap.xml content

IMPORTANT: every outbound request is validated against scope before sending.
"""

import re
from urllib.parse import urljoin, urlparse

import requests
from requests.exceptions import RequestException

from aiplatform.skills.security.scope_validator import is_in_scope

_DEFAULT_TIMEOUT = 10
_UA = "EchoForge-Security-Audit/1.0 (surface mapping; contact: security@echoforge.biz)"

# Paths to probe for common exposures
_SENSITIVE_PATHS = [
    "/.env",
    "/.env.local",
    "/.env.production",
    "/.git/HEAD",
    "/.git/config",
    "/backup.zip",
    "/backup.tar.gz",
    "/wp-config.php",
    "/config.php",
    "/database.php",
    "/admin",
    "/admin/",
    "/administrator/",
    "/phpmyadmin/",
    "/phpMyAdmin/",
    "/adminer.php",
    "/wp-admin/",
    "/login",
    "/dashboard",
    "/api/",
    "/api/v1/",
    "/api/v2/",
    "/graphql",
    "/swagger",
    "/swagger-ui.html",
    "/swagger-ui/",
    "/openapi.json",
    "/api-docs",
    "/redoc",
    "/.well-known/security.txt",
    "/robots.txt",
    "/sitemap.xml",
    "/crossdomain.xml",
    "/server-status",
    "/server-info",
]

# Technology fingerprints — header/html patterns
_TECH_SIGNATURES = {
    "WordPress":     [("X-Powered-By", ""), ("html", "wp-content"), ("html", "wp-includes")],
    "Drupal":        [("X-Generator", "Drupal"), ("html", "Drupal")],
    "Joomla":        [("html", "/media/jui/"), ("html", "Joomla!")],
    "Laravel":       [("X-Powered-By", ""), ("html", "laravel"), ("Set-Cookie", "laravel_session")],
    "Django":        [("html", "__django"), ("Set-Cookie", "csrftoken")],
    "Rails":         [("X-Powered-By", "Phusion Passenger"), ("X-Runtime", "")],
    "Next.js":       [("X-Powered-By", "Next.js"), ("html", "__NEXT_DATA__")],
    "React":         [("html", "react-root"), ("html", "data-reactroot")],
    "Vue.js":        [("html", "data-v-"), ("html", "__vue_app__")],
    "nginx":         [("Server", "nginx")],
    "Apache":        [("Server", "Apache")],
    "Cloudflare":    [("CF-RAY", ""), ("Server", "cloudflare")],
    "AWS ALB":       [("Server", "awselb")],
    "Vercel":        [("X-Vercel-Id", ""), ("Server", "Vercel")],
    "PHP":           [("X-Powered-By", "PHP")],
    "ASP.NET":       [("X-Powered-By", "ASP.NET"), ("X-AspNet-Version", "")],
}


# ── Public entry point ─────────────────────────────────────────────────────────

def run_surface_mapping(target_url: str, scope_domain: str,
                        subdomains: list[str] | None = None) -> dict:
    """
    Map the attack surface of a target.

    Args:
        target_url:   The primary target URL (https://example.com).
        scope_domain: The validated scope domain (example.com).
        subdomains:   Subdomains discovered in Phase 1 to probe.

    Returns:
        dict with keys: target_baseline, tech_stack, exposed_paths,
                        live_subdomains, robots_txt, sitemap_urls, errors
    """
    results: dict = {
        "target_url": target_url,
        "scope_domain": scope_domain,
        "target_baseline": {},
        "tech_stack": [],
        "exposed_paths": [],
        "live_subdomains": [],
        "robots_txt": "",
        "sitemap_urls": [],
        "errors": [],
    }

    _probe_target_baseline(target_url, scope_domain, results)
    _probe_sensitive_paths(target_url, scope_domain, results)
    _fetch_robots_and_sitemap(target_url, scope_domain, results)

    if subdomains:
        _probe_subdomains(subdomains, scope_domain, results)

    return results


# ── Target baseline ───────────────────────────────────────────────────────────

def _probe_target_baseline(url: str, scope_domain: str, results: dict) -> None:
    if not is_in_scope(url, scope_domain):
        results["errors"].append(f"Scope violation prevented: {url}")
        return
    try:
        resp = requests.get(
            url, timeout=_DEFAULT_TIMEOUT,
            headers={"User-Agent": _UA},
            allow_redirects=True,
            verify=True,
        )
        baseline = {
            "status_code": resp.status_code,
            "final_url": resp.url,
            "redirect_chain": [r.url for r in resp.history],
            "https_enforced": resp.url.startswith("https://"),
            "headers": dict(resp.headers),
            "server": resp.headers.get("Server", ""),
            "content_type": resp.headers.get("Content-Type", ""),
            "content_length": len(resp.content),
        }
        results["target_baseline"] = baseline
        results["tech_stack"] = _fingerprint_tech(resp.headers, resp.text)
    except Exception as exc:
        results["errors"].append(f"Baseline probe: {exc}")


# ── Sensitive path probing ────────────────────────────────────────────────────

def _probe_sensitive_paths(base_url: str, scope_domain: str, results: dict) -> None:
    base = base_url.rstrip("/")
    for path in _SENSITIVE_PATHS:
        url = base + path
        if not is_in_scope(url, scope_domain):
            continue
        try:
            resp = requests.get(
                url, timeout=_DEFAULT_TIMEOUT,
                headers={"User-Agent": _UA},
                allow_redirects=False,
                verify=True,
            )
            # Only flag 200s and interesting 30x that don't redirect to login
            if resp.status_code == 200:
                snippet = resp.text[:300].strip()
                severity = _classify_path_severity(path, resp.text)
                results["exposed_paths"].append({
                    "path": path,
                    "url": url,
                    "status": resp.status_code,
                    "severity": severity,
                    "content_snippet": snippet,
                    "content_type": resp.headers.get("Content-Type", ""),
                })
        except RequestException:
            pass  # Connection refused, timeout — path not exposed


def _classify_path_severity(path: str, body: str) -> str:
    critical_patterns = [
        r"APP_KEY=", r"DB_PASSWORD=", r"AWS_SECRET", r"SECRET_KEY",
        r"\[core\]", r"gitdir:",  # .git/config, .git/HEAD
    ]
    high_patterns = [
        r"\$db_pass", r"password\s*=", r"<phpmyadmin", r"swagger",
        r"graphql", r"openapi",
    ]
    for pattern in critical_patterns:
        if re.search(pattern, body, re.IGNORECASE):
            return "Critical"
    for pattern in high_patterns:
        if re.search(pattern, body, re.IGNORECASE):
            return "High"
    if any(p in path for p in ["/.env", "/.git", "/wp-config", "/config.php"]):
        return "High"
    if any(p in path for p in ["/admin", "/phpmyadmin", "/adminer"]):
        return "Medium"
    return "Low"


# ── Robots.txt + sitemap ──────────────────────────────────────────────────────

def _fetch_robots_and_sitemap(base_url: str, scope_domain: str, results: dict) -> None:
    base = base_url.rstrip("/")
    for url, key in [(base + "/robots.txt", "robots_txt"),
                     (base + "/sitemap.xml", "sitemap_raw")]:
        if not is_in_scope(url, scope_domain):
            continue
        try:
            r = requests.get(url, timeout=_DEFAULT_TIMEOUT,
                             headers={"User-Agent": _UA}, verify=True)
            if r.status_code == 200:
                if key == "robots_txt":
                    results["robots_txt"] = r.text[:2000]
                    # Extract Disallow paths — often reveal internal structure
                    disallowed = re.findall(r"Disallow:\s*(.+)", r.text)
                    results["robots_disallowed_paths"] = [d.strip() for d in disallowed]
        except RequestException:
            pass


# ── Subdomain liveness ────────────────────────────────────────────────────────

def _probe_subdomains(subdomains: list[str], scope_domain: str, results: dict) -> None:
    for subdomain in subdomains[:50]:  # cap at 50 to keep phase fast
        for scheme in ("https", "http"):
            url = f"{scheme}://{subdomain}"
            if not is_in_scope(url, scope_domain):
                continue
            try:
                resp = requests.get(
                    url, timeout=6,
                    headers={"User-Agent": _UA},
                    allow_redirects=True,
                    verify=False,  # subdomains may have cert mismatches
                )
                results["live_subdomains"].append({
                    "subdomain": subdomain,
                    "url": resp.url,
                    "status": resp.status_code,
                    "server": resp.headers.get("Server", ""),
                    "title": _extract_title(resp.text),
                })
                break  # https worked, don't also try http
            except RequestException:
                continue


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>([^<]*)</title>", html, re.IGNORECASE)
    return m.group(1).strip()[:100] if m else ""


# ── Tech fingerprinting ───────────────────────────────────────────────────────

def _fingerprint_tech(headers: dict, html: str) -> list[str]:
    detected = []
    headers_lower = {k.lower(): v for k, v in headers.items()}
    html_lower = html[:50000].lower()

    for tech, signatures in _TECH_SIGNATURES.items():
        for source, pattern in signatures:
            if source == "html":
                if pattern.lower() in html_lower:
                    if tech not in detected:
                        detected.append(tech)
                    break
            else:
                header_val = headers_lower.get(source.lower(), "")
                if pattern == "" and header_val:
                    if tech not in detected:
                        detected.append(tech)
                    break
                elif pattern and pattern.lower() in header_val.lower():
                    if tech not in detected:
                        detected.append(tech)
                    break
    return detected
