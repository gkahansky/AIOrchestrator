"""
Sprint 3 script — Phase 3: Generate image, resize, and create mockups for a subject.

Reads a subjects JSON file (output of Phase 2), picks a subject by index or slug,
runs image generation → resize → mockup creation, and saves all outputs.

Usage:
    python scripts/run_phase3.py <subjects_json> [OPTIONS]

Options:
    --index     Subject index (0-based, default: 0)
    --slug      Subject slug (takes priority over --index)
    --out       Local output directory (default: ./output/images)
    --no-drive  Skip Drive upload

Examples:
    python scripts/run_phase3.py output/subjects/botanical-line-art/subjects-botanical-line-art.json
    python scripts/run_phase3.py output/subjects/botanical-line-art/subjects-botanical-line-art.json --index 2
    python scripts/run_phase3.py output/subjects/botanical-line-art/subjects-botanical-line-art.json --slug botanical-01 --no-drive
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from ventures.etsy.pipeline import run_phase_3


def main():
    parser = argparse.ArgumentParser(description="Phase 3: Image generation, resize, and mockups.")
    parser.add_argument("subjects_json", help="Path to subjects JSON file (Phase 2 output).")
    parser.add_argument("--index",    type=int, default=0, help="Subject index (0-based).")
    parser.add_argument("--slug",     default=None, help="Subject slug (overrides --index).")
    parser.add_argument("--out",      default="./output/images")
    parser.add_argument("--no-drive", action="store_true")
    args = parser.parse_args()

    subjects_path = Path(args.subjects_json)
    if not subjects_path.exists():
        print(f"ERROR: File not found: {subjects_path}")
        sys.exit(1)

    subjects = json.loads(subjects_path.read_text())

    # Select subject
    if args.slug:
        matches = [s for s in subjects if s.get("subject_id") == args.slug]
        if not matches:
            print(f"ERROR: No subject with slug '{args.slug}' found.")
            sys.exit(1)
        subject = matches[0]
    else:
        if args.index >= len(subjects):
            print(f"ERROR: Index {args.index} out of range (0–{len(subjects)-1}).")
            sys.exit(1)
        subject = subjects[args.index]

    print(f"Phase 3 — Image Generation")
    print(f"Subject : {subject.get('subject_id')} — {subject.get('title_draft', '')[:60]}")
    print(f"Output  : {args.out}")
    print(f"Drive   : {'no' if args.no_drive else 'yes'}")
    print()

    result = run_phase_3(
        subject=subject,
        save_to_drive=not args.no_drive,
        output_dir=args.out,
    )

    print()
    print(f"Phase 3 complete:")
    print(f"  Raw image  : {result['raw_image']}")
    print(f"  Variants   :")
    for vname, vdata in result["variants"].items():
        if isinstance(vdata, dict):
            print(f"    {vname:<12}  PNG: {Path(vdata['png']).name}  JPG: {Path(vdata['jpg']).name}")
    print(f"  Mockups    :")
    m = result["mockups"]
    for scene in ("living_room", "office", "bedroom"):
        if scene in m:
            print(f"    {scene:<14} {m[scene]}")
    print(f"  Total cost : ${result['total_cost']:.4f}")
    if result.get("drive_folder_id"):
        print(f"  Drive      : folder {result['drive_folder_id']}")
    # Persist result so Phase 4 can load it
    import json as _json
    result_path = Path(args.out) / subject.get("subject_id", "listing") / "phase3-result.json"
    result_path.write_text(_json.dumps(result, indent=2))
    print(f"  Result JSON: {result_path}")
    print()
    print(f"Next: run scripts/run_phase4.py with this result:")
    print(f"  python scripts/run_phase4.py <subjects_json> {result_path}")


if __name__ == "__main__":
    main()
