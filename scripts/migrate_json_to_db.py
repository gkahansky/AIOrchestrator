"""
Phase 1 data migration: import existing order.json files into PostgreSQL.

Scans all output directories for order.json files produced by the
marketing_audit and content_studio pipelines and upserts them into
the jobs table. Safe to run multiple times — uses upsert logic.

Usage:
    python scripts/migrate_json_to_db.py [--dry-run] [--output-dir ./output]
"""

import argparse
import json
import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from aiplatform.database.session import ping
from aiplatform.database.job_ops import upsert_job


# venture_name → subdirectory name inside output_dir
VENTURE_DIRS = {
    "marketing_audit": "marketing_audit",
    "content_studio":  "content_studio",
}


def find_order_files(output_dir: Path, venture_subdir: str) -> list[Path]:
    """Return all order.json files under output_dir/venture_subdir/*/."""
    base = output_dir / venture_subdir
    if not base.exists():
        return []
    return sorted(base.glob("*/order.json"))


def migrate(output_dir: Path, dry_run: bool) -> None:
    if not ping():
        print("[ERROR] Cannot connect to database. Check DATABASE_URL in .ENV.")
        sys.exit(1)

    total = 0
    errors = 0

    for venture, subdir in VENTURE_DIRS.items():
        files = find_order_files(output_dir, subdir)
        print(f"\n{venture}: found {len(files)} order.json file(s) in {output_dir / subdir}")

        for path in files:
            try:
                order = json.loads(path.read_text(encoding="utf-8"))
                order_id = order.get("order_id") or order.get("id") or path.parent.name
                status = order.get("status", "unknown")

                if "order_id" not in order:
                    order["order_id"] = order_id

                print(f"  {'[DRY RUN] ' if dry_run else ''}upsert {order_id} status={status}")

                if not dry_run:
                    upsert_job(order, venture)
                total += 1

            except Exception as exc:
                print(f"  [ERROR] {path}: {exc}")
                errors += 1

    print(f"\nDone. {total} order(s) processed, {errors} error(s).")
    if dry_run:
        print("(dry-run mode — no changes written)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate order.json files to PostgreSQL")
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="Root output directory (default: ./output)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report without writing to the database",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    print(f"Scanning: {output_dir}")
    print(f"Mode:     {'DRY RUN' if args.dry_run else 'LIVE'}")

    migrate(output_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
