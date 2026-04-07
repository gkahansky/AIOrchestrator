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
            formatted = f"{criteria[0]}.{criteria[1]}.{criteria[2:]}"
            return f"Criteria {formatted}"
    return f"Rule {rule_id}"


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

    pdf.set_font("Helvetica", "B", 18)
    title = "Accessibility Sample Report" if is_sample else "Accessibility Audit Report"
    pdf.cell(0, 10, _s(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _s(f"Target URL: {url}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Generated: {timestamp}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _s("Audit Summary"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _s(f"WCAG score: {wcag_score}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Total Rules Violated: {len(violations)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Total Isolated Instances: {len(flattened_violations)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Incomplete automatic checks: {len(incomplete)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Passing checks: {len(passes)}"), new_x="LMARGIN", new_y="NEXT")
    if is_sample:
        pdf.multi_cell(
            0,
            5,
            _s("Sample tier: this one-page version shows a few real findings and censors the rest. Upgrade to a full audit for the complete remediation plan."),
            new_x="LMARGIN", new_y="NEXT"
        )
    pdf.ln(4)

    # Glossary
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _s("Severity Glossary & SLA"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    
    glossary_items = [
        ("Critical", "High risk of legal action. Complete blocker for users with disabilities (e.g., missing keyboard trap escape). SLA: Fix within 24-48 hours."),
        ("High", "Significant legal risk. Severe barriers for many users (e.g., missing form labels). SLA: Fix within 1-2 weeks."),
        ("Medium", "Moderate risk. Causes frustration or difficulty (e.g., color contrast issues). SLA: Fix within 1-3 months."),
        ("Low", "Low immediate risk, but still a WCAG violation. Minor friction for users. SLA: Address in next regular release.")
    ]
    for sev, desc in glossary_items:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(16, 5, _s(f"{sev}: "), new_x="RIGHT")
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _s(desc), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _s("Detailed Violations" if not is_sample else "Sample Findings"), new_x="LMARGIN", new_y="NEXT")
    if not flattened_violations:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _s("No violations were detected by the automated scan."), new_x="LMARGIN", new_y="NEXT")
    else:
        current_severity = None
        current_principle = None
        
        for index, item in enumerate(visible_violations, start=1):
            if item["severity"] != current_severity:
                current_severity = item["severity"]
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(180, 0, 0) 
                pdf.cell(0, 6, _s(f"Severity: {current_severity}"), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
                current_principle = None
                
            if item["principle"] != current_principle:
                current_principle = item["principle"]
                pdf.set_font("Helvetica", "I", 10)
                pdf.cell(0, 6, _s(f"  {current_principle}"), new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "B", 9)
            pdf.multi_cell(
                0,
                6,
                _s(f"{index}. Rule: {item['rule_id']} ({item['wcag_criteria']})"),
                new_x="LMARGIN", new_y="NEXT"
            )
            
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, _s(f"Description: {item['description']}"), new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_text_color(45, 92, 170)
            pdf.multi_cell(0, 5, _s("WCAG Guideline: https://www.w3.org/WAI/standards-guidelines/wcag/"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(0, 5, _s("Target Element:"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Courier", "", 8)
            pdf.multi_cell(0, 4, _s(item["target"]), new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(0, 5, _s("Code Snippet:"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Courier", "", 8)
            pdf.multi_cell(0, 4, _s(item["html"]), new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(0, 5, _s("Remediation / Example:"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            clean_summary = item["failureSummary"].strip().replace("\n\n", "\n")
            pdf.multi_cell(0, 4, _s(clean_summary), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

        if is_sample and hidden_violations:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 6, _s("Additional Findings (censored)"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(
                0,
                5,
                _s(f"{hidden_violations} additional isolated instance findings are hidden in this sample report."),
                new_x="LMARGIN", new_y="NEXT"
            )
            for _ in range(min(hidden_violations, 4)):
                pdf.multi_cell(0, 5, _s("[ REDACTED FOR SAMPLE PREVIEW ]"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    if is_sample:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _s("Next Step"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(
            0,
            6,
            _s("This sample is designed for lead generation: a few real issues are visible, while the full set stays censored until the client upgrades."),
            new_x="LMARGIN", new_y="NEXT"
        )

    pdf.output(str(output))
    return {
        "pdf_path": str(output),
        "size_bytes": output.stat().st_size,
        "violation_rules": len(violations),
        "violation_instances": _violation_instance_count(violations),
        "is_sample": is_sample,
    }