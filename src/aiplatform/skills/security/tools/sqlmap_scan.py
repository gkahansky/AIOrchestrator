"""
Tool wrapper: sqlmap
SQL injection detection and confirmation.
Phase 4 only — Professional and Agency tiers.
Falls back to [] if sqlmap is not installed.

Configuration: --level=2 --risk=1 prevents destructive tests.
Never uses --dbs, --dump, or --os-shell — detection only.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def tool_available() -> bool:
    return shutil.which("sqlmap") is not None


def run_sqlmap(
    target_url: str,
    scope_domain: str,
    urls_with_params: list[str] | None = None,
    work_dir: str | None = None,
    timeout: int = 300,
) -> list[dict]:
    """
    Run sqlmap to detect (not exploit) SQL injection vulnerabilities.

    Tests the primary target URL and any discovered URLs with parameters.
    Uses --level=2 --risk=1 for non-destructive detection.
    Uses --crawl=1 to discover additional injection points on the page.

    Args:
        target_url:       Primary target URL.
        scope_domain:     Validated scope domain.
        urls_with_params: Additional URLs with parameters from Phase 2 discovery.
        work_dir:         Directory for sqlmap output.
        timeout:          Total timeout in seconds.

    Returns:
        List of confirmed SQL injection finding dicts.
    """
    if not tool_available():
        return []

    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    sqlmap_out = tmp / "sqlmap"
    sqlmap_out.mkdir(exist_ok=True)

    targets = [target_url]
    if urls_with_params:
        targets += [u for u in urls_with_params if scope_domain in u and "?" in u]
    # Deduplicate and cap at 5 URLs to keep runtime reasonable
    targets = list(dict.fromkeys(targets))[:5]

    findings = []
    per_url_timeout = max(60, timeout // len(targets))

    for url in targets:
        result = _scan_url(url, sqlmap_out, per_url_timeout)
        findings.extend(result)

    return findings


def _scan_url(url: str, output_dir: Path, timeout: int) -> list[dict]:
    cmd = [
        "sqlmap",
        "-u", url,
        "--batch",              # non-interactive, use defaults
        "--level=2",            # test level (1-5): 2 covers headers + cookies
        "--risk=1",             # risk level (1-3): 1 = safe, non-destructive
        "--forms",              # also test forms on the page
        "--crawl=1",            # crawl one level deep
        "--timeout=20",         # per-request timeout
        "--retries=0",          # no retries (keep it fast)
        "--output-dir", str(output_dir),
        "--flush-session",      # fresh session for each run
        "--technique=BEUS",     # Boolean, Error, Union, Stacked (no time-based by default)
        "--no-logging",
    ]

    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        stdout = ""
    except Exception:
        return []

    return _parse_output(stdout, url)


def _parse_output(output: str, url: str) -> list[dict]:
    findings = []

    # sqlmap announces injection points with "Parameter: X (TYPE) is vulnerable"
    # and "Type: <injection type>"
    injection_blocks = re.findall(
        r"Parameter:\s*(.+?)\s*\((.+?)\).*?is vulnerable.*?Type:\s*(.+?)[\r\n]",
        output,
        re.DOTALL | re.IGNORECASE,
    )

    for param, param_type, injection_type in injection_blocks:
        param = param.strip()
        injection_type = injection_type.strip()
        severity, cvss = _classify_injection(injection_type)

        # Extract the payload line if present
        payload_match = re.search(r"Payload:\s*(.+)", output)
        payload = payload_match.group(1).strip() if payload_match else ""

        findings.append({
            "tool": "sqlmap",
            "title": f"SQL Injection — parameter: {param}",
            "severity": severity,
            "category": "Injection",
            "description": (
                f"sqlmap confirmed a SQL injection vulnerability in the '{param}' parameter "
                f"({param_type}). Injection type: {injection_type}. "
                f"An attacker can read, modify, or delete database contents."
            ),
            "url": url,
            "evidence": f"Parameter: {param} ({param_type})\nType: {injection_type}"
                        + (f"\nPayload: {payload}" if payload else ""),
            "cvss_estimate": cvss,
            "fix": (
                "Use parameterised queries or prepared statements — never concatenate user input into SQL. "
                "Apply an ORM with proper escaping. "
                "Restrict database user permissions to only what the application requires."
            ),
            "tags": ["sqli", "injection", "sqlmap", "confirmed"],
            "param": param,
            "injection_type": injection_type,
        })

    return findings


def _classify_injection(injection_type: str) -> tuple[str, float]:
    t = injection_type.lower()
    if "union" in t or "stacked" in t:
        return "Critical", 9.8  # Direct data extraction
    if "boolean" in t or "error" in t:
        return "High", 8.5       # Confirmed but blind/error-based
    if "time" in t:
        return "High", 7.5       # Time-based blind — slower to exploit
    return "High", 7.5
