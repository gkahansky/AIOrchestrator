"""
Skill: drive_read
Download a file from Google Drive to a local path.

Input:
    file_id   (str):        Drive file ID.
    dest_path (str | Path): Local path to write the file to.

Output:
    {
        "dest_path":  str,
        "filename":   str,
        "mime_type":  str,
        "size_bytes": int,
    }
"""

import io
import os
from pathlib import Path

from googleapiclient.http import MediaIoBaseDownload

from aiplatform.skills.storage._drive_auth import get_drive_service


def drive_read(file_id: str, dest_path: str | Path) -> dict:
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    service = get_drive_service()

    meta = (
        service.files()
        .get(fileId=file_id, fields="name,mimeType,size")
        .execute()
    )

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    dest_path.write_bytes(buffer.getvalue())

    return {
        "dest_path": str(dest_path),
        "filename": meta["name"],
        "mime_type": meta.get("mimeType", ""),
        "size_bytes": int(meta.get("size", len(buffer.getvalue()))),
    }


def drive_read_json(file_id: str) -> dict:
    """Convenience wrapper — download a JSON file and return parsed content."""
    import json
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name

    try:
        drive_read(file_id, tmp_path)
        with open(tmp_path) as f:
            return json.load(f)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
