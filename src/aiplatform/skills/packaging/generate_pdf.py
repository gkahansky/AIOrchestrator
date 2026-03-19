"""
Skill: generate_pdf
Generate the review-sheet PDF for a listing using fpdf2.

PDF sections:
  - Header (listing slug, date)
  - Thumbnails: 3 mockups + 1 raw image
  - Metadata block (title, description, tags, price)
  - Auto-checks: resolution ✓, tag count = 13 ✓, title ≤ 140 chars ✓,
                 ZIP ≤ 20 MB ✓, 3 mockups present ✓
  - Drive links
  - Decision field: Approve / Reject / Edit / Regenerate

Uses fpdf2 (not WeasyPrint — avoid Windows GTK3 dependency).
"""

from datetime import date
from pathlib import Path

from fpdf import FPDF


# Helvetica (built-in) is latin-1 only. Map common Unicode chars to safe ASCII.
_UNICODE_MAP = str.maketrans({
    "\u2014": "--",   # em dash
    "\u2013": "-",    # en dash
    "\u2018": "'",    # left single quote
    "\u2019": "'",    # right single quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u2026": "...",  # ellipsis
    "\u00a0": " ",    # non-breaking space
    "\u2122": "(TM)", # trademark
    "\u00ae": "(R)",  # registered
    "\u00a9": "(C)",  # copyright
})


def _s(text: str) -> str:
    """Sanitize text to latin-1 safe for fpdf Helvetica."""
    return text.translate(_UNICODE_MAP).encode("latin-1", errors="replace").decode("latin-1")


_TITLE_MAX_CHARS  = 140
_REQUIRED_TAGS    = 13
_ZIP_MAX_BYTES    = 20 * 1024 * 1024
_THUMB_W          = 42   # mm — thumbnail width
_THUMB_H          = 42   # mm — thumbnail height
_PAGE_W           = 210  # A4 mm
_PAGE_H           = 297
_MARGIN           = 15


def generate_pdf(listing_data: dict, output_path: str) -> dict:
    """
    Render a review-sheet PDF for a listing.

    Args:
        listing_data: dict with keys:
            slug              (str)
            title             (str)
            description       (str)
            tags              (list[str])
            price_usd         (float)
            mockup_paths      (list[str])   — up to 3 paths
            raw_image_path    (str)
            zip_path          (str)
            zip_size_bytes    (int)
            metadata_drive_link (str | None)
            zip_drive_link    (str | None)

    Returns:
        { pdf_path (str), size_bytes (int), checks_passed (dict) }
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    slug         = listing_data.get("slug", "unknown")
    title        = listing_data.get("title", "")
    description  = listing_data.get("description", "")
    tags         = listing_data.get("tags", [])
    price_usd    = listing_data.get("price_usd", 0.0)
    mockup_paths = listing_data.get("mockup_paths", [])
    raw_img      = listing_data.get("raw_image_path", "")
    zip_path_str = listing_data.get("zip_path", "")
    zip_size     = listing_data.get("zip_size_bytes", 0)
    drive_meta   = listing_data.get("metadata_drive_link", "")
    drive_zip    = listing_data.get("zip_drive_link", "")
    run_date     = date.today().isoformat()

    # ── Auto-checks ──────────────────────────────────────────────────────────
    checks = {
        "title_length":     len(title) <= _TITLE_MAX_CHARS,
        "tag_count":        len(tags) == _REQUIRED_TAGS,
        "zip_size":         zip_size <= _ZIP_MAX_BYTES if zip_size else False,
        "mockups_present":  len(mockup_paths) >= 3,
        "raw_image_exists": Path(raw_img).exists() if raw_img else False,
    }
    all_pass = all(checks.values())

    # ── Build PDF ─────────────────────────────────────────────────────────────
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "Etsy Listing Review Sheet", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, _s(f"Slug: {slug}    Date: {run_date}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Status banner
    banner_color = (220, 255, 220) if all_pass else (255, 220, 220)
    banner_text  = "ALL CHECKS PASSED - Ready for review" if all_pass else "CHECKS FAILED - See issues below"
    pdf.set_fill_color(*banner_color)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, banner_text, fill=True, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    # Thumbnails
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Images", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    thumb_x = _MARGIN
    # Show raw image first
    if raw_img and Path(raw_img).exists():
        try:
            pdf.image(raw_img, x=thumb_x, w=_THUMB_W, h=_THUMB_H)
            pdf.set_xy(thumb_x, pdf.get_y() + 1)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(_THUMB_W, 4, "RAW IMAGE", align="C")
        except Exception:
            pass
        thumb_x += _THUMB_W + 4

    # Mockup thumbnails
    for i, mp in enumerate(mockup_paths[:3]):
        if Path(mp).exists():
            try:
                pdf.image(mp, x=thumb_x, y=pdf.get_y() - (_THUMB_H + 1), w=_THUMB_W, h=_THUMB_H)
                pdf.set_xy(thumb_x, pdf.get_y() + 1)
                pdf.set_font("Helvetica", "", 7)
                label = ["Living Room", "Office", "Bedroom"][i]
                pdf.cell(_THUMB_W, 4, label, align="C")
            except Exception:
                pass
            thumb_x += _THUMB_W + 4

    # Move below the thumbnail row
    pdf.ln(_THUMB_H + 8)

    # Metadata
    _section(pdf, "Listing Metadata")
    _kv(pdf, "Title",       title)
    _kv(pdf, "Price",       f"${price_usd:.2f} USD")
    _kv(pdf, "Description", description, multiline=True)
    _kv(pdf, "Tags",        ", ".join(tags))
    pdf.ln(3)

    # Auto-checks table
    _section(pdf, "Auto-Checks")
    _check_row(pdf, "Title length ≤ 140 chars",   checks["title_length"],
               f"{len(title)} chars")
    _check_row(pdf, f"Tag count = {_REQUIRED_TAGS}",          checks["tag_count"],
               f"{len(tags)} tags")
    _check_row(pdf, "ZIP ≤ 20 MB",                checks["zip_size"],
               f"{zip_size / (1024*1024):.2f} MB" if zip_size else "unknown")
    _check_row(pdf, "3 mockups present",           checks["mockups_present"],
               f"{len(mockup_paths)} mockups")
    _check_row(pdf, "Raw image on disk",           checks["raw_image_exists"])
    pdf.ln(3)

    # Drive links
    if drive_meta or drive_zip:
        _section(pdf, "Drive Links")
        if drive_meta:
            _kv(pdf, "Metadata JSON", drive_meta)
        if drive_zip:
            _kv(pdf, "Delivery ZIP",  drive_zip)
        pdf.ln(3)

    # File paths
    _section(pdf, "Local Paths")
    _kv(pdf, "Raw image", raw_img)
    _kv(pdf, "ZIP",       zip_path_str)
    pdf.ln(3)

    # Decision section
    _section(pdf, "Reviewer Decision")
    for choice in ["Approve", "Reject", "Edit - Regenerate image", "Edit - Fix metadata"]:
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(8, 7, "[ ]", new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 7, _s(f"  {choice}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, "Notes:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(180, 180, 180)
    for _ in range(4):
        pdf.cell(0, 8, "", border="B", new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(output_path))
    size_bytes = output_path.stat().st_size

    return {
        "pdf_path":      str(output_path),
        "size_bytes":    size_bytes,
        "checks_passed": checks,
    }


# ─── PDF helpers ─────────────────────────────────────────────────────────────

def _section(pdf: FPDF, title: str) -> None:
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(240, 240, 245)
    pdf.cell(0, 6, _s(f"  {title}"), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _kv(pdf: FPDF, key: str, value: str, multiline: bool = False) -> None:
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(38, 5, _s(f"{key}:"), new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "", 9)
    value = _s(value)
    if multiline and len(value) > 80:
        pdf.multi_cell(0, 5, value, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 5, value[:120] + ("..." if len(value) > 120 else ""), new_x="LMARGIN", new_y="NEXT")


def _check_row(pdf: FPDF, label: str, passed: bool, detail: str = "") -> None:
    icon  = "[OK]" if passed else "[!!]"
    color = (0, 140, 0) if passed else (200, 0, 0)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*color)
    pdf.cell(12, 5, icon, new_x="RIGHT", new_y="TOP")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    suffix = f"  ({_s(detail)})" if detail else ""
    pdf.cell(0, 5, _s(f"  {label}") + suffix, new_x="LMARGIN", new_y="NEXT")
