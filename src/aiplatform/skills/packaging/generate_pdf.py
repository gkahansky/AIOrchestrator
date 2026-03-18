"""
Skill: generate_pdf
Generate the review-sheet PDF for a listing using WeasyPrint.

Status: Sprint 3 — not yet implemented.

PDF sections:
  - Header (listing slug, date)
  - 3 mockup thumbnails + 1 raw image thumbnail
  - Metadata block (title, description, tags, price)
  - Auto-checks: resolution ✓, tag count = 13 ✓, title ≤ 140 chars ✓,
                 ZIP ≤ 20MB ✓, 3 mockups present ✓
  - Drive links
  - Decision field: Approve / Reject / Edit / Regenerate
"""


def generate_pdf(listing_data: dict, output_path: str) -> dict:
    """
    Render a review-sheet PDF for a listing.

    Args:
        listing_data: Dict with keys: slug, title, description, tags, price_usd,
                      mockup_paths (list[str]), raw_image_path, zip_path,
                      metadata_drive_link, zip_drive_link.
        output_path:  Where to write the .pdf file.

    Returns:
        { pdf_path, size_bytes, checks_passed (dict) }
    """
    raise NotImplementedError("generate_pdf is a Sprint 3 feature.")
