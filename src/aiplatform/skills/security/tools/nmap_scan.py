"""
Tool wrapper: nmap
Port and service discovery against the target host.
Scans common web ports only — not a full port range scan.
Falls back to [] if nmap is not installed.
"""

import shutil
import subprocess
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


_WEB_PORTS = "80,443,8080,8443,8000,8001,3000,3001,5000,5001,9090,9443"


def tool_available() -> bool:
    return shutil.which("nmap") is not None


def run_nmap(
    target_url: str,
    scope_domain: str,
    timeout: int = 300,
) -> list[dict]:
    """
    Scan the target host for open ports and service versions.
    Uses -sV for version detection and common HTTP scripts.
    Returns a list of normalised findings (open ports with services).
    """
    if not tool_available():
        return []

    host = urlparse(target_url).hostname or scope_domain

    cmd = [
        "nmap",
        "-sV",                          # service/version detection
        "-T3",                          # normal timing (not aggressive)
        f"-p{_WEB_PORTS}",              # common web ports only
        "--script", "http-headers,http-title,http-methods",
        "--open",                       # only show open ports
        "-oX", "-",                     # XML output to stdout
        "--host-timeout", "90s",
        host,
    ]

    timed_out = False
    stdout = ""
    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout
    except subprocess.TimeoutExpired as exc:
        if exc.process:
            exc.process.kill()
        timed_out = True
    except Exception:
        return []

    findings = _parse_xml(stdout, target_url)
    if timed_out:
        findings.append({
            "tool": "nmap",
            "title": f"nmap scan timed out after {timeout // 60} min — partial results only",
            "severity": "Info",
            "category": "Scan Metadata",
            "description": f"The nmap scan exceeded its {timeout // 60}-minute timeout. Port findings shown are partial.",
            "url": target_url,
            "evidence": f"Timeout after {timeout}s",
            "cvss_estimate": 0.0,
            "fix": "",
            "tags": ["timeout", "scan-metadata"],
        })
    return findings


def _parse_xml(xml_output: str, target_url: str) -> list[dict]:
    findings = []
    if not xml_output.strip():
        return findings

    try:
        root = ET.fromstring(xml_output)
    except ET.ParseError:
        return findings

    for host in root.findall("host"):
        ports_el = host.find("ports")
        if ports_el is None:
            continue

        for port_el in ports_el.findall("port"):
            state_el = port_el.find("state")
            if state_el is None or state_el.get("state") != "open":
                continue

            portid = port_el.get("portid", "?")
            protocol = port_el.get("protocol", "tcp")

            service_el = port_el.find("service")
            service_name = ""
            product = ""
            version = ""
            if service_el is not None:
                service_name = service_el.get("name", "")
                product = service_el.get("product", "")
                version = service_el.get("version", "")

            # Extract script output (http-title, http-methods)
            script_evidence = []
            for script_el in port_el.findall("script"):
                sid = script_el.get("id", "")
                output = script_el.get("output", "")
                if output:
                    script_evidence.append(f"{sid}: {output}")

            description = f"Port {portid}/{protocol} is open"
            if product:
                description += f" — {product}"
                if version:
                    description += f" {version}"
            if service_name:
                description += f" ({service_name})"

            severity, cvss = _classify_port(portid, service_name, product, version)

            findings.append({
                "tool": "nmap",
                "title": f"Open port {portid}/{protocol}: {product or service_name or 'unknown'}",
                "severity": severity,
                "category": "Network Exposure",
                "description": description,
                "url": target_url,
                "evidence": "\n".join(script_evidence) if script_evidence else description,
                "cvss_estimate": cvss,
                "fix": _remediation(portid, service_name, product),
                "tags": ["network", "port-scan"],
            })

    return findings


def _classify_port(portid: str, service: str, product: str, version: str) -> tuple[str, float]:
    """Return (severity, cvss_estimate) based on port/service context."""
    combined = f"{service} {product} {version}".lower()

    # High-risk: non-web services on a web server
    if portid in ("21", "22", "23", "25", "110", "143", "3306", "5432", "6379", "27017"):
        return "High", 7.5

    # Outdated/vulnerable versions
    if any(v in combined for v in ("1.0", "1.1", "5.0", "5.1", "2.2", "2.4.49", "2.4.50")):
        return "Medium", 6.0

    # Unencrypted HTTP on non-standard port (not 80)
    if "http" in combined and portid not in ("80", "443"):
        return "Low", 3.5

    return "Info", 1.0


def _remediation(portid: str, service: str, product: str) -> str:
    if portid == "21":
        return "Disable FTP — use SFTP or SCP instead. FTP transmits credentials in plaintext."
    if portid == "22":
        return "Restrict SSH access to trusted IP ranges. Disable password auth, use key-based only."
    if portid in ("3306", "5432"):
        return "Database port is publicly accessible. Restrict to localhost or private network only."
    if portid == "6379":
        return "Redis is exposed. Bind to 127.0.0.1 and require authentication."
    return f"Review whether port {portid} needs to be publicly accessible. Apply firewall rules to restrict access."
