"""
Sprint 4 script — Phase 6: Create Etsy draft listing.

Reads an approved subject + Phase 3/4 outputs, creates a draft listing on Etsy,
attaches mockup images and delivery.zip, and sends notification with the draft URL.

NEVER publishes listings — agent stops at draft. Human clicks Publish in Etsy.

Usage:
    # Create draft for a single approved listing (auto-finds outputs by slug):
    python scripts/run_phase6.py --slug botanical-01

    # Explicit paths:
    python scripts/run_phase6.py \\
        --subjects output/subjects/botanical-line-art/subjects-botanical-line-art.json \\
        --slug botanical-01

    # Poll Etsy until human publishes (blocks until confirmed or 24h timeout):
    python scripts/run_phase6.py --slug botanical-01 --poll-publish

Options:
    --slug          Subject slug (required)
    --subjects      Path to subjects JSON (default: auto-search ./output/subjects/)
    --out           Local output directory root (default: ./output)
    --no-drive      Skip Drive upload of draft record
    --poll-publish  After draft creation, poll Etsy until human publishes

Environment (must be set in .env):
    ETSY_API_KEY          — Etsy app keystring
    ETSY_ACCESS_TOKEN     — OAuth2 access token
    ETSY_SHOP_ID          — Your shop ID
    HUMAN_REVIEW_EMAIL    — Where to send the draft-ready notification
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".ENV")

from ventures.etsy.pipeline import run_phase_6, poll_for_publish


def main():
    parser = argparse.ArgumentParser(description="Phase 6 — Create Etsy draft listing")
    parser.add_argument("--slug",         required=True, help="Subject slug, e.g. botanical-01")
    parser.add_argument("--subjects",     help="Path to subjects JSON (auto-found if omitted)")
    parser.add_argument("--out",          default="./output", help="Output root dir (default: ./output)")
    parser.add_argument("--no-drive",     action="store_true")
    parser.add_argument("--poll-publish", action="store_true",
                        help="Poll Etsy after draft creation until human publishes")
    args = parser.parse_args()

    slug     = args.slug
    out_root = Path(args.out)

    # ── Load subject ──────────────────────────────────────────────────────────
    subject = _load_subject(slug, args.subjects, out_root)
    if not subject:
        print(f"ERROR: Could not find subject '{slug}' in subjects JSON.")
        sys.exit(1)

    # ── Load Phase 3 result ───────────────────────────────────────────────────
    phase3_result = _load_json(out_root / "images" / slug / "phase3-result.json")
    if not phase3_result:
        # Fallback: use metadata.json for paths
        meta_path = out_root / "images" / slug / "metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            phase3_result = {
                "metadata_path": str(meta_path),
                "mockups": meta.get("mockups", {}),
                "raw_image": meta.get("raw_image", ""),
            }

    # ── Load Phase 4 result ───────────────────────────────────────────────────
    phase4_result = _load_json(out_root / "packages" / slug / "phase4-result.json")
    if not phase4_result:
        zip_path = out_root / "packages" / slug / f"{slug}-delivery.zip"
        if zip_path.exists():
            phase4_result = {"zip_path": str(zip_path)}

    # ── Run Phase 6 ───────────────────────────────────────────────────────────
    print(f"\nPhase 6 — creating Etsy draft for '{slug}'")

    result = run_phase_6(
        subject=subject,
        phase3_result=phase3_result,
        phase4_result=phase4_result,
        output_dir=str(out_root),
        save_to_drive=not args.no_drive,
    )

    if "error" in result:
        print(f"\nERROR: {result['error']}")
        sys.exit(1)

    print(f"\nPhase 6 complete:")
    print(f"  Listing ID:      {result['listing_id']}")
    print(f"  Draft URL:       {result['draft_url']}")
    print(f"  Images uploaded: {result['images_uploaded']}/3")
    print(f"  ZIP uploaded:    {'YES' if result['file_uploaded'] else 'NO'}")
    if result.get("drive_draft_id"):
        print(f"  Drive record:    https://drive.google.com/file/d/{result['drive_draft_id']}/view")

    print(f"\n  -> Open your Etsy Shop Manager and click Publish when ready.")
    print(f"  -> {result['draft_url']}")

    # ── Optionally poll for publish ───────────────────────────────────────────
    if args.poll_publish:
        print(f"\nPolling Etsy for publish confirmation (Ctrl+C to stop)...")
        poll_result = poll_for_publish(draft_records=[result])
        if poll_result["published"]:
            listing_url = poll_result["published"][0].get("url", "")
            print(f"\n  [PUBLISHED] {listing_url}")
        else:
            print(f"\n  Draft still unpublished — run again with --poll-publish to resume.")


def _load_subject(slug: str, subjects_path: str | None, out_root: Path) -> dict | None:
    """Find the subject dict matching slug, searching subjects_path or auto-discovering."""
    candidates = []

    if subjects_path:
        candidates.append(Path(subjects_path))
    else:
        # Auto-discover all subjects JSON files under output/subjects/
        candidates = list((out_root / "subjects").glob("*/subjects-*.json"))

    for path in candidates:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        # subjects JSON is a list
        if isinstance(data, list):
            for s in data:
                if s.get("subject_id") == slug:
                    return s
        # subjects JSON wrapped in {subjects: [...]}
        if isinstance(data, dict):
            for s in data.get("subjects", []):
                if s.get("subject_id") == slug:
                    return s
    return None


def _load_json(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


if __name__ == "__main__":
    main()
