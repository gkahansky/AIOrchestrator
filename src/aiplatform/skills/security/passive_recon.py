"""
Phase 1 — Passive OSINT Reconnaissance Skill

Zero active traffic to the target. All data sourced from third-party APIs.

Collects:
  - Subdomains via crt.sh certificate transparency
  - DNS records (A, MX, TXT, NS, CNAME)
  - IP address + reverse DNS
  - SPF / DMARC policy analysis
  - HaveIBeenPwned breach check (requires API key)
  - Censys host data (requires API key)
  - Historical URLs via Wayback Machine CDX API (free, no key)
  - Basic tech fingerprint via HTTP headers (passive — no crawling)

Returns a findings dict consumed by the pipeline and later passed to Claude.
"""

import re
import socket
import time
from urllib.parse import urlparse

import dns.resolver
import requests


_DEFAULT_TIMEOUT = 10
_UA = "EchoForge-Security-Audit/1.0 (passive recon; contact: security@echoforge.biz)"


# ── Public entry point ─────────────────────────────────────────────────────────

def run_passive_recon(domain: str, hibp_api_key: str = "",
                      censys_api_key: str = "") -> dict:
    """
    Run all passive OSINT checks against a domain.

    Args:
        domain:        The registrable domain (e.g. "example.com").
        hibp_api_key:  HaveIBeenPwned API key (optional — skips breach check if absent).
        censys_api_key: Censys bearer token (optional — skips Censys enrichment if absent).
                        Get it from search.censys.io → Account → API.

    Returns:
        dict with keys: domain, subdomains, dns_records, ip_info, spf_dmarc,
                        wayback_urls, breach_info, censys_info, errors
    """
    results: dict = {
        "domain": domain,
        "subdomains": [],
        "dns_records": {},
        "ip_info": {},
        "spf_dmarc": {},
        "wayback_urls": [],
        "breach_info": {},
        "censys_info": {},
        "errors": [],
    }

    # Run all checks — each is isolated so one failure doesn't abort the rest
    _collect_subdomains_crtsh(domain, results)
    _collect_dns_records(domain, results)
    _collect_ip_info(domain, results)
    _analyse_spf_dmarc(domain, results)
    _collect_wayback_urls(domain, results)

    if hibp_api_key:
        _check_hibp(domain, hibp_api_key, results)

    if censys_api_key:
        _enrich_censys(results.get("ip_info", {}).get("ip", ""), censys_api_key, results)

    return results


# ── Subdomain enumeration — crt.sh ────────────────────────────────────────────

def _collect_subdomains_crtsh(domain: str, results: dict) -> None:
    try:
        resp = requests.get(
            "https://crt.sh/",
            params={"q": f"%.{domain}", "output": "json"},
            timeout=_DEFAULT_TIMEOUT,
            headers={"User-Agent": _UA},
        )
        if resp.status_code != 200:
            results["errors"].append(f"crt.sh returned {resp.status_code}")
            return
        entries = resp.json()
        seen: set[str] = set()
        for entry in entries:
            for name in str(entry.get("name_value", "")).split("\n"):
                name = name.strip().lstrip("*.")
                if name and domain in name and name not in seen:
                    seen.add(name)
        results["subdomains"] = sorted(seen)
    except Exception as exc:
        results["errors"].append(f"crt.sh: {exc}")


# ── DNS records ───────────────────────────────────────────────────────────────

def _collect_dns_records(domain: str, results: dict) -> None:
    records: dict = {}
    for rtype in ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"):
        try:
            answers = dns.resolver.resolve(domain, rtype, lifetime=5)
            records[rtype] = [str(r) for r in answers]
        except dns.resolver.NXDOMAIN:
            records[rtype] = []
        except dns.resolver.NoAnswer:
            records[rtype] = []
        except Exception:
            records[rtype] = []

    # Zone transfer attempt (should always fail on properly configured DNS)
    try:
        ns_list = records.get("NS", [])
        zt_results = []
        for ns in ns_list[:2]:  # only try first 2 nameservers
            try:
                z = dns.zone.from_xfr(dns.query.xfr(ns.rstrip("."), domain, lifetime=3))
                zt_results.append(f"ZONE TRANSFER SUCCEEDED on {ns} — critical finding!")
            except Exception:
                zt_results.append(f"{ns}: refused (expected)")
        records["zone_transfer"] = zt_results
    except Exception:
        records["zone_transfer"] = []

    results["dns_records"] = records


# ── IP info ───────────────────────────────────────────────────────────────────

def _collect_ip_info(domain: str, results: dict) -> None:
    try:
        ip = socket.gethostbyname(domain)
        rdns = ""
        try:
            rdns = socket.gethostbyaddr(ip)[0]
        except Exception:
            pass

        # Basic ASN / org info via ip-api.com (free, no key)
        org_info = {}
        try:
            r = requests.get(
                f"http://ip-api.com/json/{ip}",
                timeout=_DEFAULT_TIMEOUT,
                params={"fields": "status,country,regionName,city,org,isp,as"},
                headers={"User-Agent": _UA},
            )
            if r.status_code == 200:
                org_info = r.json()
        except Exception:
            pass

        results["ip_info"] = {
            "ip": ip,
            "rdns": rdns,
            "country": org_info.get("country", ""),
            "org": org_info.get("org", ""),
            "isp": org_info.get("isp", ""),
            "asn": org_info.get("as", ""),
        }
    except Exception as exc:
        results["errors"].append(f"IP resolution: {exc}")


# ── SPF / DMARC ───────────────────────────────────────────────────────────────

def _analyse_spf_dmarc(domain: str, results: dict) -> None:
    spf = ""
    dmarc = ""
    issues = []

    # SPF — look in TXT records
    for txt in results.get("dns_records", {}).get("TXT", []):
        if "v=spf1" in txt:
            spf = txt
            break

    # DMARC — dedicated subdomain
    try:
        answers = dns.resolver.resolve(f"_dmarc.{domain}", "TXT", lifetime=5)
        for r in answers:
            val = str(r)
            if "v=DMARC1" in val:
                dmarc = val
                break
    except Exception:
        pass

    if not spf:
        issues.append("No SPF record — domain is vulnerable to email spoofing")
    elif "+all" in spf:
        issues.append("SPF uses '+all' — allows any host to send mail as this domain")

    if not dmarc:
        issues.append("No DMARC record — phishing/spoofing is unrestricted")
    elif "p=none" in dmarc:
        issues.append("DMARC policy is 'none' — monitoring only, not enforced")

    results["spf_dmarc"] = {
        "spf_record": spf,
        "dmarc_record": dmarc,
        "issues": issues,
    }


# ── Wayback Machine historical URLs ───────────────────────────────────────────

def _collect_wayback_urls(domain: str, results: dict) -> None:
    try:
        resp = requests.get(
            "http://web.archive.org/cdx/search/cdx",
            params={
                "url": f"*.{domain}/*",
                "output": "json",
                "fl": "original",
                "collapse": "urlkey",
                "limit": 200,
            },
            timeout=15,
            headers={"User-Agent": _UA},
        )
        if resp.status_code != 200:
            return
        data = resp.json()
        # First row is the header ["original"]
        urls = [row[0] for row in data[1:] if row]
        results["wayback_urls"] = urls[:200]
    except Exception as exc:
        results["errors"].append(f"Wayback Machine: {exc}")


# ── HaveIBeenPwned — domain breach check ─────────────────────────────────────

def _check_hibp(domain: str, api_key: str, results: dict) -> None:
    try:
        resp = requests.get(
            f"https://haveibeenpwned.com/api/v3/breaches",
            headers={
                "hibp-api-key": api_key,
                "User-Agent": _UA,
            },
            timeout=_DEFAULT_TIMEOUT,
        )
        if resp.status_code != 200:
            results["errors"].append(f"HIBP: {resp.status_code}")
            return

        breaches = resp.json()
        domain_breaches = [
            {
                "name": b["Name"],
                "date": b["BreachDate"],
                "data_classes": b.get("DataClasses", []),
                "is_verified": b.get("IsVerified", False),
            }
            for b in breaches
            if domain.lower() in b.get("Domain", "").lower()
        ]
        results["breach_info"] = {
            "breaches_found": len(domain_breaches),
            "breaches": domain_breaches,
        }
    except Exception as exc:
        results["errors"].append(f"HIBP: {exc}")


# ── Censys host enrichment ────────────────────────────────────────────────────

def _enrich_censys(ip: str, api_key: str, results: dict) -> None:
    """Enrich IP data via Censys API v2 — uses a single bearer token."""
    if not ip:
        return
    try:
        resp = requests.get(
            f"https://search.censys.io/api/v2/hosts/{ip}",
            timeout=_DEFAULT_TIMEOUT,
            headers={"User-Agent": _UA, "Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code != 200:
            results["errors"].append(f"Censys: {resp.status_code}")
            return

        data = resp.json().get("result", {})
        services = data.get("services", [])
        open_ports = [
            {
                "port": s.get("port"),
                "transport": s.get("transport_protocol", ""),
                "service": s.get("service_name", ""),
                "banner": s.get("banner", "")[:200],
            }
            for s in services
        ]
        results["censys_info"] = {
            "ip": ip,
            "open_ports": open_ports,
            "last_updated": data.get("last_updated_at", ""),
        }
    except Exception as exc:
        results["errors"].append(f"Censys: {exc}")
