"""
Tool wrapper: nikto
Web server misconfiguration and vulnerability scanner.
Falls back to [] if nikto is not installed.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


_SEVERITY_CVSS = {"Critical": 9.0, "High": 7.5, "Medium": 5.0, "Low": 3.0}


def tool_available() -> bool:
    return shutil.which("nikto") is not None


def run_nikto(
    target_url: str,
    scope_domain: str,
    work_dir: str | None = None,
    timeout: int = 600,
) -> list[dict]:
    """
    Run nikto against the target URL.
    Outputs JSON and normalises into the standard finding dict.
    """
    if not tool_available():
        return []

    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    out_file = tmp / "nikto-output.json"

    cmd = [
        "nikto",
        "-host", target_url,
        "-Format", "json",
        "-output", str(out_file),
        "-nointeractive",
        "-timeout", "20",
        # Tuning: focus on interesting checks, skip slow brute-force
        # 1=Interesting, 2=Misconfig, 3=Info disclosure, 4=Injection, 5=Remote file retrieval,
        # 6=Denial of Service (skip), 7=Remote file retrieval (2), 8=Command execution, 9=SQL injection
        "-Tuning", "1234589",
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

    findings = _parse_output(out_file, target_url)
    if timed_out:
        findings.append({
            "tool": "nikto",
            "title": f"nikto scan timed out after {timeout // 60} min — partial results only",
            "severity": "Info",
            "category": "Scan Metadata",
            "description": f"The nikto scan exceeded its {timeout // 60}-minute timeout. Findings shown are partial.",
            "url": target_url,
            "evidence": f"Timeout after {timeout}s",
            "cvss_estimate": 0.0,
            "fix": "",
            "tags": ["timeout", "scan-metadata"],
        })
    return findings


def _parse_output(out_file: Path, target_url: str) -> list[dict]:
    findings = []
    if not out_file.exists():
        return findings

    try:
        data = json.loads(out_file.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return findings

    # Nikto JSON: {"host": {...}, "vulnerabilities": [...]}
    # or a list of host objects
    if isinstance(data, dict):
        vulns = data.get("vulnerabilities", [])
    elif isinstance(data, list) and data:
        vulns = data[0].get("vulnerabilities", []) if isinstance(data[0], dict) else []
    else:
        return findings

    for v in vulns:
        msg = v.get("msg", "")
        if not msg:
            continue

        severity = _classify_nikto_message(msg)
        url = v.get("url", target_url)
        method = v.get("method", "GET")

        findings.append({
            "tool": "nikto",
            "title": _short_title(msg),
            "severity": severity,
            "category": "Security Misconfiguration",
            "description": msg,
            "url": url,
            "evidence": f"{method} {url}",
            "cvss_estimate": _SEVERITY_CVSS.get(severity, 3.0),
            "fix": "Review and remediate the identified server configuration issue.",
            "tags": ["nikto", "misconfiguration"],
            "osvdb": v.get("osvdbid", ""),
        })

    return findings


def _classify_nikto_message(msg: str) -> str:
    msg_lower = msg.lower()
    if any(k in msg_lower for k in ("remote file include", "command execution", "sql injection",
                                     "buffer overflow", "arbitrary file", "rce")):
        return "Critical"
    if any(k in msg_lower for k in ("allowed methods", "put", "delete", "directory index",
                                     "sensitive file", "backup", "config", "phpinfo",
                                     "default account", "default password")):
        return "High"
    if any(k in msg_lower for k in ("x-frame", "content-security", "x-powered-by",
                                     "server header", "etag", "clickjack")):
        return "Medium"
    return "Low"


def _short_title(msg: str) -> str:
    """Return the first sentence of the nikto message as a title."""
    first = msg.split(".")[0].split(":")[0].strip()
    return first[:120] if first else "Nikto finding"
