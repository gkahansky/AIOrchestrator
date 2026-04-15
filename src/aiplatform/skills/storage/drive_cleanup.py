"""
Skill: drive_cleanup
Delete files older than N days from specific Google Drive folders.

ONLY operates on explicitly listed folder IDs — never traverses beyond them.
Used for security audit and accessibility audit data retention enforcement (30-day policy).

Input:
    folder_ids    (list[str]):  Drive folder IDs to clean. Only files directly inside
                                these folders are deleted — no recursive descent.
    max_age_days  (int):        Delete files with modifiedTime older than this (default 30).
    dry_run       (bool):       If True, returns what would be deleted without deleting.

Output:
    {
        "deleted": [{"file_id": str, "name": str, "modified": str, "folder_id": str}],
        "skipped": [{"file_id": str, "name": str, "reason": str}],
        "errors":  [str],
        "dry_run": bool,
    }
"""

from datetime import datetime, timezone, timedelta
from typing import Any

from aiplatform.skills.storage._drive_auth import get_drive_service


def cleanup_old_drive_files(
    folder_ids: list[str],
    max_age_days: int = 30,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Delete files older than max_age_days from the listed Drive folders.

    Safety rules:
    - Only deletes files (not folders) directly inside the listed folder_ids
    - Never recurses into subfolders
    - Never accepts a folder_id of "" or "root" — raises ValueError
    - Returns a full audit log of what was deleted / skipped
    """
    if not folder_ids:
        raise ValueError("folder_ids must not be empty")

    for fid in folder_ids:
        if not fid or fid.lower() in ("root", "my drive"):
            raise ValueError(f"Refusing to clean a root-level folder: '{fid}'")

    service = get_drive_service()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    cutoff_str = cutoff.isoformat()

    deleted = []
    skipped = []
    errors = []

    for folder_id in folder_ids:
        try:
            # List files in this folder modified before the cutoff
            # Only files (not folders) — mimeType != folder
            page_token = None
            while True:
                resp = service.files().list(
                    q=(
                        f"'{folder_id}' in parents "
                        f"and mimeType != 'application/vnd.google-apps.folder' "
                        f"and modifiedTime < '{cutoff_str}' "
                        f"and trashed = false"
                    ),
                    fields="nextPageToken, files(id, name, modifiedTime, size)",
                    pageSize=100,
                    pageToken=page_token,
                ).execute()

                for file in resp.get("files", []):
                    file_id = file["id"]
                    name = file["name"]
                    modified = file.get("modifiedTime", "")

                    if dry_run:
                        deleted.append({
                            "file_id": file_id,
                            "name": name,
                            "modified": modified,
                            "folder_id": folder_id,
                            "action": "would_delete",
                        })
                    else:
                        try:
                            service.files().delete(fileId=file_id).execute()
                            deleted.append({
                                "file_id": file_id,
                                "name": name,
                                "modified": modified,
                                "folder_id": folder_id,
                                "action": "deleted",
                            })
                        except Exception as exc:
                            errors.append(f"Failed to delete {name} ({file_id}): {exc}")
                            skipped.append({
                                "file_id": file_id,
                                "name": name,
                                "reason": str(exc),
                            })

                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

        except Exception as exc:
            errors.append(f"Error listing folder {folder_id}: {exc}")

    return {
        "deleted": deleted,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
        "cutoff_date": cutoff_str,
        "folders_checked": folder_ids,
        "deleted_count": len(deleted),
        "error_count": len(errors),
    }
