"""
Skill: generate_accessibility_report
Render a PDF summary for an accessibility audit.

Input:
    audit_data   (dict): axe scan result payload.
    output_path  (str):  Path to the PDF to create.

Output:
    {
        "pdf_path": str,
        "size_bytes": int,
        "violation_rules": int,
        "violation_instances": int,
    }
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

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


def _s(value: object) -> str:
    return str(value).encode("latin-1", "replace").decode("latin-1")


def _violation_instance_count(violations: list[dict]) -> int:
    total = 0
    for violation in violations:
        nodes = violation.get("nodes") or []
        total += len(nodes) if nodes else 1
    return total

def _map_impact_to_severity(impact: str) -> str:
    mapping = {
        "minor": "Low",
        "moderate": "Medium",
        "serious": "High",
        "critical": "Critical"
    }
    return mapping.get(impact, "Medium")


def _get_severity_order(severity: str) -> int:
    return {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}.get(severity, 5)


def _get_wcag_principle(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("wcag1"):
            return "Principle 1: Perceivable"
        elif tag.startswith("wcag2"):
            return "Principle 2: Operable"
        elif tag.startswith("wcag3"):
            return "Principle 3: Understandable"
        elif tag.startswith("wcag4"):
            return "Principle 4: Robust"
    return "Other / General"


def _get_wcag_criteria(tags: list[str], rule_id: str) -> str:
    for tag in tags:
        if tag.startswith("wcag") and len(tag) >= 7:
            criteria = tag.replace("wcag", "")
            if len(criteria) >= 3 and criteria[:3].isdigit():
                return f"{criteria[0]}.{criteria[1]}.{criteria[2:]}"
    return rule_id


def _full_width(pdf: FPDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def generate_accessibility_report(audit_data: dict, output_path: str, tier: str = "standard") -> dict:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    violations = audit_data.get("violations", []) or []
    incomplete = audit_data.get("incomplete", []) or []
    passes = audit_data.get("passes", []) or []
    wcag_score = audit_data.get("wcag_score", "N/A")
    url = audit_data.get("url", "")
    timestamp = audit_data.get("timestamp", "")
    is_sample = tier in {"single_page", "sample"}

    flattened_violations = []
    for rule in violations:
        rule_id = rule.get("id", "unknown")
        rule_desc = rule.get("description", "No description")
        tags = rule.get("tags", [])
        principle = _get_wcag_principle(tags)
        wcag_criteria = _get_wcag_criteria(tags, rule_id)
        
        nodes = rule.get("nodes", [])
        if not nodes:
            impact = rule.get("impact", "moderate")
            flattened_violations.append({
                "severity": _map_impact_to_severity(impact),
                "principle": principle,
                "rule_id": rule_id,
                "description": rule_desc,
                "wcag_criteria": wcag_criteria,
                "html": "N/A",
                "target": "N/A",
                "failureSummary": rule.get("help", "No remediation provided.")
            })
        else:
            for node in nodes:
                impact = node.get("impact") or rule.get("impact", "moderate")
                target_str = ", ".join(node.get("target", [])) if node.get("target") else "N/A"
                flattened_violations.append({
                    "severity": _map_impact_to_severity(impact),
                    "principle": principle,
                    "rule_id": rule_id,
                    "description": rule_desc,
                    "wcag_criteria": wcag_criteria,
                    "html": node.get("html", "N/A"),
                    "target": target_str,
                    "failureSummary": node.get("failureSummary", rule.get("help", "No remediation provided."))
                })

    # Sort primarily by severity (Critical -> Low), then by Principle
    flattened_violations.sort(key=lambda x: (_get_severity_order(x["severity"]), x["principle"]))

    visible_violations = flattened_violations[:4] if is_sample else flattened_violations
    hidden_violations = max(0, len(flattened_violations) - len(visible_violations))

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # Title Header (styled)
    pdf.set_fill_color(33, 37, 41)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    title = "Accessibility Sample Report" if is_sample else "Accessibility Audit Report"
    pdf.cell(0, 14, _s(" " + title), fill=True, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(4)
    pdf.cell(0, 6, _s(f"Target URL: {url}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Generated: {timestamp}"), new_x="LMARGIN", new_y="NEXT")
    pdf.line(15, pdf.get_y()+2, pdf.w-15, pdf.get_y()+2)
    pdf.ln(6)

    # Audit Summary Section
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 80, 150)
    pdf.cell(0, 8, _s("1. Audit Summary"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    
    pdf.cell(60, 6, _s("WCAG score:"), border=1)
    pdf.cell(0, 6, _s(str(wcag_score)), border=1, new_x="LMARGIN", new_y="NEXT")
    
    pdf.cell(60, 6, _s("Total Rules Violated:"), border=1)
    pdf.cell(0, 6, _s(str(len(violations))), border=1, new_x="LMARGIN", new_y="NEXT")
    
    pdf.cell(60, 6, _s("Total Isolated Instances:"), border=1)
    pdf.cell(0, 6, _s(str(len(flattened_violations))), border=1, new_x="LMARGIN", new_y="NEXT")
    
    pdf.cell(60, 6, _s("Incomplete automatic checks:"), border=1)
    pdf.cell(0, 6, _s(str(len(incomplete))), border=1, new_x="LMARGIN", new_y="NEXT")
    
    pdf.cell(60, 6, _s("Passing checks:"), border=1)
    pdf.cell(0, 6, _s(str(len(passes))), border=1, new_x="LMARGIN", new_y="NEXT")
    
    if is_sample:
        pdf.ln(2)
        pdf.set_text_color(150, 0, 0)
        pdf.multi_cell(
            0,
            6,
            _s("Sample tier: this one-page version shows a few real findings and censors the rest. Upgrade to a full audit for the complete remediation plan."),
            new_x="LMARGIN", new_y="NEXT"
        )
        pdf.set_text_color(0, 0, 0)
    
    pdf.line(15, pdf.get_y()+4, pdf.w-15, pdf.get_y()+4)
    pdf.ln(8)

    # Violation Overview Section
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 80, 150)
    pdf.cell(0, 8, _s("2. Violation Overview"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    
    total_instances = len(flattened_violations)
    violation_summary = {}
    for item in flattened_violations:
        rule_desc = item["description"]
        rule_id = item["rule_id"]
        sev = item["severity"]
        key = (rule_id, rule_desc)
        if key not in violation_summary:
            violation_summary[key] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Total": 0}
        violation_summary[key][sev] += 1
        violation_summary[key]["Total"] += 1
        
    if not violation_summary:
        pdf.cell(0, 6, _s("No violations found."), new_x="LMARGIN", new_y="NEXT")
    else:
        # Table Header
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(75, 7, _s("Violation Description"), border=1, fill=True)
        pdf.cell(18, 7, _s("Pct %"), border=1, fill=True, align="C")
        pdf.cell(18, 7, _s("Count"), border=1, fill=True, align="C")
        pdf.cell(69, 7, _s("Breakdown (C/H/M/L)"), border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("Helvetica", "", 9)
        for (rule_id, rule_desc), counts in sorted(violation_summary.items(), key=lambda x: x[1]["Total"], reverse=True):
            pct = (counts["Total"] / total_instances * 100) if total_instances > 0 else 0
            
            # Text clipping for desc
            desc_text = rule_desc if len(rule_desc) < 45 else rule_desc[:42] + "..."
            
            pdf.cell(75, 6, _s(desc_text), border=1)
            pdf.cell(18, 6, _s(f"{pct:.1f}%"), border=1, align="C")
            pdf.cell(18, 6, _s(str(counts["Total"])), border=1, align="C")
            
            breakdown = f"C:{counts['Critical']} H:{counts['High']} M:{counts['Medium']} L:{counts['Low']}"
            pdf.cell(69, 6, _s(breakdown), border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    
    pdf.line(15, pdf.get_y()+4, pdf.w-15, pdf.get_y()+4)
    pdf.ln(8)

    # Glossary Section (Table Format)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 80, 150)
    pdf.cell(0, 8, _s("3. Severity Glossary & SLA"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    
    # Table Header for Glossary
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(20, 7, _s("Severity"), border=1, fill=True)
    pdf.cell(100, 7, _s("Description"), border=1, fill=True)
    pdf.cell(0, 7, _s("Recommended SLA"), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    
    glossary_items = [
        ("Critical", "Complete blocker for users with disabilities.", "Fix within 24-48 hrs"),
        ("High", "Severe barriers for many users. Sig risk.", "Fix within 1-2 weeks"),
        ("Medium", "Causes frustration or difficulty.", "Fix within 1-3 months"),
        ("Low", "Minor friction for users.", "Next regular release")
    ]
    
    pdf.set_font("Helvetica", "", 9)
    for sev, desc, sla in glossary_items:
        # Get Y position to draw matching height cells if multi_cell used, but these fit in 1 line
        pdf.cell(20, 6, _s(sev), border=1)
        pdf.cell(100, 6, _s(desc), border=1)
        pdf.cell(0, 6, _s(sla), border=1, new_x="LMARGIN", new_y="NEXT")
        
    pdf.line(15, pdf.get_y()+4, pdf.w-15, pdf.get_y()+4)
    pdf.ln(8)

    # Detailed Violations Section
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 80, 150)
    pdf.cell(0, 8, _s("4. Detailed Violations" if not is_sample else "4. Sample Findings"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    
    if not flattened_violations:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _s("No violations were detected by the automated scan."), new_x="LMARGIN", new_y="NEXT")
    else:
        current_severity = None
        current_principle = None
        
        for index, item in enumerate(visible_violations, start=1):
            if item["severity"] != current_severity:
                current_severity = item["severity"]
                pdf.ln(4)
                pdf.set_fill_color(220, 220, 220)
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(180, 0, 0) 
                pdf.cell(0, 8, _s(f" Severity: {current_severity} "), fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
                current_principle = None
                
            if item["principle"] != current_principle:
                current_principle = item["principle"]
                pdf.ln(2)
                pdf.set_font("Helvetica", "I", 10)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 6, _s(f"{current_principle}"), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)


            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(245, 245, 245)
            # Use 'Violation:' instead of 'Rule:'
            pdf.cell(0, 7, _s(f" {index}. Violation: {item['description'] or item['rule_id']}"), fill=True, new_x="LMARGIN", new_y="NEXT")
            
            # Build WCAG link using WCAG_MAP
            wcag_key = item['wcag_criteria']
            label, link = WCAG_MAP.get(wcag_key, (f"{wcag_key} (WCAG Guideline)", "https://www.w3.org/WAI/standards-guidelines/wcag/"))
            
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(50, 6, _s("Description:"), border=0)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 6, _s(item["description"]), new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(50, 6, _s("WCAG Success Criterion:"), border=0)
            pdf.set_text_color(0, 80, 150)
            pdf.cell(0, 6, _s(f"{label}"), link=link, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, _s("Target Element:"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Courier", "", 8)
            pdf.set_fill_color(250, 250, 250)
            pdf.multi_cell(0, 5, _s(item["target"]), fill=True, new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, _s("Code Snippet:"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Courier", "", 8)
            pdf.multi_cell(0, 5, _s(item["html"]), fill=True, new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, _s("Remediation / Example:"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            clean_summary = item["failureSummary"].strip().replace("\n\n", "\n")
            pdf.multi_cell(0, 5, _s(clean_summary), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        if is_sample and hidden_violations:
            pdf.ln(5)
            pdf.set_fill_color(220, 220, 220)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 8, _s(" Additional Findings (censored)"), fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(
                0,
                6,
                _s(f"  {hidden_violations} additional isolated instance findings are hidden in this sample report."),
                new_x="LMARGIN", new_y="NEXT"
            )
            for _ in range(min(hidden_violations, 3)):
                pdf.ln(1)
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(150, 150, 150)
                pdf.cell(0, 6, _s("  [ REDACTED ]"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(4)

    pdf.output(str(output))
    return {
        "pdf_path": str(output),
        "size_bytes": output.stat().st_size,
        "violation_rules": len(violations),
        "violation_instances": _violation_instance_count(violations),
        "is_sample": is_sample,
    }