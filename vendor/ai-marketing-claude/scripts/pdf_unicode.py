"""
Unicode / RTL font support for ReportLab PDF generation.

Registers Noto Sans (installed via fonts-noto apt package) with ReportLab so
that Arabic, Hebrew, and other non-Latin scripts render as actual glyphs.

Arabic/Hebrew also need reshaping + bidi reordering before ReportLab sees them
(ReportLab is LTR-only). arabic-reshaper + python-bidi handle this.

Usage:
    from pdf_unicode import setup_unicode_fonts, rt

    reg, bold = setup_unicode_fonts()
    # Use reg/bold as fontName in ParagraphStyle / TableStyle.
    # Wrap any string through rt() before putting it in a Paragraph/String:
    #   Paragraph(rt("مرحبا"), style)
"""

from __future__ import annotations
import os
import unicodedata

UNICODE_FONT      = "Helvetica"       # updated after successful registration
UNICODE_FONT_BOLD = "Helvetica-Bold"

_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    r"C:\Windows\Fonts\NotoSans-Regular.ttf",
]
_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    r"C:\Windows\Fonts\NotoSans-Bold.ttf",
]


def setup_unicode_fonts() -> tuple[str, str]:
    """
    Register Noto Sans with ReportLab. Idempotent — safe to call multiple times.
    Returns (regular_font_name, bold_font_name).
    Falls back to Helvetica if no Unicode font is found.
    """
    global UNICODE_FONT, UNICODE_FONT_BOLD
    if UNICODE_FONT != "Helvetica":
        return UNICODE_FONT, UNICODE_FONT_BOLD

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        reg  = next((p for p in _REGULAR_CANDIDATES if os.path.exists(p)), None)
        bold = next((p for p in _BOLD_CANDIDATES   if os.path.exists(p)), None)

        if reg:
            pdfmetrics.registerFont(TTFont("NotoSans", reg))
            UNICODE_FONT = "NotoSans"
        if bold:
            pdfmetrics.registerFont(TTFont("NotoSans-Bold", bold))
            UNICODE_FONT_BOLD = "NotoSans-Bold"
        elif UNICODE_FONT == "NotoSans":
            UNICODE_FONT_BOLD = "NotoSans"   # use regular as bold fallback
    except Exception:
        pass

    return UNICODE_FONT, UNICODE_FONT_BOLD


def rt(text: str) -> str:
    """
    Reshape Text for correct PDF rendering of RTL scripts.

    For Arabic / Hebrew: applies arabic-reshaper (contextual glyph forms)
    then python-bidi (visual reordering for LTR canvas).
    Pure Latin strings pass through unchanged.
    If the packages are absent the original string is returned unchanged.
    """
    if not text or not _has_rtl(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        return text


def _has_rtl(text: str) -> bool:
    return any(unicodedata.bidirectional(c) in ("R", "AL", "AN") for c in text)
