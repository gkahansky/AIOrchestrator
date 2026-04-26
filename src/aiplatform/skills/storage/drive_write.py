"""
Skill: drive_write
Write a local file to a Google Drive folder.

Input:
    local_path  (str | Path): Path to the local file.
    folder_id   (str):        Drive folder ID to upload into.
    mime_type   (str):        Optional MIME type override. Auto-detected if omitted.
    filename    (str):        Optional filename override. Uses local filename if omitted.

Output:
    {
        "file_id":       str,   # Drive file ID
        "filename":      str,
        "web_view_link": str,   # https://drive.google.com/file/d/.../view
        "size_bytes":    int,
    }
"""

import mimetypes
import time
from pathlib import Path
from typing import Optional

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from aiplatform.skills.storage._drive_auth import get_drive_service

# Google Drive transiently returns 500/503 — retry up to 3 times with backoff.
_RETRYABLE_STATUS = {500, 502, 503, 504}
_MAX_RETRIES = 3


def _execute_with_retry(request):
    """Execute a Drive API request, retrying on transient 5xx errors."""
    delay = 2.0
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return request.execute()
        except HttpError as exc:
            if exc.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                print(f"  drive_write: Drive API {exc.status_code} — retrying in {delay:.0f}s (attempt {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(delay)
                delay *= 2
            else:
                raise


def drive_write(
    local_path: str | Path,
    folder_id: str,
    mime_type: Optional[str] = None,
    filename: Optional[str] = None,
    share_anyone_with_link: bool = False,
) -> dict:
    local_path = Path(local_path)

    if not local_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    resolved_filename = filename or local_path.name
    resolved_mime = mime_type or mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"

    service = get_drive_service()

    file_metadata = {
        "name": resolved_filename,
        "parents": [folder_id],
    }
    media = MediaFileUpload(str(local_path), mimetype=resolved_mime, resumable=True)

    file = _execute_with_retry(
        service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,name,webViewLink,size",
        )
    )

    if share_anyone_with_link:
        _execute_with_retry(
            service.permissions().create(
                fileId=file["id"],
                body={"type": "anyone", "role": "reader"},
                fields="id",
            )
        )

    return {
        "file_id": file["id"],
        "filename": file["name"],
        "web_view_link": file.get("webViewLink", ""),
        "size_bytes": int(file.get("size", 0)),
    }
