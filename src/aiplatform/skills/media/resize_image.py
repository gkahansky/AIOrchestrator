"""
Skill: resize_image
Resize a source image to the 4 standard Etsy delivery variants using Pillow.

Variants (from CLAUDE.md spec):
    square    — 3000 × 3000 px  (1:1)
    portrait  — 2400 × 3600 px  (2:3)
    landscape — 3600 × 2400 px  (3:2)
    wide_4k   — 3840 × 2160 px  (16:9)

Both PNG and JPG are produced for each variant.
The full artwork is always visible — padded with white to reach exact dimensions.
Etsy minimum: 2000px on shortest side — all variants exceed this.

Input:
    source_path (str | Path): Local path to the source image.
    output_dir  (str | Path): Directory to write the 8 output files.
    quality_jpg (int):        JPEG quality (1–95). Default: 92.

Output:
    {
        "square":    { "png": str, "jpg": str, "width": 3000, "height": 3000 },
        "portrait":  { "png": str, "jpg": str, "width": 2400, "height": 3600 },
        "landscape": { "png": str, "jpg": str, "width": 3600, "height": 2400 },
        "wide_4k":   { "png": str, "jpg": str, "width": 3840, "height": 2160 },
        "source_path": str,
    }
"""

from pathlib import Path
from typing import Optional

from PIL import Image


VARIANTS = {
    "square":    (3000, 3000),
    "portrait":  (2400, 3600),
    "landscape": (3600, 2400),
    "wide_4k":   (3840, 2160),
}


def resize_to_variants(
    source_path: str | Path,
    output_dir: str | Path,
    quality_jpg: int = 92,
    pad_color: tuple = (255, 255, 255),
) -> dict:
    """
    Resize source_path to all 4 variants and save as PNG + JPG.

    The full artwork is always visible — scaled to fit within the target
    dimensions and padded with white (or pad_color) to reach exact size.
    No cropping occurs.
    """
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        raise FileNotFoundError(f"Source image not found: {source_path}")

    source_img = Image.open(source_path).convert("RGB")
    stem = source_path.stem

    result = {"source_path": str(source_path)}

    for variant_name, (target_w, target_h) in VARIANTS.items():
        resized = _fit_with_pad(source_img, target_w, target_h, pad_color)

        png_path = output_dir / f"{stem}-{variant_name}.png"
        jpg_path = output_dir / f"{stem}-{variant_name}.jpg"

        resized.save(png_path, format="PNG", optimize=True)
        resized.save(jpg_path, format="JPEG", quality=quality_jpg, optimize=True)

        result[variant_name] = {
            "png": str(png_path),
            "jpg": str(jpg_path),
            "width": target_w,
            "height": target_h,
        }

    return result


def _fit_with_pad(
    img: Image.Image,
    target_w: int,
    target_h: int,
    pad_color: tuple = (255, 255, 255),
) -> Image.Image:
    """
    Scale the image to fit entirely within the target dimensions (no cropping),
    then centre it on a pad_color background to reach exact target size.
    Upscales if the source is smaller than the target.
    """
    src_w, src_h = img.size
    scale = min(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)

    scaled = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (target_w, target_h), pad_color)
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2
    canvas.paste(scaled, (paste_x, paste_y))
    return canvas
