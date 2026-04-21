import sys

content = r'''"""
Skill: generate_accessibility_report
Render a PDF summary for an accessibility audit using Playwright and an HTML template.

Input:
    audit_data   (dict): axe scan result payload.
    output_path  (str):  Path to the PDF to create.
"""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright

WCAG_MAP = {
    "1.1.1": ("1.1.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html"),
    "1.2.1": ("1.2.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/audio-only-and-video-only-prerecorded.html"),
    "1.2.2": ("1.2.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html"),
    "1.3.1": ("1.3.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships.html"),
    "1.3.5": ("1.3.5 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/identify-input-purpose.html"),
    "1.4.1": ("1.4.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html"),
    "1.4.3": ("1.4.3 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html"),
    "1.4.4": ("1.4.4 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html"),
    "1.4.11": ("1.4.11 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html"),
    "1.4.12": ("1.4.12 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html"),
    "2.1.1": ("2.1.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html"),
    "2.2.1": ("2.2.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html"),
    "2.2.2": ("2.2.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html"),
    "2.4.1": ("2.4.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/bypass-blocks.html"),
    "2.4.2": ("2.4.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/page-titled.html"),
    "2.4.4": ("2.4.4 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html"),
    "2.4.6": ("2.4.6 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/headings-and-labels.html"),
    "2.4.7": ("2.4.7 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html"),
    "3.1.1": ("3.1.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/language-of-page.html"),
    "3.1.2": ("3.1.2 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/language-of-parts.html"),
    "3.2.2": ("3.2.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/on-input.html"),
    "3.3.2": ("3.3.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html"),
    "4.1.1": ("4.1.1 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/parsing.html"),
    "4.1.2": ("4.1.2 (Level A)", "https://www.w3.org/WAI/WCAG22/Understanding/name-role-value.html"),
    "4.1.3": ("4.1.3 (Level AA)", "https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html"),
}

def _html_escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def _map_impact_to_severity(impact: str) -> str:
    mapping = {"minor": "Low", "moderate": "Medium", "serious": "High", "critical": "Critical"}
    return mapping.get(impact, "Medium")

def _get_severity_order(severity: str) -> int:
    return {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}.get(severity, 5)

def _get_wcag_principle(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("wcag1"): return "1. Perceivable"
        elif tag.startswith("wcag2"): return "2. Operable"
        elif tag.startswith("wcag3"): return "3. Understandable"
        elif tag.startswith("wcag4"): return "4. Robust"
    return "Other Principles"

def _get_wcag_criteria(tags: list[str], rule_id: str) -> str:
    for tag in tags:
        if tag.startswith("wcag") and len(tag) >= 7:
            criteria = tag.replace("wcag", "")
            if len(criteria) >= 3 and criteria[:3].isdigit():
                return f"{criteria[0]}.{criteria[1]}.{criteria[2:]}"
    return rule_id

# Map severity to CSS classes matching DESIGN.md
SEV_CLASSES = {
    "Critical": "bg-error/10 text-error",
    "High": "bg-tertiary/10 text-tertiary",
    "Medium": "bg-primary/10 text-primary",
    "Low": "bg-secondary-container text-on-secondary-container"
}

def generate_accessibility_report(audit_data: dict, output_path: str, tier: str = "standard") -> dict:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    violations = audit_data.get("violations", []) or []
    incomplete = audit_data.get("incomplete", []) or []
    passes = audit_data.get("passes", []) or []
    wcag_score = audit_data.get("wcag_score", 0)
    url = audit_data.get("url", "")
    
    raw_ts = audit_data.get("timestamp", "")
    try:
        if isinstance(raw_ts, str) and raw_ts.endswith("Z"): raw_ts = raw_ts[:-1]
        dt = datetime.fromisoformat(raw_ts)
        formatted_date = dt.strftime("%B %d, %Y")
    except Exception:
        formatted_date = raw_ts

    is_sample = tier in {"single_page", "sample"}

    flattened_violations = []
    
    checklist_map = {
        "1. Perceivable": {}, "2. Operable": {}, "3. Understandable": {}, "4. Robust": {}
    }
    
    for p in passes:
        tags = p.get("tags", [])
        principle = _get_wcag_principle(tags)
        if principle in checklist_map:
            key = _get_wcag_criteria(tags, p.get("id"))
            checklist_map[principle][key] = {"id": p.get("id"), "wcag": key, "status": "Pass"}

    for rule in violations:
        rule_id = rule.get("id", "unknown")
        rule_desc = rule.get("description", "No description")
        tags = rule.get("tags", [])
        principle = _get_wcag_principle(tags)
        wcag_criteria = _get_wcag_criteria(tags, rule_id)
        
        if principle in checklist_map:
            checklist_map[principle][wcag_criteria] = {"id": rule_id, "wcag": wcag_criteria, "status": "Fail"}

        nodes = rule.get("nodes", [])
        if not nodes:
            impact = rule.get("impact", "moderate")
            flattened_violations.append({
                "severity": _map_impact_to_severity(impact), "principle": principle,
                "rule_id": rule_id, "description": rule_desc, "wcag_criteria": wcag_criteria,
                "html": "N/A", "target": "N/A", "failureSummary": rule.get("help", "No remediation provided.")
            })
        else:
            for node in nodes:
                impact = node.get("impact") or rule.get("impact", "moderate")
                target_str = ", ".join(node.get("target", [])) if node.get("target") else "N/A"
                flattened_violations.append({
                    "severity": _map_impact_to_severity(impact), "principle": principle,
                    "rule_id": rule_id, "description": rule_desc, "wcag_criteria": wcag_criteria,
                    "html": node.get("html", "N/A"), "target": target_str,
                    "failureSummary": node.get("failureSummary", rule.get("help", ""))
                })

    flattened_violations.sort(key=lambda x: (_get_severity_order(x["severity"]), x["principle"]))

    total_instances = len(flattened_violations)
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    violation_summary = {}
    
    for item in flattened_violations:
        counts[item["severity"]] += 1
        key = (item["rule_id"], item["description"])
        if key not in violation_summary: 
            violation_summary[key] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Total": 0}
        violation_summary[key][item["severity"]] += 1
        violation_summary[key]["Total"] += 1

    overview_table_html = ""
    for (rule_id, rule_desc), cnt in sorted(violation_summary.items(), key=lambda x: x[1]["Total"], reverse=True):
        pct = (cnt["Total"] / total_instances * 100) if total_instances > 0 else 0
        desc_esc = _html_escape(rule_desc)
        brk = f"C:{cnt['Critical']} H:{cnt['High']} M:{cnt['Medium']} L:{cnt['Low']}"
        overview_table_html += f"""
        <tr class="bg-surface-container-lowest">
            <td class="px-8 py-6">
                <p class="text-sm font-bold text-on-surface">{desc_esc}</p>
                <p class="text-xs text-on-surface-variant mt-1">Rule ID: {_html_escape(rule_id)}</p>
            </td>
            <td class="px-8 py-6 text-center text-sm font-medium text-on-surface">{pct:.1f}%</td>
            <td class="px-8 py-6 text-center text-sm font-bold text-primary">{cnt["Total"]}</td>
            <td class="px-8 py-6 text-center font-mono text-[10px] text-on-surface-variant">{brk}</td>
        </tr>
        """
        
    if not violation_summary:
        overview_table_html = '<tr><td colspan="4" class="px-8 py-6 text-center">No violations found.</td></tr>'

    checklist_html = ""
    for prin, items_dict in checklist_map.items():
        checklist_html += f"<div><h4 class='text-lg font-bold mb-6 border-b border-outline-variant/20 pb-4'>{prin}</h4><ul class='space-y-4'>"
        for wcag, info in sorted(items_dict.items()):
            label, _ = WCAG_MAP.get(wcag, (wcag, ""))
            if info["status"] == "Fail": 
                span = "<span class='flex items-center gap-2 text-[10px] font-bold text-error uppercase'><span class='material-symbols-outlined text-sm'>cancel</span> Fail</span>"
            else: 
                span = "<span class='flex items-center gap-2 text-[10px] font-bold text-primary uppercase'><span class='material-symbols-outlined text-sm'>check_circle</span> Pass</span>"
            checklist_html += f"<li class='flex items-center justify-between py-1'><span class='text-sm text-on-surface-variant'>{label}</span>{span}</li>"
        if not items_dict:
            checklist_html += "<li class='text-sm text-on-surface-variant italic'>No checks recorded.</li>"
        checklist_html += "</ul></div>"

    visible_violations = flattened_violations[:4] if is_sample else flattened_violations
    hidden_violations = max(0, len(flattened_violations) - len(visible_violations))
    
    deepdive_html = ""
    for item in visible_violations:
        sev = item["severity"]
        sev_class = SEV_CLASSES.get(sev, SEV_CLASSES["Medium"])
        wcag_raw = item["wcag_criteria"]
        wcag_label, wcag_link = WCAG_MAP.get(wcag_raw, (f"{wcag_raw} (WCAG)", "https://www.w3.org/WAI/standards-guidelines/wcag/"))
        desc = _html_escape(item["description"])
        target = _html_escape(item["target"])
        html_code = _html_escape(item["html"])
        remediation = _html_escape(item["failureSummary"]).replace("\\n", "<br/>")

        deepdive_html += f"""
        <div class="bg-surface-container-low p-12 rounded-xl relative overflow-hidden page-break break-inside-avoid mt-8">
            <div class="relative z-10">
                <div class="flex items-center gap-3 mb-6">
                    <span class="px-3 py-1 {sev_class} text-[10px] font-black uppercase rounded-sm">{sev} Finding</span>
                    <h3 class="text-2xl font-black tracking-tight text-on-surface">{desc}</h3>
                </div>
                <div class="mb-6">
                    <a class="text-xs font-bold text-primary uppercase hover:underline" href="{wcag_link}">WCAG Success Criterion: {wcag_label}</a>
                </div>
                <div class="grid grid-cols-1 gap-6">
                    <div>
                        <h4 class="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-3">Problem / Target Element</h4>
                        <div class="bg-surface-container-highest/20 p-4 rounded-lg text-sm text-on-surface font-mono overflow-x-auto whitespace-pre-wrap">{target}</div>
                    </div>
                    <div>
                        <h4 class="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-3">Code Snippet</h4>
                        <div class="bg-inverse-surface text-inverse-on-surface p-6 rounded-lg font-mono text-xs overflow-x-auto">
                            <div class="mb-2 text-error-container">// Non-compliant markup</div>
                            <div class="mb-2 whitespace-pre-wrap">{html_code}</div>
                        </div>
                    </div>
                    <div>
                        <h4 class="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-3">Remediation Instruction</h4>
                        <div class="bg-surface-container-highest/50 p-6 rounded-lg text-sm text-on-surface leading-relaxed">
                            {remediation}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    if is_sample and hidden_violations > 0:
        deepdive_html += f"""
        <div class="bg-error-container/30 p-12 rounded-xl text-center mt-12 page-break">
            <h3 class="text-2xl font-black text-on-surface mb-2">{hidden_violations} More Instances Found</h3>
            <p class="text-on-surface-variant">The remaining isolated violation occurrences are available securely in the full audit report. Upgrade to review all specific code targets.</p>
        </div>
        """

    try: wcag_score_float = float(wcag_score)
    except: wcag_score_float = 0.0
    dial_deg = int((wcag_score_float / 100.0) * 360)

    tpl_path = Path(__file__).parent / "report_template.html"
    with open(tpl_path, "r", encoding="utf-8") as f:
        html_str = f.read()

    replacements = {
        "{{ url }}": str(url),
        "{{ title_prefix }}": "Sample Scan" if is_sample else "Full Audit",
        "{{ formatted_date }}": str(formatted_date),
        "{{ overall_score }}": str(wcag_score),
        "{{ dial_deg }}": str(dial_deg),
        "{{ compliance_status }}": "Requires Action" if total_instances > 0 else "Compliant",
        "{{ compliance_description }}": "Systemic improvements required for enterprise-grade accessibility." if total_instances > 0 else "No violations were found during automated scanning.",
        "{{ count_critical }}": str(counts["Critical"]),
        "{{ count_high }}": str(counts["High"]),
        "{{ count_medium }}": str(counts["Medium"]),
        "{{ count_low }}": str(counts["Low"]),
        "{{ incomplete_count }}": str(len(incomplete)),
        "{{ passes_count }}": str(len(passes)),
        "{{ violation_rules_count }}": str(len(violations)),
        "{{ violation_instances_count }}": str(total_instances),
        "{{ checklist_html }}": checklist_html,
        "{{ overview_table_html }}": overview_table_html,
        "{{ deepdive_html }}": deepdive_html
    }

    for k, v in replacements.items():
        html_str = html_str.replace(k, v)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page()
        page.set_content(html_str, wait_until="networkidle")
        page.pdf(
            path=str(output),
            print_background=True,
            format="A4",
            margin={"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"}
        )
        browser.close()

    return {
        "pdf_path": str(output),
        "size_bytes": output.stat().st_size,
        "violation_rules": len(violations),
        "violation_instances": len(flattened_violations),
        "is_sample": is_sample,
    }
'''

with open('src/aiplatform/skills/audit/generate_accessibility_report.py', 'w', encoding='utf-8') as f:
    f.write(content)
