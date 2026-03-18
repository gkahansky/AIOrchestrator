"""
Sprint 1 script — Generate an image via DALL-E 3 and save it locally.
Thin CLI wrapper around platform/skills/media/generate_image.py

Usage:
    python scripts/generate_image.py "minimalist botanical monstera line art" [OPTIONS]

Options:
    --ar        Aspect ratio: 1:1 | 2:3 | 3:2 | 16:9  (default: 1:1)
    --tier      Quality tier: standard | premium        (default: standard)
    --out       Output directory                        (default: ./output/images)
    --name      Output filename stem                    (default: auto-generated)
    --upload    Upload to Google Drive after generation (default: false)

Examples:
    python scripts/generate_image.py "minimalist botanical line art, black on white --ar 1:1"
    python scripts/generate_image.py "watercolour koi fish" --ar 2:3 --out ./output/test
    python scripts/generate_image.py "boho sun illustration" --ar 1:1 --upload
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from aiplatform.skills.media.generate_image import generate_image


def main():
    parser = argparse.ArgumentParser(description="Generate an image via DALL-E 3.")
    parser.add_argument("prompt", help="Image generation prompt.")
    parser.add_argument("--ar", default="1:1", choices=["1:1", "2:3", "3:2", "16:9"],
                        help="Aspect ratio (default: 1:1).")
    parser.add_argument("--tier", default="standard", choices=["standard", "premium"],
                        help="Quality tier (default: standard).")
    parser.add_argument("--out", default="./output/images",
                        help="Output directory (default: ./output/images).")
    parser.add_argument("--name", default=None,
                        help="Output filename stem (default: auto-generated).")
    parser.add_argument("--upload", action="store_true",
                        help="Upload to Google Drive after generation.")
    args = parser.parse_args()

    print(f"Prompt   : {args.prompt}")
    print(f"Ratio    : {args.ar}")
    print(f"Tier     : {args.tier}")
    print(f"Out dir  : {args.out}")
    print()

    print("Generating image...")
    result = generate_image(
        prompt=args.prompt,
        aspect_ratio=args.ar,
        quality_tier=args.tier,
        output_dir=args.out,
        filename=args.name,
    )

    print(f"Tool used  : {result['tool_used']}")
    print(f"Cost       : ${result['cost']:.4f}")
    print(f"Dimensions : {result['width']} × {result['height']}")
    print(f"Saved to   : {result['image_path']}")
    if result.get("prompt") and result["prompt"] != args.prompt:
        print(f"Revised prompt: {result['prompt']}")

    if args.upload:
        folder_id = _require_env("DRIVE_03_IMAGES_ID")
        print(f"\nUploading to Drive folder {folder_id}...")
        from aiplatform.skills.storage.drive_write import drive_write
        drive_result = drive_write(result["image_path"], folder_id)
        print(f"Uploaded   : {drive_result['web_view_link']}")
        result["drive_file_id"] = drive_result["file_id"]
        result["drive_link"] = drive_result["web_view_link"]

    # Write result JSON alongside the image
    json_path = Path(result["image_path"]).with_suffix(".json")
    json_path.write_text(json.dumps(result, indent=2))
    print(f"Metadata   : {json_path}")


def _require_env(key: str) -> str:
    import os
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} is not set in .env")
        sys.exit(1)
    return val


if __name__ == "__main__":
    main()
