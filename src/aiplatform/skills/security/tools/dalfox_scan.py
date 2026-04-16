"""
Tool wrapper: dalfox
XSS (Cross-Site Scripting) scanner and PoC generator.
Phase 4 only — Professional and Agency tiers.
Falls back to [] if dalfox is not installed.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def tool_available() -> bool:
    return shutil.which("dalfox") is not None


def run_dalfox(
    target_url: str,
    scope_domain: str,
    urls_with_params: list[str] | None = None,
    work_dir: str | None = None,
    rate_limit_ms: int = 300,
    timeout: int = 180,
) -> list[dict]:
    """
    Scan for XSS vulnerabilities using dalfox.

    Args:
        target_url:       Primary target URL.
        scope_domain:     Validated scope domain — dalfox is constrained to this.
        urls_with_params: Additional URLs with query parameters discovered in Phase 2.
                          dalfox tests each parameter independently.
        work_dir:         Directory to write output files.
        rate_limit_ms:    Milliseconds between requests (default 300 = ~3 req/s).
        timeout:          Total timeout in seconds for the scan.

    Returns:
        List of normalised XSS finding dicts with PoC payload.
    """
    if not tool_available():
        return []

    targets = [target_url]
    if urls_with_params:
        # Only include in-scope URLs
        targets += [u for u in urls_with_params if scope_domain in u]

    tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    out_file = tmp / "dalfox-output.json"

    # Write target list to file for batch mode
    target_file = tmp / "dalfox-targets.txt"
    target_file.write_text("\n".join(targets), encoding="utf-8")

    cmd = [
        "dalfox", "file", str(target_file),
        "--output", str(out_file),
        "--format", "json",
        "--silence",
        "--no-spinner",
        "--timeout", "10",
        "--delay", str(rate_limit_ms),
        "--skip-bav",                # skip BAV analysis (faster)
        "--only-poc", "g",           # only generate GET PoC
        "--worker", "2",             # 2 workers (low-noise)
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
        # dalfox JSON output: array of finding objects
        data = json.loads(out_file.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        # Try NDJSON (one object per line)
        data = []
        for line in out_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if isinstance(data, dict):
        data = [data]

    for item in data:
        xss_type = item.get("type", "XSS")
        poc = item.get("poc", item.get("PoC", ""))
        param = item.get("param", "")
        url = item.get("url", target_url)
        evidence = poc or url

        title = f"Cross-Site Scripting (XSS) — parameter: {param}" if param else "Cross-Site Scripting (XSS)"

        findings.append({
            "tool": "dalfox",
            "title": title,
            "severity": "High",
            "category": "Cross-Site Scripting",
            "description": (
                f"dalfox confirmed a {xss_type} XSS vulnerability. "
                f"The parameter '{param}' reflects unsanitised user input into the page. "
                f"An attacker can steal session cookies, redirect users, or perform actions on their behalf."
            ),
            "url": url,
            "evidence": evidence,
            "cvss_estimate": 7.2,
            "fix": (
                "HTML-encode all output: encode <, >, \", ', & before rendering in HTML context. "
                "Use a Content-Security-Policy to restrict script execution. "
                "Implement input validation on the server side."
            ),
            "tags": ["xss", "dalfox", "confirmed"],
            "poc": poc,
            "param": param,
        })

    return findings
