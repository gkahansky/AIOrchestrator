"""
Content Studio — PDF generation for podcast content packages.

generate_full_pdf(order, content, output_path)
    Complete content package as a polished PDF.
    Includes all sections for the tier.

generate_sample_pdf(order, content, output_path)
    Sample/outreach version with SAMPLE watermark.
    Timestamps shown in full (quality demo).
    Show notes, transcript, social captions, newsletter, SEO: first paragraph
    visible, remainder replaced with redaction bars + locked content message.
    CTA page at the end.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, KeepTogether,
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ─── Constants ────────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = letter        # 612 × 792 pt
MARGIN_L = MARGIN_R = 50
MARGIN_T = MARGIN_B = 50
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R   # 512 pt

BRAND_PRIMARY  = colors.HexColor("#C4622D")   # terracotta
BRAND_DARK     = colors.HexColor("#1A1A2E")   # near-black
BRAND_LIGHT_BG = colors.HexColor("#FDF8F4")   # warm off-white
BRAND_MID      = colors.HexColor("#7B6F64")   # warm grey
BRAND_RULE     = colors.HexColor("#E8DDD4")   # light divider
TEXT_BODY      = colors.HexColor("#2D2926")
REDACT_COLOR   = colors.HexColor("#C0B8B0")   # muted grey for redaction bars

SECTION_ORDER = [
    ("show_notes",       "Show Notes"),
    ("timestamps",       "Timestamps"),
    ("guest_bio",        "Guest Bio"),
    ("transcript",       "Full Transcript"),
    ("social_captions",  "Social Media Captions"),
    ("newsletter_excerpt", "Newsletter Excerpt"),
    ("seo_metadata",     "SEO Metadata"),
]

# Sections shown in full in the sample (quality demo); rest are redacted
SAMPLE_FULL_SECTIONS = {"timestamps", "guest_bio"}


# ─── Watermark flowable ───────────────────────────────────────────────────────

class DiagonalWatermark(Flowable):
    """Draws a diagonal SAMPLE watermark spanning the full page."""

    def __init__(self, text: str = "SAMPLE", alpha: float = 0.07):
        super().__init__()
        self.text = text
        self.alpha = alpha
        self.width = 0
        self.height = 0

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(colors.Color(0.3, 0.3, 0.3, alpha=self.alpha))
        canvas.setFont("Helvetica-Bold", 90)
        canvas.translate(PAGE_W / 2, PAGE_H / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, self.text)
        canvas.restoreState()


# ─── Helper: redaction bar ────────────────────────────────────────────────────

def _redact_bar(width: int, height: int = 10) -> Table:
    """Single redaction bar as a 1-cell table."""
    t = Table([[""]], colWidths=[width], rowHeights=[height])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), REDACT_COLOR),
        ("LINEABOVE",  (0, 0), (-1, -1), 0, REDACT_COLOR),
        ("LINEBELOW",  (0, 0), (-1, -1), 0, REDACT_COLOR),
    ]))
    return t


def _redact_block(num_bars: int, width: int = CONTENT_W) -> list:
    """Stack of redaction bars with varying widths."""
    widths = [width, int(width * 0.88), int(width * 0.95),
              int(width * 0.75), int(width * 0.90)]
    items = []
    for i in range(num_bars):
        items.append(_redact_bar(widths[i % len(widths)]))
        items.append(Spacer(1, 3))
    return items


# ─── Style registry ───────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()

    normal = ParagraphStyle(
        "cs_body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=TEXT_BODY,
        spaceAfter=4,
    )

    return {
        "title": ParagraphStyle(
            "cs_title",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=BRAND_DARK,
            spaceBefore=0,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "cs_subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=BRAND_MID,
            spaceBefore=0,
            spaceAfter=2,
        ),
        "section_heading": ParagraphStyle(
            "cs_section",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=BRAND_PRIMARY,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "body": normal,
        "body_mono": ParagraphStyle(
            "cs_mono",
            parent=normal,
            fontName="Courier",
            fontSize=8.5,
            leading=13,
        ),
        "cta_heading": ParagraphStyle(
            "cs_cta_head",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=BRAND_DARK,
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=8,
        ),
        "cta_body": ParagraphStyle(
            "cs_cta_body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            textColor=BRAND_MID,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "footer": ParagraphStyle(
            "cs_footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=BRAND_MID,
            alignment=TA_CENTER,
        ),
        "locked_msg": ParagraphStyle(
            "cs_locked",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=BRAND_MID,
            spaceBefore=4,
            spaceAfter=8,
        ),
    }


# ─── Shared header builder ────────────────────────────────────────────────────

def _header_elements(order: dict, styles: dict, is_sample: bool) -> list:
    show = order.get("show_name", "Podcast")
    episode = order.get("episode_title", "Episode")
    host = order.get("host_name", "")
    tier = order["tier"].title()
    date_str = datetime.utcnow().strftime("%B %d, %Y")

    elements = []

    # Banner strip
    banner_label = "SAMPLE REPORT" if is_sample else "CONTENT PACKAGE"
    banner_style = ParagraphStyle(
        "cs_banner",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        spaceBefore=0,
        spaceAfter=0,
    )
    if is_sample:
        banner_text = (
            f'SAMPLE REPORT — Timestamps and Guest Bio shown in full. '
            f'Remaining content locked. '
            f'<a href="mailto:contact@echoforge.com"><u>Contact Echoforge</u></a> for the complete package.'
        )
    else:
        banner_text = f"CONTENT PACKAGE — {tier} Tier · Generated by Echoforge Content Studio"

    banner_table = Table(
        [[Paragraph(banner_text, banner_style)]],
        colWidths=[CONTENT_W],
        rowHeights=[28],
    )
    banner_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), BRAND_DARK),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(banner_table)
    elements.append(Spacer(1, 10))

    # Title block
    elements.append(Paragraph(episode, styles["title"]))
    subtitle_parts = [show]
    if host:
        subtitle_parts.append(f"Host: {host}")
    subtitle_parts.append(f"{tier} Package · {date_str}")
    elements.append(Paragraph(" · ".join(subtitle_parts), styles["subtitle"]))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width=CONTENT_W, thickness=1.5,
                                color=BRAND_PRIMARY, spaceAfter=6))

    return elements


# ─── Section content builder ──────────────────────────────────────────────────

def _section_elements(
    title: str,
    body: str,
    styles: dict,
    redact: bool = False,
    is_mono: bool = False,
) -> list:
    """Return flowables for one content section."""
    elements = [Paragraph(title, styles["section_heading"])]

    if not body:
        return elements

    body_style = styles["body_mono"] if is_mono else styles["body"]
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

    if redact:
        # Show first paragraph, redact the rest
        first = paragraphs[0] if paragraphs else ""
        lines = first.split("\n")
        visible_text = "\n".join(lines[:3])  # show ~3 lines
        elements.append(Paragraph(visible_text.replace("\n", "<br/>"), body_style))
        elements.append(Spacer(1, 6))

        # Count remaining content to redact
        remaining_lines = sum(len(p.split("\n")) for p in paragraphs[1:])
        remaining_lines += max(0, len(lines) - 3)
        bars = min(max(3, remaining_lines // 2), 8)
        elements.extend(_redact_block(bars))
        elements.append(Paragraph(
            f"★ {remaining_lines} more lines in the full package "
            f"— contact@echoforge.com",
            styles["locked_msg"],
        ))
    else:
        for para in paragraphs:
            lines = para.split("\n")
            formatted = "<br/>".join(lines)
            elements.append(Paragraph(formatted, body_style))

    elements.append(Spacer(1, 4))
    return elements


# ─── CTA page (sample only) ───────────────────────────────────────────────────

def _cta_page_elements(order: dict, styles: dict) -> list:
    tier = order["tier"]
    from ventures.content_studio import config as cs_config
    tier_info = cs_config.TIERS.get(tier, {})
    price = tier_info.get("price_usd", "")
    description = tier_info.get("description", "")

    elements = [
        Spacer(1, 30),
        HRFlowable(width=CONTENT_W, thickness=1, color=BRAND_RULE),
        Spacer(1, 24),
    ]

    cta_table = Table(
        [[
            Paragraph("Unlock Your Complete Content Package", styles["cta_heading"]),
        ],
        [
            Paragraph(
                f"This sample shows Timestamps and Guest Bio in full.<br/>"
                f"The <b>{tier.title()} Package</b> ({description}) includes all sections "
                f"fully written and ready to publish.",
                styles["cta_body"],
            ),
        ],
        [
            Paragraph(
                f'<a href="mailto:contact@echoforge.com">'
                f'<u><b>Reply to order your complete package — echoforge.biz</b></u></a>',
                styles["cta_body"],
            ),
        ]],
        colWidths=[CONTENT_W],
    )
    cta_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), BRAND_LIGHT_BG),
        ("LEFTPADDING",  (0, 0), (-1, -1), 24),
        ("RIGHTPADDING", (0, 0), (-1, -1), 24),
        ("TOPPADDING",   (0, 0), (-1, 0),  20),
        ("BOTTOMPADDING",(0, -1),(-1, -1), 20),
        ("TOPPADDING",   (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -2), 0),
        ("BOX",          (0, 0), (-1, -1), 1.5, BRAND_PRIMARY),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(cta_table)
    return elements


# ─── Footer callback ──────────────────────────────────────────────────────────

def _make_footer(styles: dict, is_sample: bool):
    label = "SAMPLE" if is_sample else ""

    def on_page(canvas, doc):
        canvas.saveState()
        footer_text = f"Generated by Echoforge Content Studio — echoforge.biz"
        if label:
            footer_text = f"SAMPLE  ·  {footer_text}"
        y = MARGIN_B - 18
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(BRAND_MID)
        canvas.drawCentredString(PAGE_W / 2, y, footer_text)
        # Page number
        canvas.drawRightString(
            PAGE_W - MARGIN_R, y,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    return on_page


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_full_pdf(order: dict, content: dict, output_path: str | Path) -> str:
    """
    Generate a complete content package PDF.
    All tier sections included in full.
    Returns the output path as a string.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B + 20,
        title=f"{order.get('episode_title', 'Episode')} — Content Package",
    )

    elements = _header_elements(order, styles, is_sample=False)

    from ventures.content_studio import config as cs_config
    tier_sections = set(cs_config.TIERS.get(order["tier"], {}).get("sections", []))

    for key, label in SECTION_ORDER:
        if key not in tier_sections:
            continue
        body = content.get(key, "")
        if not body:
            continue
        is_mono = key in ("transcript", "seo_metadata")
        elements.extend(_section_elements(label, body, styles, redact=False, is_mono=is_mono))

    doc.build(elements, onFirstPage=_make_footer(styles, False),
              onLaterPages=_make_footer(styles, False))
    return str(output_path)


def generate_sample_pdf(order: dict, content: dict, output_path: str | Path) -> str:
    """
    Generate a watermarked sample PDF for outreach / demos.

    Timestamps and Guest Bio are shown in full.
    All other sections show the first ~3 lines then redaction bars with locked message.
    Ends with a CTA page.
    Returns the output path as a string.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B + 20,
        title=f"{order.get('episode_title', 'Episode')} — Sample Content Package",
    )

    elements: list = [DiagonalWatermark()]
    elements.extend(_header_elements(order, styles, is_sample=True))

    # Show notes always present; for sample, redact everything except
    # the "full" sections (timestamps, guest_bio)
    sample_sections = list(SECTION_ORDER)  # show all sections in sample to demonstrate value

    for key, label in sample_sections:
        body = content.get(key, "")
        if not body:
            continue
        is_full = key in SAMPLE_FULL_SECTIONS
        is_mono = key in ("transcript", "seo_metadata")
        elements.extend(_section_elements(
            label, body, styles,
            redact=(not is_full),
            is_mono=is_mono,
        ))

    elements.extend(_cta_page_elements(order, styles))

    doc.build(elements, onFirstPage=_make_footer(styles, True),
              onLaterPages=_make_footer(styles, True))
    return str(output_path)
