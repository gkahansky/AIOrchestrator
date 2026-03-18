"""
Sprint 1 script — Generate 3 photorealistic room mockups with actual artwork composited in.

Pass 1: DALL-E 3 generates room backgrounds with a magenta placeholder rectangle.
Pass 2: Pillow detects the magenta region and composites the real artwork into it.

Usage:
    python scripts/create_mockup.py <artwork_image> <artwork_description> [OPTIONS]

Options:
    --out   Output directory (default: ./output/mockups)
    --slug  Filename slug    (default: input image stem)
    --ar    Aspect ratio: 1:1 | 2:3 | 3:2 | 16:9 (default: 1:1)

Examples:
    python scripts/create_mockup.py output/test/dalle3-abc.png "minimalist botanical monstera leaf line art"
    python scripts/create_mockup.py my-art.png "watercolour koi fish" --slug koi-01 --ar 2:3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from aiplatform.skills.media.create_mockup import create_mockup


def main():
    parser = argparse.ArgumentParser(description="Generate 3 photorealistic room mockups.")
    parser.add_argument("artwork",      help="Path to the raw artwork image.")
    parser.add_argument("description",  help="Artwork description (informs room scene style).")
    parser.add_argument("--out",  default="./output/mockups", help="Output directory.")
    parser.add_argument("--slug", default=None,               help="Filename slug.")
    parser.add_argument("--ar",   default="1:1", choices=["1:1", "2:3", "3:2", "16:9"])
    args = parser.parse_args()

    artwork_path = Path(args.artwork)
    if not artwork_path.exists():
        print(f"ERROR: Artwork file not found: {artwork_path}")
        sys.exit(1)

    slug = args.slug or artwork_path.stem

    print(f"Artwork     : {artwork_path}")
    print(f"Description : {args.description}")
    print(f"Out dir     : {args.out}")
    print(f"Slug        : {slug}")
    print()
    print("Generating 3 mockups (3 x DALL-E 3 + Pillow composite)...")
    print()

    result = create_mockup(
        artwork_path=artwork_path,
        artwork_description=args.description,
        output_dir=args.out,
        slug=slug,
        aspect_ratio=args.ar,
    )

    print()
    for key, val in result.items():
        if key == "cost":
            print(f"Total cost  : ${val:.4f}")
        else:
            size_kb = Path(val).stat().st_size // 1024
            print(f"  {key:<15} {size_kb} KB  ->  {val}")


if __name__ == "__main__":
    main()
