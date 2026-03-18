"""
Skill: create_zip
Assemble the buyer delivery ZIP for a listing.

ZIP must be ≤ 20 MB (Etsy hard limit).
Compression fallback order: PNG (default) → PNG optimise → JPEG 92%.

delivery.zip structure:
    README.txt
    square/image-3000x3000.png + .jpg
    portrait/image-2400x3600.png + .jpg
    landscape/image-3600x2400.png + .jpg
    4k/image-3840x2160.png + .jpg
"""

import io
import zipfile
from pathlib import Path

from PIL import Image


ETSY_ZIP_MAX_BYTES = 20 * 1024 * 1024  # 20 MB


_DEFAULT_README = """\
Thank you for your purchase!
=============================

This ZIP contains your digital wall art in four print-ready sizes:

  square/     3000 × 3000 px  (square / 1:1)
  portrait/   2400 × 3600 px  (portrait / 2:3)
  landscape/  3600 × 2400 px  (landscape / 3:2)
  4k/         3840 × 2160 px  (widescreen / 16:9)

Each size is provided as both PNG (best quality) and JPG (smaller file).
Minimum 300 DPI when printed at the recommended sizes.

For questions or a different size, message us through Etsy.
Happy printing!
"""


def create_zip(
    variants: dict,
    output_path: str,
    readme_text: str = None,
) -> dict:
    """
    Create the delivery ZIP from resize_image output.

    Args:
        variants:    Output dict from resize_to_variants().
        output_path: Where to write the .zip file.
        readme_text: Optional README.txt content override.

    Returns:
        { zip_path (str), size_bytes (int), within_limit (bool) }
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    readme = readme_text or _DEFAULT_README

    # Folder name inside ZIP → variants key
    _FOLDER_MAP = {
        "square":    "square",
        "portrait":  "portrait",
        "landscape": "landscape",
        "wide_4k":   "4k",
    }

    # Dimension label used in the archived filename
    _DIM_LABEL = {
        "square":    "3000x3000",
        "portrait":  "2400x3600",
        "landscape": "3600x2400",
        "wide_4k":   "3840x2160",
    }

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # README
        zf.writestr("README.txt", readme)

        # Image files
        for variant_key, folder in _FOLDER_MAP.items():
            if variant_key not in variants:
                continue
            v = variants[variant_key]
            dim = _DIM_LABEL[variant_key]
            for fmt in ("png", "jpg"):
                src = Path(v[fmt])
                if not src.exists():
                    raise FileNotFoundError(f"Variant file not found: {src}")
                arcname = f"{folder}/image-{dim}.{fmt}"
                zf.write(src, arcname)

    size_bytes = output_path.stat().st_size

    # Fallback: if over 20 MB, re-compress PNGs → 8-bit palette, then switch to JPEG 92%
    if size_bytes > ETSY_ZIP_MAX_BYTES:
        size_bytes = _recompress_zip(variants, output_path, _FOLDER_MAP, _DIM_LABEL, readme)

    return {
        "zip_path":     str(output_path),
        "size_bytes":   size_bytes,
        "within_limit": size_bytes <= ETSY_ZIP_MAX_BYTES,
    }


# ─── Fallback recompression ───────────────────────────────────────────────────

def _recompress_zip(variants, output_path, folder_map, dim_label, readme) -> int:
    """
    Re-write the ZIP using in-memory PNG 8-bit quantisation for each PNG.
    If still over limit, replace PNGs with JPEG 92%.
    """
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("README.txt", readme)
        for variant_key, folder in folder_map.items():
            if variant_key not in variants:
                continue
            v = variants[variant_key]
            dim = dim_label[variant_key]

            # PNG: quantise to 8-bit palette to reduce size
            png_bytes = _quantise_png(Path(v["png"]))
            zf.writestr(f"{folder}/image-{dim}.png", png_bytes)

            # JPG: just copy
            zf.write(Path(v["jpg"]), f"{folder}/image-{dim}.jpg")

    size_bytes = output_path.stat().st_size

    if size_bytes <= ETSY_ZIP_MAX_BYTES:
        return size_bytes

    # Last resort: replace PNGs with JPEG duplicates
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("README.txt", readme)
        for variant_key, folder in folder_map.items():
            if variant_key not in variants:
                continue
            v = variants[variant_key]
            dim = dim_label[variant_key]
            jpg_path = Path(v["jpg"])
            zf.write(jpg_path, f"{folder}/image-{dim}.png")   # store as .png name for buyer clarity
            zf.write(jpg_path, f"{folder}/image-{dim}.jpg")

    return output_path.stat().st_size


def _quantise_png(path: Path) -> bytes:
    """Convert a 24-bit PNG to 8-bit palette PNG in memory."""
    img = Image.open(path).convert("RGB")
    quantised = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    buf = io.BytesIO()
    quantised.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
