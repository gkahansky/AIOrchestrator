"""
Sprint 1 script — Resize an image to 4 Etsy delivery variants.
Thin CLI wrapper around platform/skills/media/resize_image.py

Variants produced:
    square    — 3000 × 3000 px  (PNG + JPG)
    portrait  — 2400 × 3600 px  (PNG + JPG)
    landscape — 3600 × 2400 px  (PNG + JPG)
    wide_4k   — 3840 × 2160 px  (PNG + JPG)

Usage:
    python scripts/resize_image.py <input_image> [OPTIONS]

Options:
    --out       Output directory (default: same dir as input, /sized subfolder)
    --quality   JPEG quality 1–95 (default: 92)
    --upload    Upload all variants to Google Drive after resizing

Examples:
    python scripts/resize_image.py output/images/dalle3-abc123.png
    python scripts/resize_image.py my-image.png --out ./output/sized --quality 90
    python scripts/resize_image.py my-image.png --upload
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from aiplatform.skills.media.resize_image import resize_to_variants


def main():
    parser = argparse.ArgumentParser(description="Resize an image to 4 Etsy delivery variants.")
    parser.add_argument("input", help="Path to the source image.")
    parser.add_argument("--out", default=None,
                        help="Output directory (default: <input_dir>/sized/).")
    parser.add_argument("--quality", type=int, default=92,
                        help="JPEG quality 1–95 (default: 92).")
    parser.add_argument("--upload", action="store_true",
                        help="Upload all variants to Google Drive after resizing.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    output_dir = Path(args.out) if args.out else input_path.parent / "sized"

    print(f"Input    : {input_path}")
    print(f"Out dir  : {output_dir}")
    print(f"Quality  : {args.quality}")
    print()

    print("Resizing to 4 variants (PNG + JPG each)...")
    result = resize_to_variants(
        source_path=input_path,
        output_dir=output_dir,
        quality_jpg=args.quality,
    )

    total_size = 0
    for variant_name in ("square", "portrait", "landscape", "wide_4k"):
        v = result[variant_name]
        png_size = Path(v["png"]).stat().st_size
        jpg_size = Path(v["jpg"]).stat().st_size
        total_size += png_size + jpg_size
        print(f"  {variant_name:<12} {v['width']}×{v['height']}  "
              f"PNG {png_size/1024:.0f}KB  JPG {jpg_size/1024:.0f}KB")

    print(f"\nTotal output size: {total_size / (1024*1024):.1f} MB")

    if args.upload:
        folder_id = _require_env("DRIVE_03_IMAGES_ID")
        from aiplatform.skills.storage.drive_write import drive_write
        print(f"\nUploading to Drive folder {folder_id}...")
        for variant_name in ("square", "portrait", "landscape", "wide_4k"):
            v = result[variant_name]
            for fmt in ("png", "jpg"):
                dr = drive_write(v[fmt], folder_id)
                print(f"  {variant_name} {fmt.upper()}: {dr['web_view_link']}")
                result[variant_name][f"drive_{fmt}_id"] = dr["file_id"]
                result[variant_name][f"drive_{fmt}_link"] = dr["web_view_link"]

    json_path = output_dir / f"{input_path.stem}-variants.json"
    json_path.write_text(json.dumps(result, indent=2))
    print(f"\nMetadata : {json_path}")


def _require_env(key: str) -> str:
    import os
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} is not set in .env")
        sys.exit(1)
    return val


if __name__ == "__main__":
    main()
