"""
Sprint 3 script — Phase 4: Package a listing (delivery ZIP + review PDF).

Reads a subjects JSON and a Phase 3 output JSON, creates the delivery ZIP
and review-sheet PDF, and uploads to Drive /04-packages/.

Usage:
    python scripts/run_phase4.py <subjects_json> <phase3_json> [OPTIONS]

Options:
    --slug      Subject slug (required if subjects_json has multiple subjects)
    --out       Local output directory (default: ./output/packages)
    --no-drive  Skip Drive upload

Examples:
    python scripts/run_phase4.py \\
        output/subjects/botanical-line-art/subjects-botanical-line-art.json \\
        output/images/botanical-01/phase3-result.json

    python scripts/run_phase4.py \\
        output/subjects/botanical-line-art/subjects-botanical-line-art.json \\
        output/images/botanical-01/phase3-result.json \\
        --slug botanical-01 --no-drive
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from ventures.etsy.pipeline import run_phase_4


def main():
    parser = argparse.ArgumentParser(description="Phase 4: Create delivery ZIP and review PDF.")
    parser.add_argument("subjects_json", help="Path to Phase 2 subjects JSON.")
    parser.add_argument("phase3_json",   help="Path to Phase 3 result JSON.")
    parser.add_argument("--slug",     default=None, help="Subject slug.")
    parser.add_argument("--out",      default="./output/packages")
    parser.add_argument("--no-drive", action="store_true")
    args = parser.parse_args()

    # Load subjects
    subjects_path = Path(args.subjects_json)
    if not subjects_path.exists():
        print(f"ERROR: Subjects file not found: {subjects_path}")
        sys.exit(1)
    subjects = json.loads(subjects_path.read_text())

    # Load Phase 3 result
    p3_path = Path(args.phase3_json)
    if not p3_path.exists():
        print(f"ERROR: Phase 3 result not found: {p3_path}")
        sys.exit(1)
    phase3_result = json.loads(p3_path.read_text())

    # Select subject
    slug = args.slug or phase3_result.get("subject_id") or phase3_result.get("slug")
    if slug:
        matches = [s for s in subjects if s.get("subject_id") == slug]
        if not matches:
            print(f"ERROR: No subject with slug '{slug}'.")
            sys.exit(1)
        subject = matches[0]
    else:
        subject = subjects[0]
        slug    = subject.get("subject_id", "unknown")

    print(f"Phase 4 — Packaging")
    print(f"Subject : {slug}")
    print(f"Output  : {args.out}")
    print(f"Drive   : {'no' if args.no_drive else 'yes'}")
    print()

    result = run_phase_4(
        subject=subject,
        phase3_result=phase3_result,
        save_to_drive=not args.no_drive,
        output_dir=args.out,
    )

    print()
    print(f"Phase 4 complete:")
    print(f"  ZIP      : {result['zip_path']}")
    print(f"  ZIP size : {result['zip_size_bytes'] / (1024*1024):.2f} MB  "
          f"({'OK' if result['zip_within_limit'] else 'OVER LIMIT'})")
    print(f"  PDF      : {result['pdf_path']}")
    print()
    print(f"  Checks   :")
    for k, v in result["checks_passed"].items():
        icon = "[OK]" if v else "[!!]"
        print(f"    {icon}  {k}")
    if result.get("drive_zip_id"):
        print(f"  Drive ZIP ID : {result['drive_zip_id']}")
        print(f"  Drive PDF ID : {result['drive_pdf_id']}")
    print()
    print("Next: run scripts/run_phase5.py (Sprint 4) for human review notification.")


if __name__ == "__main__":
    main()
