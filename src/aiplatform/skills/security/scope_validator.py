"""
Scope Validation Skill — verifies that the requester controls the target domain.

LEGALLY REQUIRED: every active scanning phase must call this before running.
Never bypass scope validation even in testing.

Verification methods:
  dns_txt  — customer adds a TXT record "_echoforge-verify=TOKEN" to their DNS
  file     — customer uploads a file at /.well-known/echoforge-verify.txt
  manual   — human reviewer marks as verified (for returning customers, agency accounts)

Returns:
  {"verified": True, "method": "dns_txt", "domain": "example.com"}
  {"verified": False, "reason": "TXT record not found", "expected": "...", "found": [...]}
"""

import secrets
import socket
from urllib.parse import urlparse

import dns.resolver


def generate_scope_token() -> str:
    """Generate a random verification token for this audit."""
    return f"echoforge-{secrets.token_hex(16)}"


def verify_dns_txt(domain: str, token: str) -> dict:
    """
    Check that the target domain has a TXT record matching the scope token.

    The customer must add:
      _echoforge-verify.example.com  TXT  "TOKEN"

    Returns a verification result dict.
    """
    record_name = f"_echoforge-verify.{domain}"
    expected = token
    try:
        answers = dns.resolver.resolve(record_name, "TXT")
        found = []
        for rdata in answers:
            for txt_string in rdata.strings:
                found.append(txt_string.decode("utf-8"))

        if expected in found:
            return {
                "verified": True,
                "method": "dns_txt",
                "domain": domain,
                "record": record_name,
            }
        return {
            "verified": False,
            "reason": "TXT record found but token does not match",
            "expected": expected,
            "found": found,
            "record": record_name,
        }
    except dns.resolver.NXDOMAIN:
        return {
            "verified": False,
            "reason": "DNS record not found — add the TXT record and try again",
            "expected": expected,
            "record": record_name,
            "found": [],
        }
    except dns.resolver.NoAnswer:
        return {
            "verified": False,
            "reason": "No TXT records at this subdomain",
            "expected": expected,
            "record": record_name,
            "found": [],
        }
    except Exception as exc:
        return {
            "verified": False,
            "reason": f"DNS lookup failed: {exc}",
            "expected": expected,
            "record": record_name,
            "found": [],
        }


def verify_file_method(domain: str, token: str, timeout: int = 10) -> dict:
    """
    Check that the verification file exists at /.well-known/echoforge-verify.txt
    with the token as its content.
    """
    import requests

    url = f"https://{domain}/.well-known/echoforge-verify.txt"
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        content = resp.text.strip()
        if content == token:
            return {
                "verified": True,
                "method": "file",
                "domain": domain,
                "url": url,
            }
        return {
            "verified": False,
            "reason": "File found but token does not match",
            "expected": token,
            "found": content[:100],
            "url": url,
        }
    except Exception as exc:
        return {
            "verified": False,
            "reason": f"File fetch failed: {exc}",
            "url": url,
        }


def extract_domain(url: str) -> str:
    """Extract the registrable domain from a URL."""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.hostname or ""
    # Strip www. prefix
    return host.lstrip("www.")


def is_in_scope(target_url: str, scope_domain: str) -> bool:
    """
    Verify that a URL being probed is within the approved scope domain.
    Called by active scanning phases before every probe.
    """
    host = urlparse(target_url).hostname or ""
    host = host.lstrip("www.")
    return host == scope_domain or host.endswith(f".{scope_domain}")
