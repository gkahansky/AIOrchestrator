"""
Skill: drive_organise
Create folders and move files in Google Drive.

Functions:
    create_folder(name, parent_id)  → { folder_id, name, web_view_link }
    move_file(file_id, dest_folder_id) → { file_id, name }
    list_folder(folder_id)          → [{ file_id, name, mime_type }]
"""

import os
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"


def _get_service():
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "./google_credentials.json")
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_folder(name: str, parent_id: Optional[str] = None) -> dict:
    """
    Create a folder in Google Drive.

    Args:
        name:      Folder display name.
        parent_id: Parent folder ID. If None, creates in root (not recommended).

    Returns:
        { folder_id, name, web_view_link }
    """
    service = _get_service()

    body = {"name": name, "mimeType": FOLDER_MIME}
    if parent_id:
        body["parents"] = [parent_id]

    folder = (
        service.files()
        .create(body=body, fields="id,name,webViewLink")
        .execute()
    )

    return {
        "folder_id": folder["id"],
        "name": folder["name"],
        "web_view_link": folder.get("webViewLink", ""),
    }


def move_file(file_id: str, dest_folder_id: str) -> dict:
    """
    Move a file to a different folder.

    Args:
        file_id:        Drive file ID.
        dest_folder_id: ID of the destination folder.

    Returns:
        { file_id, name }
    """
    service = _get_service()

    # Retrieve current parents so we can remove them
    file = service.files().get(fileId=file_id, fields="id,name,parents").execute()
    current_parents = ",".join(file.get("parents", []))

    updated = (
        service.files()
        .update(
            fileId=file_id,
            addParents=dest_folder_id,
            removeParents=current_parents,
            fields="id,name",
        )
        .execute()
    )

    return {"file_id": updated["id"], "name": updated["name"]}


def list_folder(folder_id: str) -> list[dict]:
    """
    List all files in a Drive folder (non-recursive).

    Returns:
        [{ file_id, name, mime_type }]
    """
    service = _get_service()

    results = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id,name,mimeType)",
            orderBy="name",
        )
        .execute()
    )

    return [
        {"file_id": f["id"], "name": f["name"], "mime_type": f["mimeType"]}
        for f in results.get("files", [])
    ]
