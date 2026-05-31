"""
Remote DB sync for Cartographer instances.

The model is asymmetric:
  Master  — syncs from Mnemo sources, builds the index, then pushes its DB to
            the remote location.  Never pulls.
  Slave   — pulls the master's DB from the remote location, replacing its own
            entirely.  Never pushes.

There is no merge.  The remote holds a single file (remote_name + ".db") that
represents the authoritative Cartographer DB.  updated_at in db_meta is the
guard: pushing an older DB over a newer remote requires --force.
"""

import shutil
import sqlite3
import tempfile
from pathlib import Path

from cartographer.config import (
    get_drive_credentials_path,
    get_drive_folder,
    get_drive_token_path,
    get_local_folder_path,
    get_remote_name,
    get_source_type,
)
from cartographer.db import connect, get_db_path


class RemoteNewerError(Exception):
    """Raised when the remote DB is newer than the local one and --force is not set."""


def _build_adapter(db_path: Path | None) -> object:
    source_type = get_source_type(db_path)
    if source_type == "local_folder":
        from cartographer.adapters.local_folder import LocalFolderAdapter
        raw = get_local_folder_path(db_path)
        if not raw:
            raise ValueError(
                "Local folder path is not configured. "
                "Run: cartographer sync config local-path <PATH>"
            )
        return LocalFolderAdapter(Path(raw))
    # default: google_drive (also covers mnemo_local — remote operations always
    # need a network/folder location, so mnemo_local falls back to google_drive)
    from cartographer.adapters.google_drive import GoogleDriveAdapter
    return GoogleDriveAdapter(
        credentials_path=get_drive_credentials_path(db_path),
        token_path=get_drive_token_path(db_path),
        folder_name=get_drive_folder(db_path),
    )


def _remote_updated_at(remote_bytes: bytes) -> str | None:
    """Read db_meta.updated_at from a remote DB delivered as bytes."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        f.write(remote_bytes)
        tmp = f.name
    try:
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT updated_at FROM db_meta").fetchone()
            return str(row["updated_at"]) if row and row["updated_at"] else None
        except sqlite3.OperationalError:
            return None
        finally:
            conn.close()
    finally:
        import os
        os.unlink(tmp)


def push(force: bool = False, db_path: Path | None = None) -> str:
    """Upload the local DB to the remote location.

    Raises RemoteNewerError if the remote updated_at is later than the local
    one, unless *force* is True.

    Returns the remote name that was written (e.g. "cartographer").
    """
    local_path = db_path or get_db_path()
    local_conn = connect(db_path)
    local_row = local_conn.execute("SELECT updated_at FROM db_meta").fetchone()
    local_ts: str = local_row["updated_at"] if local_row else ""

    adapter = _build_adapter(db_path)
    remote_name = get_remote_name(db_path)

    # Check whether the remote is newer before overwriting.
    try:
        remote_bytes: bytes = adapter.download(remote_name)  # type: ignore[attr-defined]
        remote_ts = _remote_updated_at(remote_bytes)
        if remote_ts and local_ts and remote_ts > local_ts and not force:
            raise RemoteNewerError(
                f"Remote DB is newer (remote: {remote_ts}, local: {local_ts}). "
                "Use --force to overwrite."
            )
    except FileNotFoundError:
        pass  # no remote yet — first push

    adapter.upload(remote_name, local_path)  # type: ignore[attr-defined]
    return remote_name


def pull(db_path: Path | None = None) -> str:
    """Download the remote DB and replace the local one entirely.

    Returns the updated_at timestamp from the downloaded DB.
    """
    adapter = _build_adapter(db_path)
    remote_name = get_remote_name(db_path)

    remote_bytes: bytes = adapter.download(remote_name)  # type: ignore[attr-defined]

    local_path = db_path or get_db_path()
    local_path.parent.mkdir(parents=True, exist_ok=True)

    # Write atomically via a temp file in the same directory.
    tmp_fd, tmp_path_str = tempfile.mkstemp(dir=local_path.parent, suffix=".db.tmp")
    tmp_path = Path(tmp_path_str)
    try:
        with open(tmp_fd, "wb") as f:
            f.write(remote_bytes)
        shutil.move(str(tmp_path), str(local_path))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    # Read the updated_at from the newly replaced DB.
    conn = connect(db_path)
    row = conn.execute("SELECT updated_at FROM db_meta").fetchone()
    return str(row["updated_at"]) if row and row["updated_at"] else ""
