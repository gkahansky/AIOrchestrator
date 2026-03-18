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
import os
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_service():
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "./google_credentials.json")
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def drive_write(
    local_path: str | Path,
    folder_id: str,
    mime_type: Optional[str] = None,
    filename: Optional[str] = None,
) -> dict:
    local_path = Path(local_path)

    if not local_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    resolved_filename = filename or local_path.name
    resolved_mime = mime_type or mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"

    service = _get_service()

    file_metadata = {
        "name": resolved_filename,
        "parents": [folder_id],
    }
    media = MediaFileUpload(str(local_path), mimetype=resolved_mime, resumable=True)

    file = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id,name,webViewLink,size",
        )
        .execute()
    )

    return {
        "file_id": file["id"],
        "filename": file["name"],
        "web_view_link": file.get("webViewLink", ""),
        "size_bytes": int(file.get("size", 0)),
    }
