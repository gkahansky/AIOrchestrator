"""
Marketing Audit — Sample / Teaser Report Generator

Produces a censored version of the full audit report for sales outreach.
The sample shows enough to demonstrate value without giving away the full analysis.

Censoring rules:
  Score breakdown    — shown in full (all 6 dimensions + scores)
  Key findings       — severity counts in full; 1-2 sample findings shown;
                       rest visible as redaction bars (count but not content).
                       Preference order: High → Medium → Low → Critical.
                       Critical findings are censored unless ALL findings are critical.
  Action plan        — first item per timeframe shown; rest redacted with count.

Outputs:
  PDF  — professional PDF with "SAMPLE" watermark and CTA footer
  MD   — Markdown version for embedding in proposal letters
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path


# ─── Censoring logic ──────────────────────────────────────────────────────────

_SEVERITY_SAMPLE_ORDER = ["High", "Medium", "Low", "Critical"]


def censor_report_data(report_data: dict) -> dict:
    """
    Return a censored view of report_data for the sample report.
    Does NOT modify the original dict.
    """
    findings = report_data.get("findings", [])
    quick_wins = report_data.get("quick_wins", [])
    medium_term = report_data.get("medium_term", [])
    strategic = report_data.get("strategic", [])

    return {
        **report_data,
        "_sample": True,
        "_censored_findings": _censor_findings(findings),
        "_censored_actions": _censor_actions(quick_wins, medium_term, strategic),
    }


def _censor_findings(findings: list[dict]) -> dict:
    """
    Choose 1–2 findings to surface; redact the rest.

    Returns:
        {
            counts:         {"Critical": N, "High": N, "Medium": N, "Low": N},
            total:          int,
            visible:        [{"severity": str, "finding": str}],
            redacted_count: int,
        }
    """
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        sev = f.get("severity", "Medium")
        counts[sev] = counts.get(sev, 0) + 1

    # Build a pool ordered by preference; criticals always last
    visible: list[dict] = []
    for sev in _SEVERITY_SAMPLE_ORDER:
        for f in findings:
            if f.get("severity") == sev and len(visible) < 2:
                visible.append(f)
        if len(visible) >= 2:
            break

    # Fallback: if everything was critical, surface one critical
    if not visible and findings:
        visible = [findings[0]]

    return {
        "counts": counts,
        "total": len(findings),
        "visible": visible,
        "redacted_count": len(findings) - len(visible),
    }


def _censor_actions(
    quick_wins: list[str],
    medium_term: list[str],
    strategic: list[str],
) -> dict:
    """Show the first item from each timeframe; redact the rest."""
    return {
        "quick_wins": {
            "visible": quick_wins[:1],
            "redacted_count": max(0, len(quick_wins) - 1),
        },
        "medium_term": {
            "visible": medium_term[:1],
            "redacted_count": max(0, len(medium_term) - 1),
        },
        "strategic": {
            "visible": strategic[:1],
            "redacted_count": max(0, len(strategic) - 1),
        },
    }


# ─── PDF generator ────────────────────────────────────────────────────────────

def generate_sample_pdf(report_data: dict, output_path: str) -> str:
    """
    Generate the censored sample PDF.
    Returns output_path on success.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable,
    )
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.graphics import renderPDF

    censored = censor_report_data(report_data)
    cf = censored["_censored_findings"]
    ca = censored["_censored_actions"]

    COLORS = {
        "primary":    HexColor("#1B2A4A"),
        "accent":     HexColor("#2D5BFF"),
        "highlight":  HexColor("#FF6B35"),
        "success":    HexColor("#00C853"),
        "warning":    HexColor("#FFB300"),
        "danger":     HexColor("#FF1744"),
        "light_bg":   HexColor("#F5F7FA"),
        "text":       HexColor("#2C3E50"),
        "text_light": HexColor("#7F8C9B"),
        "border":     HexColor("#E0E6ED"),
        "redact":     HexColor("#1a1a2e"),   # near-black for censored bars
        "sample_banner": HexColor("#FF6B35"),
    }

    def score_color(s):
        if s >= 80: return COLORS["success"]
        if s >= 60: return COLORS["accent"]
        if s >= 40: return COLORS["warning"]
        return COLORS["danger"]

    def score_grade(s):
        if s >= 85: return "A"
        if s >= 70: return "B"
        if s >= 55: return "C"
        if s >= 40: return "D"
        return "F"

    # ── Page template with watermark ──────────────────────────────────────────
    def _watermark(canvas, doc):
        canvas.saveState()
        canvas.setFillGray(0.93)
        canvas.setFont("Helvetica-Bold", 70)
        canvas.translate(letter[0] / 2, letter[1] / 2)
        canvas.rotate(35)
        canvas.drawCentredString(0, 0, "SAMPLE")
        canvas.restoreState()

    # ── Document ──────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=50, leftMargin=50,
        topMargin=50, bottomMargin=50,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "STitle", parent=styles["Title"],
        fontSize=24, textColor=COLORS["primary"],
        spaceAfter=4, spaceBefore=0, fontName="Helvetica-Bold",
        alignment=0, leftIndent=12, rightIndent=0,
    )
    subtitle_style = ParagraphStyle(
        "SSub", parent=styles["Normal"],
        fontSize=11, textColor=COLORS["text_light"],
        spaceAfter=16, spaceBefore=0, fontName="Helvetica",
        leftIndent=12,
    )
    heading_style = ParagraphStyle(
        "SHeading", parent=styles["Heading1"],
        fontSize=16, textColor=COLORS["primary"],
        spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold",
    )
    subheading_style = ParagraphStyle(
        "SSubheading", parent=styles["Heading2"],
        fontSize=12, textColor=COLORS["text"],
        spaceBefore=12, spaceAfter=4, fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "SBody", parent=styles["Normal"],
        fontSize=9, textColor=COLORS["text"],
        spaceAfter=4, fontName="Helvetica", leading=13,
    )
    cta_style = ParagraphStyle(
        "SCTA", parent=styles["Normal"],
        fontSize=10, textColor=white,
        spaceAfter=4, fontName="Helvetica-Bold",
    )
    small_style = ParagraphStyle(
        "SSmall", parent=styles["Normal"],
        fontSize=8, textColor=COLORS["text_light"],
        fontName="Helvetica",
    )

    brand = report_data.get("brand_name", report_data.get("url", "Site"))
    url = report_data.get("url", "")
    date_str = report_data.get("date", datetime.now().strftime("%B %d, %Y"))
    overall = report_data.get("overall_score", 0)
    grade = score_grade(overall)
    tier = report_data.get("tier", "full")
    total_findings = cf["total"]
    visible_findings = len(cf["visible"])

    elements = []

    # ── SAMPLE banner ─────────────────────────────────────────────────────────
    banner_data = [[
        Paragraph(
            'SAMPLE REPORT — Partial findings only. <a href="mailto:contact@echoforge.com"><u>Contact EchoForge</u></a> for the complete audit.',
            ParagraphStyle("Banner", parent=styles["Normal"],
                           fontSize=9, textColor=white, fontName="Helvetica-Bold"),
        )
    ]]
    banner_table = Table(banner_data, colWidths=[512])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["sample_banner"]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(banner_table)
    elements.append(Spacer(1, 0.2 * inch))

    # ── Header ────────────────────────────────────────────────────────────────
    elements.append(Paragraph(f"Marketing Audit: {brand}", title_style))
    elements.append(Paragraph(
        f"URL: {url}  ·  Date: {date_str}  ·  Business type: {report_data.get('business_type', '—')}",
        subtitle_style,
    ))

    # Overall score pill
    _pill_base = dict(spaceBefore=0, spaceAfter=0, leading=14)
    score_data = [[
        Paragraph("Overall Score", ParagraphStyle("SL", parent=styles["Normal"],
                  fontSize=10, textColor=COLORS["text_light"], fontName="Helvetica", **_pill_base)),
        Paragraph(f"{overall}/100", ParagraphStyle("SV", parent=styles["Normal"],
                  fontSize=22, textColor=score_color(overall), fontName="Helvetica-Bold",
                  **{**_pill_base, "leading": 26})),
        Paragraph(f"Grade: {grade}", ParagraphStyle("SG", parent=styles["Normal"],
                  fontSize=18, textColor=COLORS["primary"], fontName="Helvetica-Bold",
                  **{**_pill_base, "leading": 22})),
        Paragraph(
            f"This sample shows {visible_findings} of {total_findings} total findings.",
            ParagraphStyle("SI", parent=styles["Normal"],
                           fontSize=9, textColor=COLORS["text_light"], fontName="Helvetica",
                           **_pill_base),
        ),
    ]]
    score_pill = Table(score_data, colWidths=[100, 110, 110, 192], rowHeights=[50])
    score_pill.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["light_bg"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 0.3, COLORS["border"]),
    ]))
    elements.append(score_pill)
    elements.append(Spacer(1, 0.15 * inch))

    # ── Score breakdown (full) ────────────────────────────────────────────────
    elements.append(Paragraph("Score Breakdown", heading_style))
    elements.append(Paragraph(
        "All six dimensions are shown in full.", small_style,
    ))
    elements.append(Spacer(1, 0.08 * inch))

    score_rows = [["Category", "Score", "Weight", "Status", "Key Finding"]]
    categories = report_data.get("categories", {})
    for dim, cat in categories.items():
        s = int(cat.get("score", 50))
        status = "Strong" if s >= 75 else "Needs Work" if s >= 50 else "Critical"
        kf = cat.get("key_finding", "")
        # Wrap key finding to ~45 chars
        kf_wrapped = textwrap.shorten(kf, width=55, placeholder="…")
        score_rows.append([
            Paragraph(dim, body_style),
            f"{s}/100",
            cat.get("weight", ""),
            status,
            Paragraph(kf_wrapped, body_style),
        ])

    score_table = Table(score_rows, colWidths=[135, 55, 45, 70, 207])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLORS["primary"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, COLORS["border"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, COLORS["light_bg"]]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    # Colour-code the score cells
    for i, (dim, cat) in enumerate(categories.items(), 1):
        s = int(cat.get("score", 50))
        score_table.setStyle(TableStyle([
            ("TEXTCOLOR", (1, i), (1, i), score_color(s)),
            ("FONTNAME", (1, i), (1, i), "Helvetica-Bold"),
        ]))
    elements.append(score_table)

    elements.append(PageBreak())

    # ── Key findings (censored) ────────────────────────────────────────────────
    elements.append(Paragraph("Key Findings", heading_style))

    # Severity summary row
    sev_counts = cf["counts"]
    sev_data = [[
        Paragraph(f"CRITICAL\n{sev_counts.get('Critical', 0)}",
                  ParagraphStyle("SC", parent=styles["Normal"], fontSize=10,
                                 textColor=COLORS["danger"], fontName="Helvetica-Bold",
                                 alignment=1)),
        Paragraph(f"HIGH\n{sev_counts.get('High', 0)}",
                  ParagraphStyle("SH", parent=styles["Normal"], fontSize=10,
                                 textColor=COLORS["highlight"], fontName="Helvetica-Bold",
                                 alignment=1)),
        Paragraph(f"MEDIUM\n{sev_counts.get('Medium', 0)}",
                  ParagraphStyle("SM", parent=styles["Normal"], fontSize=10,
                                 textColor=COLORS["warning"], fontName="Helvetica-Bold",
                                 alignment=1)),
        Paragraph(f"LOW\n{sev_counts.get('Low', 0)}",
                  ParagraphStyle("SLow", parent=styles["Normal"], fontSize=10,
                                 textColor=COLORS["accent"], fontName="Helvetica-Bold",
                                 alignment=1)),
        Paragraph(f"TOTAL\n{cf['total']}",
                  ParagraphStyle("ST", parent=styles["Normal"], fontSize=10,
                                 textColor=COLORS["primary"], fontName="Helvetica-Bold",
                                 alignment=1)),
    ]]
    sev_table = Table(sev_data, colWidths=[103, 103, 102, 102, 102])
    sev_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["light_bg"]),
        ("GRID", (0, 0), (-1, -1), 0.4, COLORS["border"]),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(sev_table)
    elements.append(Spacer(1, 0.1 * inch))

    # Visible findings
    severity_colors_map = {
        "Critical": COLORS["danger"],
        "High": COLORS["highlight"],
        "Medium": COLORS["warning"],
        "Low": COLORS["accent"],
    }

    if cf["visible"]:
        vis_rows = [["Severity", "Finding"]]
        for f in cf["visible"]:
            sev = f.get("severity", "Medium")
            vis_rows.append([
                Paragraph(sev, ParagraphStyle("FS", parent=styles["Normal"],
                          fontSize=8, fontName="Helvetica-Bold",
                          textColor=severity_colors_map.get(sev, COLORS["text"]))),
                Paragraph(f.get("finding", ""), body_style),
            ])
        vis_table = Table(vis_rows, colWidths=[65, 447])
        vis_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLORS["primary"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, COLORS["border"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, COLORS["light_bg"]]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ]))
        elements.append(vis_table)

    # Redacted rows
    if cf["redacted_count"] > 0:
        redact_rows = []
        for _ in range(min(cf["redacted_count"], 4)):
            redact_rows.append([
                _redact_bar(65, 14),
                _redact_bar(447, 14),
            ])
        redact_table = Table(redact_rows, colWidths=[65, 447])
        redact_table.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(redact_table)
        elements.append(Paragraph(
            f"... and {cf['redacted_count']} more findings in the full report.",
            small_style,
        ))

    elements.append(Spacer(1, 0.2 * inch))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=COLORS["border"]))

    # ── Action plan (censored) ─────────────────────────────────────────────────
    elements.append(Paragraph("Prioritized Action Plan", heading_style))

    for section_label, section_key in [
        ("Quick Wins (This Week)", "quick_wins"),
        ("Medium-Term Actions (1–3 Months)", "medium_term"),
        ("Strategic Initiatives (3–6 Months)", "strategic"),
    ]:
        section = ca[section_key]
        elements.append(Paragraph(section_label, subheading_style))

        if section["visible"]:
            elements.append(Paragraph(
                f"1. {section['visible'][0]}", body_style,
            ))

        redacted = section["redacted_count"]
        if redacted > 0:
            for _ in range(min(redacted, 3)):
                elements.append(_redact_bar(512, 12))
                elements.append(Spacer(1, 2))
            elements.append(Paragraph(
                f"... and {redacted} more in the full report.",
                small_style,
            ))
        elements.append(Spacer(1, 0.08 * inch))

    elements.append(PageBreak())

    # ── CTA page ──────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        "Want the complete audit?",
        ParagraphStyle("CTAH", parent=styles["Title"],
                       fontSize=22, textColor=COLORS["primary"],
                       fontName="Helvetica-Bold", spaceAfter=12),
    ))
    elements.append(Paragraph(
        f"This sample contains {visible_findings} of {total_findings} findings. "
        f"Your full report includes:",
        body_style,
    ))
    elements.append(Spacer(1, 0.1 * inch))

    full_includes = [
        f"✓  All {total_findings} prioritized findings with severity ratings",
        "✓  Complete action plan with step-by-step implementation guidance",
        "✓  Competitor comparison benchmarking",
        "✓  Before/after copy rewrite examples",
    ]
    if tier == "premium":
        full_includes.append("✓  30-day implementation roadmap with weekly milestones")

    for item in full_includes:
        elements.append(Paragraph(item, body_style))

    elements.append(Spacer(1, 0.25 * inch))

    # CTA box
    cta_box_data = [[
        Paragraph(
            "Reply to receive your complete audit report — echoforge.biz",
            ParagraphStyle("CTABox", parent=styles["Normal"],
                           fontSize=12, textColor=white, fontName="Helvetica-Bold",
                           leading=18),
        )
    ]]
    cta_box = Table(cta_box_data, colWidths=[512])
    cta_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["accent"]),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("LEFTPADDING", (0, 0), (-1, -1), 24),
    ]))
    elements.append(cta_box)

    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(
        f"Generated by EchoForge Marketing Audit — echoforge.biz  ·  {date_str}",
        small_style,
    ))

    doc.build(elements, onFirstPage=_watermark, onLaterPages=_watermark)
    return output_path


# ─── Markdown sample ──────────────────────────────────────────────────────────

def generate_sample_markdown(report_data: dict) -> str:
    """
    Generate a censored Markdown sample report.
    Designed for embedding in proposal letters and emails.
    """
    censored = censor_report_data(report_data)
    cf = censored["_censored_findings"]
    ca = censored["_censored_actions"]

    brand = report_data.get("brand_name", report_data.get("url", "Site"))
    url = report_data.get("url", "")
    date_str = report_data.get("date", datetime.now().strftime("%B %d, %Y"))
    overall = report_data.get("overall_score", 0)

    def _score_grade(s):
        if s >= 85: return "A"
        if s >= 70: return "B"
        if s >= 55: return "C"
        if s >= 40: return "D"
        return "F"

    grade = _score_grade(overall)
    total = cf["total"]
    visible_count = len(cf["visible"])

    lines = [
        f"# Marketing Audit — {brand} *(Sample Report)*",
        f"> **SAMPLE** — This report shows {visible_count} of {total} findings. "
        f"Contact [EchoForge](https://echoforge.biz) for the complete analysis.",
        "",
        f"**URL:** {url}  ",
        f"**Date:** {date_str}  ",
        f"**Business Type:** {report_data.get('business_type', '—')}  ",
        f"**Overall Score: {overall}/100 (Grade {grade})**",
        "",
        "---",
        "",
        "## Score Breakdown *(shown in full)*",
        "",
        "| Category | Score | Weight | Key Finding |",
        "|---|---|---|---|",
    ]

    for dim, cat in report_data.get("categories", {}).items():
        s = int(cat.get("score", 50))
        kf = textwrap.shorten(cat.get("key_finding", ""), width=60, placeholder="…")
        lines.append(f"| {dim} | **{s}/100** | {cat.get('weight', '')} | {kf} |")

    # Findings
    sev = cf["counts"]
    lines += [
        "",
        "---",
        "",
        "## Key Findings",
        "",
        f"**{total} total findings** — "
        f"🔴 Critical: {sev.get('Critical', 0)}  "
        f"🟠 High: {sev.get('High', 0)}  "
        f"🟡 Medium: {sev.get('Medium', 0)}  "
        f"🔵 Low: {sev.get('Low', 0)}",
        "",
    ]

    severity_emoji = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🔵"}
    for f in cf["visible"]:
        sev_label = f.get("severity", "Medium")
        emoji = severity_emoji.get(sev_label, "•")
        lines.append(f"**{emoji} {sev_label}:** {f.get('finding', '')}")
        lines.append("")

    if cf["redacted_count"] > 0:
        lines.append(f"> 🔒 **+{cf['redacted_count']} finding(s) redacted** — available in the full report")
        lines.append("")

    # Action plan
    lines += ["---", "", "## Prioritized Action Plan", ""]

    for section_label, section_key in [
        ("Quick Wins (This Week)", "quick_wins"),
        ("Medium-Term Actions (1–3 Months)", "medium_term"),
        ("Strategic Initiatives (3–6 Months)", "strategic"),
    ]:
        section = ca[section_key]
        lines.append(f"### {section_label}")
        lines.append("")
        if section["visible"]:
            lines.append(f"1. {section['visible'][0]}")
        if section["redacted_count"] > 0:
            lines.append(
                f"> 🔒 **+{section['redacted_count']} more action(s) redacted** — available in the full report"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## Get the Complete Report",
        "",
        f"This sample contains **{visible_count} of {total} findings**. "
        "Your full report includes:",
        "",
        f"- ✅ All **{total} prioritized findings** with severity ratings and fix guidance",
        "- ✅ Complete action plan with step-by-step implementation",
        "- ✅ Competitor comparison benchmarking",
        "- ✅ Before/after copy rewrite examples",
    ]

    tier = report_data.get("tier", "full")
    if tier == "premium":
        lines.append("- ✅ 30-day implementation roadmap with weekly milestones")

    lines += [
        "",
        "**Reply to receive your complete audit report**  ",
        "[echoforge.biz](https://echoforge.biz)",
        "",
        f"*Generated by EchoForge Marketing Audit — {date_str}*",
    ]

    return "\n".join(lines)


# ─── Helper: redaction bar ────────────────────────────────────────────────────

def _redact_bar(width: float, height: float):
    """Return a reportlab Drawing that looks like a redaction bar."""
    from reportlab.graphics.shapes import Drawing, Rect
    from reportlab.lib.colors import HexColor

    d = Drawing(width, height + 4)
    d.add(Rect(0, 2, width, height, fillColor=HexColor("#c8cdd3"), strokeColor=None))
    return d
