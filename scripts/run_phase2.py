"""
Sprint 2 script — Phase 2: Generate 20 subjects for an Etsy theme using Claude.

Reads a theme name, asks Claude to generate 20 image subjects with SEO titles,
DALL-E prompts, keywords, and pricing, then saves:
  - subjects-{slug}.json → local + Drive /02-subjects/{slug}/

Usage:
    python scripts/run_phase2.py <theme> [OPTIONS]

Options:
    --out       Local output directory (default: ./output/subjects)
    --no-drive  Skip Drive upload

Examples:
    python scripts/run_phase2.py "botanical line art"
    python scripts/run_phase2.py "celestial moon and stars" --no-drive
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from ventures.etsy.pipeline import run_phase_2


def main():
    parser = argparse.ArgumentParser(description="Phase 2: Generate 20 subjects for a theme.")
    parser.add_argument("theme",       help="Theme name (e.g. 'botanical line art').")
    parser.add_argument("--out",       default="./output/subjects")
    parser.add_argument("--no-drive",  action="store_true")
    args = parser.parse_args()

    print(f"Phase 2 — Subject Generation")
    print(f"Theme  : {args.theme}")
    print(f"Output : {args.out}")
    print(f"Drive  : {'no' if args.no_drive else 'yes'}")
    print()

    result = run_phase_2(
        theme=args.theme,
        save_to_drive=not args.no_drive,
        output_dir=args.out,
    )

    subjects = result["subjects"]
    print(f"\n{len(subjects)} subjects generated:")
    print()
    print(f"  {'#':<3}  {'subject_id':<35}  {'price':>6}  {'tier':<10}  title")
    print("  " + "-" * 100)
    for i, s in enumerate(subjects, 1):
        title_short = s.get("title_draft", "")[:55]
        print(f"  {i:<3}  {s.get('subject_id',''):<35}  "
              f"${s.get('price_usd', 0):<5.2f}  {s.get('quality_tier',''):<10}  {title_short}")

    print()
    print(f"Saved to : {result['json_path']}")
    if result.get("drive_file_id"):
        print(f"Drive ID : {result['drive_file_id']}")
    print()
    print("Next: run scripts/generate_image.py with a subject's image_prompt.")


if __name__ == "__main__":
    main()
