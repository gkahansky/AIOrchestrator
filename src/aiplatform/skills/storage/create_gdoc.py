"""
Skill: create_gdoc
Create a Google Doc from HTML content in a specified Drive folder.

Input:
    title                  (str):  Document title.
    html_content           (str):  HTML string — converted to Google Doc format on upload.
    folder_id              (str):  Drive folder ID to create the doc in.
    share_anyone_with_link (bool): If True, anyone with the link can view. Default: False.

Output:
    {
        "doc_id":         str,  # Google Drive file ID
        "filename":       str,
        "web_view_link":  str,  # https://docs.google.com/document/d/.../view
    }
"""

import io
import os
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_service():
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "./google_credentials.json")
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_gdoc(
    title: str,
    html_content: str,
    folder_id: str,
    share_anyone_with_link: bool = False,
) -> dict:
    """
    Create a Google Doc from HTML content.
    Uploads to Drive with MIME type conversion — Google handles the HTML → Doc transform.
    """
    service = _get_service()

    file_metadata = {
        "name": title,
        "parents": [folder_id],
        "mimeType": "application/vnd.google-apps.document",
    }
    media = MediaIoBaseUpload(
        io.BytesIO(html_content.encode("utf-8")),
        mimetype="text/html",
        resumable=False,
    )

    file = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id,name,webViewLink",
        )
        .execute()
    )

    doc_id = file["id"]

    if share_anyone_with_link:
        service.permissions().create(
            fileId=doc_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute()

    return {
        "doc_id": doc_id,
        "filename": file["name"],
        "web_view_link": file.get("webViewLink", f"https://docs.google.com/document/d/{doc_id}/view"),
    }
