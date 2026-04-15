"""
Admin Operations router — maintenance tasks runnable from the admin UI.

  POST /api/platform/admin/cleanup-drive       — delete files > 30d from security/accessibility folders
  GET  /api/platform/admin/cleanup-drive/preview — dry-run, shows what would be deleted
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aiplatform.webapp.auth import require_auth

router = APIRouter()


# ── Folder ID registry ─────────────────────────────────────────────────────────
# Only folders listed here can be cleaned. This is a hard-coded safety list —
# it prevents a misconfigured env var from wiping an unintended Drive folder.

def _get_cleanable_folder_ids() -> list[str]:
    """
    Return the list of Drive folder IDs eligible for 30-day cleanup.
    Only security audit and accessibility audit report folders are included.
    """
    candidates = [
        os.environ.get("DRIVE_SECURITY_ORDERS_ID", ""),
        os.environ.get("DRIVE_SECURITY_SAMPLES_ID", ""),
        os.environ.get("DRIVE_SECURITY_ROOT_ID", ""),
        os.environ.get("DRIVE_ACCESSIBILITY_ORDERS_ID", ""),
        os.environ.get("DRIVE_ACCESSIBILITY_SAMPLES_ID", ""),
        os.environ.get("DRIVE_ACCESSIBILITY_ROOT_ID", ""),
    ]
    # Deduplicate and remove empty strings
    seen = set()
    result = []
    for fid in candidates:
        if fid and fid not in seen:
            seen.add(fid)
            result.append(fid)
    return result


class CleanupResult(BaseModel):
    deleted_count: int
    error_count: int
    dry_run: bool
    cutoff_date: str
    folders_checked: list[str]
    deleted: list[dict]
    errors: list[str]


@router.get("/cleanup-drive/preview", response_model=CleanupResult)
def preview_drive_cleanup(
    max_age_days: int = 30,
    _: str = Depends(require_auth),
) -> CleanupResult:
    """
    Dry-run: show which Drive files would be deleted by the 30-day retention cleanup.
    Does not delete anything.
    """
    folder_ids = _get_cleanable_folder_ids()
    if not folder_ids:
        raise HTTPException(
            status_code=400,
            detail="No cleanable Drive folder IDs configured. "
                   "Set DRIVE_SECURITY_ORDERS_ID or DRIVE_ACCESSIBILITY_ORDERS_ID.",
        )

    from aiplatform.skills.storage.drive_cleanup import cleanup_old_drive_files
    result = cleanup_old_drive_files(folder_ids, max_age_days=max_age_days, dry_run=True)
    return CleanupResult(**result)


@router.post("/cleanup-drive", response_model=CleanupResult)
def run_drive_cleanup(
    max_age_days: int = 30,
    _: str = Depends(require_auth),
) -> CleanupResult:
    """
    Delete files older than max_age_days from security and accessibility audit Drive folders.

    Only operates on folder IDs explicitly set via env vars:
      DRIVE_SECURITY_ORDERS_ID, DRIVE_SECURITY_SAMPLES_ID, DRIVE_SECURITY_ROOT_ID,
      DRIVE_ACCESSIBILITY_ORDERS_ID, DRIVE_ACCESSIBILITY_SAMPLES_ID, DRIVE_ACCESSIBILITY_ROOT_ID

    Never touches any other Drive folders. Never recurses into subfolders.
    """
    folder_ids = _get_cleanable_folder_ids()
    if not folder_ids:
        raise HTTPException(
            status_code=400,
            detail="No cleanable Drive folder IDs configured. "
                   "Set DRIVE_SECURITY_ORDERS_ID or DRIVE_ACCESSIBILITY_ORDERS_ID.",
        )

    from aiplatform.skills.storage.drive_cleanup import cleanup_old_drive_files
    result = cleanup_old_drive_files(folder_ids, max_age_days=max_age_days, dry_run=False)
    return CleanupResult(**result)
