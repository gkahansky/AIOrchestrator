"""
Tool wrapper: testssl.sh
Comprehensive TLS/SSL configuration audit.
Falls back to [] if testssl.sh is not installed.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse


# testssl.sh severity → our severity
_SEVERITY_MAP = {
    "CRITICAL": "Critical",
    "HIGH":     "High",
    "MEDIUM":   "Medium",
    "LOW":      "Low",
    "INFO":     None,       # skip pure-info entries
    "OK":       None,       # skip passing checks
    "WARN":     "Low",
    "NOT ok":   "Medium",
    "NOT_ok":   "Medium",
}
_SEVERITY_CVSS = {"Critical": 9.0, "High": 7.5, "Medium": 5.0, "Low": 3.0}

# testssl IDs we care about — skip fingerprinting noise
_SKIP_IDS = {
    "service", "protocol_negotiated", "cipher_negotiated",
    "fingerprint_sha1", "fingerprint_sha256", "cert_chain_of_trust",
    "cert_notBefore", "cert_notAfter",
}


def tool_available() -> bool:
    return shutil.which("testssl.sh") is not None


def run_testssl(
    target_url: str,
    scope_domain: str,
    work_dir: str | None = None,
    timeout: int = 180,
) -> list[dict]:
    """
    Run testssl.sh against the target host:port and return TLS findings.
    Only MEDIUM severity and above are included.
    """
    if not tool_available():
        return []

    parsed = urlparse(target_url)
    host = parsed.hostname or scope_domain
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    target = f"{host}:{port}"

    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    out_file = tmp / "testssl-output.json"

    cmd = [
        "testssl.sh",
        "--jsonfile", str(out_file),
        "--quiet",
        "--severity", "MEDIUM",     # report MEDIUM+ only
        "--fast",                    # skip slower checks (beast, lucky13, etc.)
        "--nodns", "min",            # minimal DNS lookups
        "--color", "0",
        target,
    ]

    try:
        subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        return []

    return _parse_output(out_file, target_url)


def _parse_output(out_file: Path, target_url: str) -> list[dict]:
    findings = []
    if not out_file.exists():
        return findings

    try:
        data = json.loads(out_file.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return findings

    # testssl JSON is an array of result objects
    entries = data if isinstance(data, list) else data.get("scanResult", [{}])[0].get("findings", [])

    for entry in entries:
        finding_id = entry.get("id", "")
        if finding_id.lower() in _SKIP_IDS:
            continue

        severity_raw = entry.get("severity", "INFO").upper()
        severity = _SEVERITY_MAP.get(severity_raw)
        if severity is None:
            continue

        finding_text = entry.get("finding", "")
        if not finding_text or finding_text.lower() in ("not vulnerable", "not affected"):
            continue

        findings.append({
            "tool": "testssl",
            "title": _id_to_title(finding_id, finding_text),
            "severity": severity,
            "category": "Transport Security",
            "description": f"{finding_id}: {finding_text}",
            "url": target_url,
            "evidence": f"testssl finding [{finding_id}]: {finding_text}",
            "cvss_estimate": _SEVERITY_CVSS.get(severity, 3.0),
            "fix": _remediation(finding_id),
            "tags": ["tls", "ssl", "testssl"],
        })

    return findings


def _id_to_title(finding_id: str, finding_text: str) -> str:
    titles = {
        "SSLv2":        "SSLv2 supported — critically insecure",
        "SSLv3":        "SSLv3 supported — POODLE attack risk",
        "TLS1":         "TLS 1.0 supported — deprecated protocol",
        "TLS1_1":       "TLS 1.1 supported — deprecated protocol",
        "heartbleed":   "Heartbleed vulnerability (CVE-2014-0160)",
        "CCS":          "OpenSSL CCS Injection (CVE-2014-0224)",
        "ticketbleed":  "Ticketbleed (CVE-2016-9244)",
        "ROBOT":        "ROBOT attack vulnerability",
        "secure_renego": "Insecure TLS renegotiation",
        "BEAST":        "BEAST attack (TLS 1.0 CBC)",
        "LUCKY13":      "LUCKY13 attack (CBC timing)",
        "RC4":          "RC4 cipher in use — broken cipher",
        "FREAK":        "FREAK attack — export cipher suites accepted",
        "LOGJAM":       "LOGJAM attack — weak DH parameters",
        "DROWN":        "DROWN attack — SSLv2 oracle",
        "SWEET32":      "SWEET32 — 64-bit block cipher in use",
        "cert_expired": "TLS certificate has expired",
        "cert_notCA":   "Certificate not issued by trusted CA",
        "HSTS":         "HSTS header missing or misconfigured",
    }
    return titles.get(finding_id, f"TLS issue: {finding_text[:80]}")


def _remediation(finding_id: str) -> str:
    rems = {
        "SSLv2":   "Disable SSLv2 immediately. It is cryptographically broken.",
        "SSLv3":   "Disable SSLv3. Enable TLS 1.2+ only.",
        "TLS1":    "Disable TLS 1.0. Configure server to require TLS 1.2 minimum.",
        "TLS1_1":  "Disable TLS 1.1. Configure server to require TLS 1.2 minimum.",
        "heartbleed": "Patch OpenSSL to ≥1.0.1g. Rotate all private keys and certificates.",
        "RC4":     "Remove RC4 from cipher suite configuration. Use ECDHE+AES-GCM.",
        "FREAK":   "Disable export cipher suites. Ensure server rejects EXPORT-grade keys.",
        "LOGJAM":  "Use 2048-bit DH parameters or switch to ECDHE key exchange.",
        "HSTS":    "Add Strict-Transport-Security: max-age=31536000; includeSubDomains; preload",
    }
    return rems.get(finding_id, "Review and remediate the identified TLS/SSL configuration weakness.")
