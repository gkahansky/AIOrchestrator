"""
Tool wrapper: nuclei
Runs the ProjectDiscovery nuclei scanner against a scoped target and returns
normalised findings. Falls back to [] if nuclei is not installed.

Phase 3 tags  (safe, non-intrusive): misconfigs, exposures, cves, technologies,
              panels, takeovers, headers, dns, ssl, default-logins
Phase 4 tags  (active, Professional/Agency only): sqli, xss, ssrf, ssti,
              traversal, injection, lfi, rfi, redirect

Never run: dos, fuzzing, bruteforce, intrusive
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

_SEVERITY_CVSS = {
    "critical": 9.5,
    "high": 7.5,
    "medium": 5.0,
    "low": 3.0,
    "info": 1.0,
}

# Phase 3 — safe recon/misconfiguration templates
_PHASE3_TAGS = "misconfigs,exposures,cves,technologies,panels,takeovers,headers,dns,ssl,default-logins"

# Phase 4 — active exploitation templates (Professional/Agency only)
_PHASE4_TAGS = "sqli,xss,ssrf,ssti,traversal,injection,lfi,rfi,redirect"

# Templates never to run (scope: no destructive or noisy activity)
_EXCLUDE_TAGS = "dos,fuzzing,bruteforce,intrusive,headless"


def tool_available() -> bool:
    return shutil.which("nuclei") is not None


def run_nuclei_phase3(
    target_url: str,
    scope_domain: str,
    work_dir: str | None = None,
    rate_limit: int = 10,
    timeout: int = 900,
) -> list[dict]:
    """
    Phase 3 — safe misconfiguration + exposure scanning.
    Runs misconfigs, CVE, and exposure templates. No active exploitation.
    """
    return _run(target_url, scope_domain, _PHASE3_TAGS, work_dir, rate_limit, timeout)


def run_nuclei_phase4(
    target_url: str,
    scope_domain: str,
    work_dir: str | None = None,
    rate_limit: int = 5,
    timeout: int = 600,
) -> list[dict]:
    """
    Phase 4 — active vulnerability confirmation.
    Runs injection, XSS, SSRF, traversal templates. Professional/Agency only.
    """
    return _run(target_url, scope_domain, _PHASE4_TAGS, work_dir, rate_limit, timeout)


def _run(
    target_url: str,
    scope_domain: str,
    tags: str,
    work_dir: str | None,
    rate_limit: int,
    timeout: int,
) -> list[dict]:
    if not tool_available():
        return []

    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    out_file = tmp / "nuclei-output.jsonl"

    cmd = [
        "nuclei",
        "-target", target_url,
        "-tags", tags,
        "-etags", _EXCLUDE_TAGS,
        "-json-export", str(out_file),
        "-rate-limit", str(rate_limit),
        "-timeout", "10",          # per-request timeout in seconds
        "-retries", "1",
        "-no-interactsh",          # no OAST callbacks — we have no interactsh server
        "-silent",
        "-no-color",
    ]

    timed_out = False
    try:
        subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        if exc.process:
            exc.process.kill()
        timed_out = True  # Partial results are still useful
    except Exception:
        return []

    findings = _parse_output(out_file)
    if timed_out:
        findings.append({
            "tool": "nuclei",
            "title": f"nuclei scan timed out after {timeout // 60} min — partial results only",
            "severity": "Info",
            "category": "Scan Metadata",
            "description": f"The nuclei scan exceeded its {timeout // 60}-minute timeout. Findings shown are partial.",
            "url": target_url,
            "evidence": f"Timeout after {timeout}s",
            "cvss_estimate": 0.0,
            "fix": "",
            "tags": ["timeout", "scan-metadata"],
        })
    return findings


def _parse_output(out_file: Path) -> list[dict]:
    findings = []
    if not out_file.exists():
        return findings

    for line in out_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue

        info = raw.get("info", {})
        severity = info.get("severity", "info").lower()

        # Skip pure-informational findings — they inflate the report without actionable value
        if severity == "info":
            continue

        findings.append({
            "tool": "nuclei",
            "title": info.get("name", raw.get("template-id", "Unknown")),
            "severity": severity.capitalize(),
            "category": _map_category(info.get("tags", [])),
            "description": info.get("description", ""),
            "url": raw.get("matched-at", raw.get("host", "")),
            "evidence": raw.get("extracted-results", raw.get("matched-at", "")),
            "cvss_estimate": _cvss_from_info(info, severity),
            "fix": _extract_fix(info),
            "tags": info.get("tags", []),
            "template_id": raw.get("template-id", ""),
        })

    return findings


def _cvss_from_info(info: dict, severity: str) -> float:
    # Use nuclei's classification CVSS if present
    classification = info.get("classification", {})
    cvss = classification.get("cvss-score")
    if cvss:
        try:
            return float(cvss)
        except (TypeError, ValueError):
            pass
    return _SEVERITY_CVSS.get(severity, 3.0)


def _extract_fix(info: dict) -> str:
    remediation = info.get("remediation", "")
    if remediation:
        return remediation
    refs = info.get("reference", [])
    if refs:
        return f"See: {refs[0]}"
    return "Review and remediate the identified configuration or vulnerability."


def _map_category(tags: list) -> str:
    tag_set = {t.lower() for t in tags}
    if tag_set & {"sqli", "sql-injection"}:
        return "Injection"
    if tag_set & {"xss", "cross-site-scripting"}:
        return "Cross-Site Scripting"
    if tag_set & {"ssrf"}:
        return "Server-Side Request Forgery"
    if tag_set & {"cve"}:
        return "Known CVE"
    if tag_set & {"misconfig", "misconfiguration", "misconfigs"}:
        return "Security Misconfiguration"
    if tag_set & {"exposure", "exposures"}:
        return "Sensitive Exposure"
    if tag_set & {"panel", "panels"}:
        return "Exposed Admin Panel"
    if tag_set & {"takeover", "takeovers"}:
        return "Subdomain Takeover"
    if tag_set & {"default-login"}:
        return "Default Credentials"
    return "Vulnerability"
