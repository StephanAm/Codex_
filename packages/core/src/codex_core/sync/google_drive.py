import io
from pathlib import Path
from typing import Any

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Google Drive support requires the google-drive extra: uv pip install 'note_taker[google-drive]'"
    ) from exc

from .adapter import AuthRequired

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_DEFAULT_FOLDER = "note-taker-sync"


def run_auth_flow(credentials_path: Path, token_path: Path) -> None:
    """Open a browser for OAuth consent and persist the resulting token."""
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {credentials_path}. "
            "Download it from Google Cloud Console "
            "(APIs & Services → Credentials → OAuth 2.0 Client ID)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), _SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())


class GoogleDriveAdapter:
    def __init__(
        self,
        credentials_path: Path,
        token_path: Path,
        folder_name: str = _DEFAULT_FOLDER,
    ) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._folder_name = folder_name
        self._service: Any = None
        self._folder_id: str | None = None

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service
        creds: Any = None
        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self._token_path), _SCOPES)  # type: ignore[no-untyped-call]
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._token_path.write_text(creds.to_json())
            else:
                raise AuthRequired("Google Drive authorization required. Use the GUI to complete the OAuth flow.")
        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def _get_folder_id(self) -> str:
        if self._folder_id:
            return self._folder_id
        svc = self._get_service()
        results = (
            svc.files()
            .list(
                q=f"name='{self._folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id)",
            )
            .execute()
        )
        files = results.get("files", [])
        if files:
            self._folder_id = files[0]["id"]
        else:
            meta = {
                "name": self._folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            created = svc.files().create(body=meta, fields="id").execute()
            self._folder_id = created["id"]
        assert self._folder_id is not None
        return self._folder_id

    def upload(self, device_id: str, local_db: Path) -> None:
        svc = self._get_service()
        folder_id = self._get_folder_id()
        filename = f"{device_id}.db"
        results = (
            svc.files()
            .list(
                q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
                fields="files(id)",
            )
            .execute()
        )
        files = results.get("files", [])
        media = MediaFileUpload(str(local_db), mimetype="application/octet-stream")
        if files:
            svc.files().update(fileId=files[0]["id"], media_body=media).execute()
        else:
            meta = {"name": filename, "parents": [folder_id]}
            svc.files().create(body=meta, media_body=media).execute()

    def list_devices(self) -> list[str]:
        svc = self._get_service()
        folder_id = self._get_folder_id()
        results = (
            svc.files()
            .list(
                q=f"'{folder_id}' in parents and name contains '.db' and trashed=false",
                fields="files(name)",
            )
            .execute()
        )
        return [f["name"].removesuffix(".db") for f in results.get("files", [])]

    def download(self, device_id: str) -> bytes:
        svc = self._get_service()
        folder_id = self._get_folder_id()
        filename = f"{device_id}.db"
        results = (
            svc.files()
            .list(
                q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
                fields="files(id)",
            )
            .execute()
        )
        files = results.get("files", [])
        if not files:
            raise FileNotFoundError(f"No remote DB for device {device_id!r}")
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, svc.files().get_media(fileId=files[0]["id"]))
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()
