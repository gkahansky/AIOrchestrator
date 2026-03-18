"""
Sprint 2 script — Phase 1: Research and score Etsy themes.

Queries Google Trends + Etsy listing data for each theme via SerpAPI,
scores on demand / competition / monetisation, and saves:
  - themes-{date}.csv   → local + Drive /01-research/
  - themes-{date}.json  → local + Drive /01-research/

Usage:
    python scripts/run_phase1.py [OPTIONS]

Options:
    --themes  Comma-separated theme list (default: built-in 25 seed themes)
    --out     Local output directory (default: ./output/research)
    --no-drive  Skip Drive upload

Examples:
    python scripts/run_phase1.py
    python scripts/run_phase1.py --themes "botanical line art,celestial moon,boho sun"
    python scripts/run_phase1.py --no-drive --out ./output/research
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from ventures.etsy.pipeline import run_phase_1, SEED_THEMES


def main():
    parser = argparse.ArgumentParser(description="Phase 1: Research and score Etsy themes.")
    parser.add_argument("--themes",    default=None, help="Comma-separated theme list.")
    parser.add_argument("--out",       default="./output/research")
    parser.add_argument("--no-drive",  action="store_true", help="Skip Drive upload.")
    args = parser.parse_args()

    themes = [t.strip() for t in args.themes.split(",")] if args.themes else SEED_THEMES

    print(f"Phase 1 — Theme Research")
    print(f"Themes   : {len(themes)}")
    print(f"Output   : {args.out}")
    print(f"Drive    : {'no' if args.no_drive else 'yes'}")
    print()

    result = run_phase_1(
        seed_themes=themes,
        save_to_drive=not args.no_drive,
        output_dir=args.out,
    )

    print()
    print(f"Results saved:")
    print(f"  CSV  : {result['csv_path']}")
    print(f"  JSON : {result['json_path']}")
    if result.get("drive_csv_id"):
        print(f"  Drive CSV  ID : {result['drive_csv_id']}")
        print(f"  Drive JSON ID : {result['drive_json_id']}")

    print()
    print(f"{'Theme':<35} {'Score':>6}  {'Demand':>7}  {'Comp':>6}  {'Monet':>6}  {'Pass?':>6}")
    print("-" * 75)
    for t in result["themes"]:
        flag = "YES" if t["proceed"] else "-"
        print(f"{t['theme']:<35} {t['score']:>6.1f}  {t['demand']:>7.1f}  "
              f"{t['competition']:>6.1f}  {t['monetisation']:>6.1f}  {flag:>6}")

    print()
    print(f"Passing (>= 60): {result['passing_themes']} / {result['total_themes']}")
    print("Run run_phase2.py with a passing theme slug to generate subjects.")


if __name__ == "__main__":
    main()
