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
        "Google Drive support requires the google-drive extra: uv pip install 'codex-core[google-drive]'"
    ) from exc

from codex_core.logger import get_logger

from .adapter import AuthRequired

_log = get_logger("drive")

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
            creds = Credentials.from_authorized_user_file(str(self._token_path), _SCOPES)
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
            _log.debug("folder id cached: %s", self._folder_id)
            return self._folder_id
        svc = self._get_service()
        _log.debug("looking up Drive folder %r", self._folder_name)
        results = (
            svc.files()
            .list(
                q=f"name='{self._folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id,createdTime)",
            )
            .execute()
        )
        files = results.get("files", [])
        _log.debug("folder lookup returned %d result(s): %s", len(files), files)
        if files:
            files.sort(key=lambda f: f.get("createdTime", ""))
            self._folder_id = files[0]["id"]
            _log.debug("using folder id: %s (createdTime: %s)", self._folder_id, files[0].get("createdTime"))
        else:
            meta = {
                "name": self._folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            created = svc.files().create(body=meta, fields="id").execute()
            self._folder_id = created["id"]
            _log.debug("folder not found — created new folder id: %s", self._folder_id)
        assert self._folder_id is not None
        return self._folder_id

    def upload(self, device_id: str, local_db: Path) -> None:
        svc = self._get_service()
        folder_id = self._get_folder_id()
        filename = f"{device_id}.db"
        _log.debug("upload: checking for existing file %r in folder %s", filename, folder_id)
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
            _log.debug("upload: updating existing file id %s", files[0]["id"])
            svc.files().update(fileId=files[0]["id"], media_body=media).execute()
        else:
            _log.debug("upload: creating new file %r", filename)
            meta = {"name": filename, "parents": [folder_id]}
            svc.files().create(body=meta, media_body=media).execute()
        _log.debug("upload: done")

    def list_devices(self) -> list[str]:
        svc = self._get_service()
        folder_id = self._get_folder_id()
        _log.debug("list_devices: listing files in folder %s", folder_id)
        results = (
            svc.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(name)",
            )
            .execute()
        )
        all_files = results.get("files", [])
        _log.debug("list_devices: raw results (%d files): %s", len(all_files), [f["name"] for f in all_files])
        devices = [
            f["name"].removesuffix(".db")
            for f in all_files
            if f["name"].endswith(".db")
        ]
        _log.debug("list_devices: device ids after .db filter: %s", devices)
        return devices

    def download(self, device_id: str) -> bytes:
        svc = self._get_service()
        folder_id = self._get_folder_id()
        filename = f"{device_id}.db"
        _log.debug("download: looking for %r in folder %s", filename, folder_id)
        results = (
            svc.files()
            .list(
                q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
                fields="files(id)",
            )
            .execute()
        )
        files = results.get("files", [])
        _log.debug("download: found %d match(es) for %r", len(files), filename)
        if not files:
            raise FileNotFoundError(f"No remote DB for device {device_id!r}")
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, svc.files().get_media(fileId=files[0]["id"]))
        done = False
        while not done:
            _, done = downloader.next_chunk()
        _log.debug("download: received %d bytes for %r", len(buf.getvalue()), device_id)
        return buf.getvalue()
