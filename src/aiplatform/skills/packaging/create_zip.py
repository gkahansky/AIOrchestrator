"""
Skill: create_zip
Assemble the buyer delivery ZIP for a listing.

Status: Sprint 3 — not yet implemented.

ZIP must be ≤ 20MB (Etsy hard limit).
Compression fallback order: PNG 16-bit → PNG 8-bit → JPEG 92%.

delivery.zip structure:
    README.txt
    square/image-3000x3000.png + .jpg
    portrait/image-2400x3600.png + .jpg
    landscape/image-3600x2400.png + .jpg
    4k/image-3840x2160.png + .jpg
"""

ETSY_ZIP_MAX_BYTES = 20 * 1024 * 1024  # 20 MB


def create_zip(variants: dict, output_path: str, readme_text: str = None) -> dict:
    """
    Create the delivery ZIP from resize_image output.

    Args:
        variants:    Output dict from resize_to_variants().
        output_path: Where to write the .zip file.
        readme_text: Optional README.txt content.

    Returns:
        { zip_path, size_bytes, within_limit }
    """
    raise NotImplementedError("create_zip is a Sprint 3 feature.")
