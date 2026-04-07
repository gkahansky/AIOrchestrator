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
    visible_violations = violations[:3] if is_sample else violations[:15]
    hidden_violations = max(0, len(violations) - len(visible_violations))

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
    pdf.cell(0, 8, _s("Summary"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _s(f"WCAG score: {wcag_score}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Violation rules: {len(violations)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Violation instances: {_violation_instance_count(violations)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Incomplete checks: {len(incomplete)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _s(f"Passing checks: {len(passes)}"), new_x="LMARGIN", new_y="NEXT")
    if is_sample:
        pdf.multi_cell(
            0,
            5,
            _s("Sample tier: this one-page version shows a few real findings and censors the rest. Upgrade to a full audit for the complete remediation plan."),
            new_x="LMARGIN", new_y="NEXT"
        )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _s("Top Violations" if not is_sample else "Sample Findings"), new_x="LMARGIN", new_y="NEXT")
    if not violations:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _s("No violations were detected by the automated scan."), new_x="LMARGIN", new_y="NEXT")
    else:
        for index, violation in enumerate(visible_violations, start=1):
            nodes = violation.get("nodes") or []
            impact = violation.get("impact") or "unknown"
            help_url = violation.get("help_url") or ""
            description = violation.get("description") or ""

            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(
                0,
                6,
                _s(f"{index}. {violation.get('id', 'unknown')} | impact: {impact} | occurrences: {len(nodes)}"),
                new_x="LMARGIN", new_y="NEXT"
            )
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, _s(description or "No description provided."), new_x="LMARGIN", new_y="NEXT")
            if help_url:
                pdf.set_text_color(45, 92, 170)
                pdf.multi_cell(0, 5, _s(help_url), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(0, 0, 0)
            if nodes:
                first_target = ", ".join(nodes[0].get("target", [])[:3])
                if first_target:
                    pdf.multi_cell(0, 5, _s(f"Example target: {first_target}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        if is_sample and hidden_violations:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 6, _s("Additional Findings (censored)"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(
                0,
                5,
                _s(f"{hidden_violations} additional rule-level findings are hidden in this sample report."),
                new_x="LMARGIN", new_y="NEXT"
            )
            for _ in range(min(hidden_violations, 6)):
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