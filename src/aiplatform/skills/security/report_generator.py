"""
Phase 6 — Security Audit Report Generation Skill

Receives aggregated findings from all active phases, sends them to the Claude API
for correlation and narrative generation, then renders a PDF via Playwright.

Claude produces:
  - Deduplicated, prioritised findings with CVSS scores
  - Attack chain narratives
  - Executive summary in plain business language
  - Remediation roadmap

The PDF is generated from an HTML template using Playwright (same approach as
the marketing audit report).
"""

import json
from datetime import datetime
from pathlib import Path

import anthropic


# ── Public entry point ─────────────────────────────────────────────────────────

def generate_security_report(
    audit_data: dict,
    output_path: str,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """
    Call Claude API to correlate findings and generate the report PDF.

    Args:
        audit_data:  Dict containing target info, phase results, tier, etc.
        output_path: Absolute path for the output PDF.
        model:       Claude model to use.

    Returns:
        {"pdf_path": str, "report_data": dict, "size_bytes": int,
         "findings_count": int, "risk_score": int}
    """
    report_data = _correlate_with_claude(audit_data, model)
    pdf_path = _render_pdf(report_data, output_path)
    size = Path(pdf_path).stat().st_size

    return {
        "pdf_path": pdf_path,
        "report_data": report_data,
        "size_bytes": size,
        "findings_count": len(report_data.get("findings", [])),
        "risk_score": report_data.get("overall_risk_score", 0),
    }


# ── Claude API correlation ────────────────────────────────────────────────────

def _correlate_with_claude(audit_data: dict, model: str) -> dict:
    client = anthropic.Anthropic()
    prompt = _build_correlation_prompt(audit_data)

    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=(
            "You are a senior penetration tester and security analyst writing a "
            "professional security audit report. You have deep expertise in OWASP, "
            "CVSS scoring, and communicating risk to both technical and non-technical "
            "stakeholders. Respond with valid JSON only — no markdown, no commentary."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned invalid JSON: {exc}\n\nRaw:\n{raw[:500]}")

    # Inject metadata
    report.setdefault("target_url", audit_data.get("target_url", ""))
    report.setdefault("target_domain", audit_data.get("target_domain", ""))
    report.setdefault("tier", audit_data.get("tier", "starter"))
    report.setdefault("audit_date", datetime.now().strftime("%B %d, %Y"))
    report.setdefault("findings", [])
    report.setdefault("attack_chains", [])
    report.setdefault("quick_wins", [])
    report.setdefault("medium_term", [])
    report.setdefault("strategic", [])
    report.setdefault("overall_risk_score", 0)

    return report


def _build_correlation_prompt(audit_data: dict) -> str:
    target = audit_data.get("target_url", "")
    tier = audit_data.get("tier", "starter")
    phase1 = audit_data.get("phase1_recon", {})
    phase2 = audit_data.get("phase2_surface", {})
    phase3 = audit_data.get("phase3_vuln", {})

    # Compact the raw data so it fits in context
    recon_summary = _summarise_recon(phase1)
    surface_summary = _summarise_surface(phase2)
    vuln_summary = _summarise_vulns(phase3)

    scope_note = {
        "starter": "Phases 1–3 only (passive OSINT + surface mapping + header/TLS/CORS analysis)",
        "professional": "All 5 phases including authenticated Playwright testing",
        "agency": "Full scan, multi-subdomain scope, white-label output",
    }.get(tier, "Phases 1–3")

    return f"""
You are producing a security audit report for: {target}
Audit tier: {tier.upper()} — {scope_note}

AGGREGATED FINDINGS FROM ALL PHASES:

{recon_summary}

{surface_summary}

{vuln_summary}

TASK:
1. Deduplicate overlapping findings (same vulnerability from different phases = one finding)
2. Assign accurate CVSS 3.1 base scores — use the full range, don't cluster at 7.0
3. Group findings into attack chains where individual issues combine into a multi-step attack
4. Write an executive summary in plain language (2-3 paragraphs, no jargon, business risk focus)
5. Produce a risk-prioritised remediation roadmap

Return a JSON object matching this exact schema:

{{
  "executive_summary": "string — 2-3 paragraphs, plain language, business risk framing",
  "overall_risk_score": 0-100,
  "risk_rating": "Critical | High | Medium | Low | Minimal",
  "findings": [
    {{
      "id": "F-001",
      "category": "string — OWASP category (e.g. Security Misconfiguration, Injection)",
      "title": "string — concise finding title",
      "severity": "Critical | High | Medium | Low | Informational",
      "cvss_score": 0.0-10.0,
      "description": "string — what is wrong and why it matters",
      "evidence": "string — what was observed during the scan",
      "impact": "string — business consequence if exploited",
      "fix": "string — specific, actionable remediation steps",
      "effort": "Low | Medium | High"
    }}
  ],
  "attack_chains": [
    {{
      "title": "string — attack chain name",
      "severity": "Critical | High | Medium",
      "steps": ["string — step 1", "string — step 2"],
      "impact": "string — combined impact of the chain",
      "finding_ids": ["F-001", "F-003"]
    }}
  ],
  "quick_wins": ["string — specific action (under 1 day)"],
  "medium_term": ["string — action (1-4 weeks)"],
  "strategic": ["string — longer-term initiative"],
  "compliance_notes": {{
    "owasp_top_10": ["string — relevant OWASP category"],
    "gdpr_relevant": true,
    "soc2_relevant": true
  }}
}}
"""


def _summarise_recon(phase1: dict) -> str:
    if not phase1:
        return "PHASE 1 (Passive Recon): Not run or no data."
    lines = ["--- PHASE 1: PASSIVE OSINT RECON ---"]
    lines.append(f"Subdomains discovered: {len(phase1.get('subdomains', []))} "
                 f"({', '.join(phase1.get('subdomains', [])[:10])})")
    ip = phase1.get("ip_info", {})
    if ip:
        lines.append(f"IP: {ip.get('ip')} | ASN: {ip.get('asn')} | Org: {ip.get('org')}")
    spf = phase1.get("spf_dmarc", {})
    if spf.get("issues"):
        lines.append(f"Email security issues: {spf['issues']}")
    breaches = phase1.get("breach_info", {})
    if breaches.get("breaches_found", 0) > 0:
        lines.append(f"HIBP breaches: {breaches['breaches_found']} breach(es) found")
    wayback = phase1.get("wayback_urls", [])
    if wayback:
        lines.append(f"Historical URLs (Wayback): {len(wayback)} endpoints found")
    errors = phase1.get("errors", [])
    if errors:
        lines.append(f"Recon errors: {errors}")
    return "\n".join(lines)


def _summarise_surface(phase2: dict) -> str:
    if not phase2:
        return "PHASE 2 (Surface Mapping): Not run or no data."
    lines = ["--- PHASE 2: ATTACK SURFACE MAPPING ---"]
    baseline = phase2.get("target_baseline", {})
    lines.append(f"HTTPS enforced: {baseline.get('https_enforced', False)}")
    lines.append(f"Server: {baseline.get('server', 'unknown')}")
    lines.append(f"Tech stack: {phase2.get('tech_stack', [])}")
    exposed = phase2.get("exposed_paths", [])
    if exposed:
        lines.append(f"Exposed paths ({len(exposed)}):")
        for p in exposed:
            lines.append(f"  [{p.get('severity')}] {p.get('path')} — HTTP {p.get('status')}")
    live_subs = phase2.get("live_subdomains", [])
    if live_subs:
        lines.append(f"Live subdomains: {[s.get('subdomain') for s in live_subs]}")
    robots = phase2.get("robots_txt", "")
    if robots:
        lines.append(f"robots.txt Disallow paths: {phase2.get('robots_disallowed_paths', [])}")
    return "\n".join(lines)


def _summarise_vulns(phase3: dict) -> str:
    if not phase3:
        return "PHASE 3 (Vulnerability Scan): Not run or no data."
    lines = ["--- PHASE 3: AUTOMATED VULNERABILITY SCAN ---"]

    # Headers
    header_audit = phase3.get("header_audit", {})
    failed_headers = [h for h, d in header_audit.items()
                      if not h.startswith("_") and d.get("severity") not in ("Pass", "")]
    if failed_headers:
        lines.append(f"Failed security headers: {failed_headers}")

    leak_hdrs = header_audit.get("_info_leak_headers", {})
    if leak_hdrs:
        lines.append(f"Version-leaking headers: {leak_hdrs}")

    # TLS
    tls = phase3.get("tls_audit", {})
    if tls.get("issues"):
        lines.append(f"TLS issues: {tls['issues']}")
    else:
        lines.append(f"TLS version: {tls.get('tls_version', 'unknown')} — "
                     f"Cipher: {tls.get('cipher_suite', 'unknown')}")

    # CORS
    cors = phase3.get("cors_issues", [])
    if cors:
        for c in cors:
            lines.append(f"CORS [{c.get('severity')}]: {c.get('description')}")

    # Cookies
    cookies = phase3.get("cookie_issues", [])
    if cookies:
        for ck in cookies:
            lines.append(f"Cookie '{ck.get('name')}' [{ck.get('severity')}]: "
                         f"{'; '.join(ck.get('issues', []))}")

    # Findings count
    lines.append(f"Total raw findings from Phase 3: {len(phase3.get('findings', []))}")
    for f in phase3.get("findings", []):
        lines.append(f"  [{f.get('severity')}] {f.get('title')}")

    return "\n".join(lines)


# ── PDF rendering ─────────────────────────────────────────────────────────────

def _render_pdf(report_data: dict, output_path: str) -> str:
    tpl_path = Path(__file__).parent / "report_template.html"
    with open(tpl_path, "r", encoding="utf-8") as f:
        html = f.read()

    html = _inject_report_data(html, report_data)

    from playwright.sync_api import sync_playwright
    output_p = Path(output_path)
    output_p.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(output_p),
            print_background=True,
            format="A4",
            margin={"top": "0.5in", "bottom": "0.5in", "left": "0in", "right": "0in"},
        )
        browser.close()

    return str(output_p)


def _html_escape(text: str) -> str:
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _inject_report_data(html: str, data: dict) -> str:
    """Substitute all {{ placeholders }} in the template."""
    from datetime import datetime

    score = data.get("overall_risk_score", 0)
    rating = data.get("risk_rating", "Unknown")
    rating_color = {
        "Critical": "text-red-600",
        "High": "text-orange-500",
        "Medium": "text-yellow-600",
        "Low": "text-green-600",
        "Minimal": "text-blue-500",
    }.get(rating, "text-on-surface")

    # Findings HTML
    findings_html = ""
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Informational": 4}
    findings = sorted(data.get("findings", []),
                      key=lambda f: severity_order.get(f.get("severity", "Low"), 5))
    for f in findings:
        sev = f.get("severity", "Medium")
        sev_color = {
            "Critical": "text-red-600", "High": "text-orange-500",
            "Medium": "text-yellow-600", "Low": "text-green-600",
        }.get(sev, "text-on-surface")
        cvss = f.get("cvss_score", "")
        findings_html += f"""
        <div class="bg-surface-container-lowest p-5 rounded-xl border border-surface-container shadow-sm space-y-3 break-inside-avoid">
            <div class="flex items-center justify-between">
                <span class="text-xs font-bold {sev_color} uppercase tracking-wide">{_html_escape(sev)}</span>
                <span class="text-xs font-label text-on-surface-variant">CVSS {cvss}</span>
            </div>
            <div>
                <span class="text-[9px] font-label font-bold uppercase tracking-widest text-on-surface-variant/60">Finding</span>
                <p class="text-sm font-headline font-semibold text-primary mt-0.5">{_html_escape(f.get('title', ''))}</p>
            </div>
            <div>
                <span class="text-[9px] font-label font-bold uppercase tracking-widest text-on-surface-variant/60">Description</span>
                <p class="text-xs font-body text-on-surface-variant mt-0.5">{_html_escape(f.get('description', ''))}</p>
            </div>
            <div>
                <span class="text-[9px] font-label font-bold uppercase tracking-widest text-on-surface-variant/60">Impact</span>
                <p class="text-xs font-body text-on-surface-variant mt-0.5">{_html_escape(f.get('impact', ''))}</p>
            </div>
            <div>
                <span class="text-[9px] font-label font-bold uppercase tracking-widest text-on-surface-variant/60">Remediation</span>
                <p class="text-xs font-body text-on-surface mt-0.5">{_html_escape(f.get('fix', ''))}</p>
            </div>
        </div>
        """

    # Attack chains HTML
    chains_html = ""
    for chain in data.get("attack_chains", []):
        steps_html = "".join(
            f'<li class="text-xs font-body text-on-surface-variant">{_html_escape(s)}</li>'
            for s in chain.get("steps", [])
        )
        sev = chain.get("severity", "High")
        sev_color = {"Critical": "text-red-600", "High": "text-orange-500",
                     "Medium": "text-yellow-600"}.get(sev, "text-on-surface")
        chains_html += f"""
        <div class="bg-surface-container-lowest border border-surface-container rounded-xl p-6 break-inside-avoid">
            <div class="flex items-center gap-3 mb-3">
                <span class="material-symbols-outlined {sev_color}">warning</span>
                <h3 class="font-headline font-bold text-primary">{_html_escape(chain.get('title', ''))}</h3>
                <span class="text-xs font-bold {sev_color} uppercase ml-auto">{_html_escape(sev)}</span>
            </div>
            <ol class="list-decimal list-inside space-y-1 mb-3">{steps_html}</ol>
            <p class="text-xs font-body text-on-surface-variant italic">{_html_escape(chain.get('impact', ''))}</p>
        </div>
        """

    # Roadmap HTML
    def roadmap_phase(title: str, items: list, color: str) -> str:
        if not items:
            return ""
        lines = "".join(
            f'<div class="flex gap-3 items-start"><span class="material-symbols-outlined {color} text-sm mt-0.5">check_box_outline_blank</span>'
            f'<p class="text-xs font-bold text-primary">{_html_escape(str(i))}</p></div>'
            for i in items
        )
        return f"""
        <div class="bg-surface-container-lowest border border-surface-container rounded-xl overflow-hidden flex flex-col sm:flex-row break-inside-avoid shadow-sm">
            <div class="p-6 sm:w-1/4 flex flex-col justify-center border-r border-surface-container bg-surface-container/30">
                <h3 class="text-lg font-headline font-bold text-primary">{title}</h3>
            </div>
            <div class="p-6 grid grid-cols-2 gap-4 flex-grow">{lines}</div>
        </div>
        """

    roadmap_html = (
        roadmap_phase("Quick Wins", data.get("quick_wins", []), "text-secondary")
        + roadmap_phase("Medium-Term", data.get("medium_term", []), "text-primary")
        + roadmap_phase("Strategic", data.get("strategic", []), "text-on-surface-variant")
    )

    # Category summary (finding counts per severity)
    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Informational": 0}
    for f in findings:
        sev = f.get("severity", "Low")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    summary_html = "".join(
        f"""<div class="text-center">
            <div class="text-3xl font-headline font-bold {
                {'Critical': 'text-red-600', 'High': 'text-orange-500',
                 'Medium': 'text-yellow-600', 'Low': 'text-green-600',
                 'Informational': 'text-blue-500'}.get(sev, 'text-on-surface')
            }">{count}</div>
            <div class="text-xs font-label text-on-surface-variant mt-1">{sev}</div>
        </div>"""
        for sev, count in severity_counts.items()
    )

    replacements = {
        "{{ target_url }}": _html_escape(data.get("target_url", "")),
        "{{ target_domain }}": _html_escape(data.get("target_domain", "")),
        "{{ audit_date }}": _html_escape(data.get("audit_date", "")),
        "{{ tier }}": _html_escape(data.get("tier", "").title()),
        "{{ overall_risk_score }}": str(score),
        "{{ risk_rating }}": _html_escape(rating),
        "{{ rating_color }}": rating_color,
        "{{ executive_summary }}": _html_escape(data.get("executive_summary", "")),
        "{{ severity_summary_html }}": summary_html,
        "{{ findings_html }}": findings_html,
        "{{ attack_chains_html }}": chains_html,
        "{{ roadmap_html }}": roadmap_html,
        "{{ total_findings }}": str(len(findings)),
    }

    for k, v in replacements.items():
        html = html.replace(k, v)

    return html
