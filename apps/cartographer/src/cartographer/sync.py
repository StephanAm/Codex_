# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Sync: push and pull Mnemo DBs between the local mirror and the configured source.

Three source types:
  google_drive  — shared Google Drive folder (default)
  local_folder  — local sync folder on disk
  mnemo_local   — read the local Mnemo instance's DB directly by path (pull only)
"""

import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cartographer.config import (
    CREDENTIALS_PATH,
    TOKEN_PATH,
    get_device_id,
    get_drive_folder,
    get_local_folder_path,
    get_mnemo_db_path,
    get_source_type,
)
from cartographer.db import connect, get_db_path, touch_updated_at
from cartographer.merge import MergeResult, merge_from_bytes, merge_from_path


@dataclass
class SyncReport:
    source_type: str
    results: list[tuple[str, MergeResult | Exception]] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return sum(r.total_changes for _, r in self.results if isinstance(r, MergeResult))

    @property
    def errors(self) -> list[tuple[str, Exception]]:
        return [(label, exc) for label, exc in self.results if isinstance(exc, Exception)]


def sync(db_path: Path | None = None) -> SyncReport:
    """Pull from the configured source and merge into the local mirror."""
    source_type = get_source_type(db_path)
    local = connect(db_path)
    report = SyncReport(source_type=source_type)

    if source_type == "google_drive":
        _sync_google_drive(local, report, db_path)
    elif source_type == "local_folder":
        _sync_local_folder(local, report, db_path)
    elif source_type == "mnemo_local":
        _sync_mnemo_local(local, report, db_path)
    else:
        raise ValueError(f"Unknown source type: {source_type!r}")

    if report.total_changes > 0:
        touch_updated_at(local)

    return report


def sync_push(db_path: Path | None = None) -> tuple[str, str]:
    """Upload the local mirror to the configured source as {device_id}.db.

    Returns (device_id, source_type).
    Not supported for mnemo_local (no writable sync folder).
    """
    source_type = get_source_type(db_path)
    if source_type == "mnemo_local":
        raise ValueError("sync push is not supported for the mnemo_local source.")
    device_id = get_device_id(db_path)
    actual_db = db_path or get_db_path()
    tmp = _create_mirror_export(actual_db)
    try:
        adapter = _build_adapter(source_type, db_path)
        adapter.upload(device_id, tmp)
    finally:
        tmp.unlink(missing_ok=True)
    return device_id, source_type


# ---------------------------------------------------------------------------
# Per-source-type sync implementations
# ---------------------------------------------------------------------------


def _build_adapter(source_type: str, db_path: Path | None) -> Any:
    if source_type == "google_drive":
        from cartographer.adapters.google_drive import GoogleDriveAdapter

        return GoogleDriveAdapter(
            credentials_path=CREDENTIALS_PATH,
            token_path=TOKEN_PATH,
            folder_name=get_drive_folder(db_path),
        )
    if source_type == "local_folder":
        from cartographer.adapters.local_folder import LocalFolderAdapter

        raw = get_local_folder_path(db_path)
        if not raw:
            raise ValueError("Local folder path is not configured. Run: carto sync config local-path <PATH>")
        return LocalFolderAdapter(Path(raw))
    raise ValueError(f"Unknown source type: {source_type!r}")


def _create_mirror_export(db_path: Path) -> Path:
    """Return a temp DB file containing only the note-data mirror tables.

    Cartographer-specific tables (embeddings, index_state, db_meta) are stripped
    so the export looks like a standard Mnemo device DB to consumers.
    """
    tmp = Path(tempfile.mktemp(suffix=".db"))
    shutil.copy2(db_path, tmp)
    conn = sqlite3.connect(tmp)
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in ("embeddings", "index_state", "db_meta"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute("DELETE FROM config WHERE key != 'device_id'")
    conn.commit()
    conn.execute("VACUUM")  # must run outside a transaction
    conn.close()
    return tmp


def _sync_google_drive(local: object, report: SyncReport, db_path: Path | None) -> None:
    assert isinstance(local, sqlite3.Connection)

    try:
        adapter = _build_adapter("google_drive", db_path)
    except Exception as exc:
        report.results.append(("google_drive", exc))
        return
    try:
        devices = adapter.list_devices()
    except Exception as exc:
        report.results.append(("google_drive", exc))
        return

    for device_id in devices:
        try:
            data = adapter.download(device_id)
            result = merge_from_bytes(local, data)
            report.results.append((device_id, result))
        except Exception as exc:
            report.results.append((device_id, exc))


def _sync_local_folder(local: object, report: SyncReport, db_path: Path | None) -> None:
    assert isinstance(local, sqlite3.Connection)

    raw = get_local_folder_path(db_path)
    if not raw:
        report.results.append(
            (
                "local_folder",
                ValueError("Local folder path is not configured. Run: carto sync config local-path <PATH>"),
            )
        )
        return

    try:
        adapter = _build_adapter("local_folder", db_path)
    except Exception as exc:
        report.results.append(("local_folder", exc))
        return

    for device_id in adapter.list_devices():
        try:
            data = adapter.download(device_id)
            result = merge_from_bytes(local, data)
            report.results.append((device_id, result))
        except Exception as exc:
            report.results.append((device_id, exc))


def _sync_mnemo_local(local: object, report: SyncReport, db_path: Path | None) -> None:
    assert isinstance(local, sqlite3.Connection)

    raw = get_mnemo_db_path(db_path)
    path = Path(raw)
    if not path.exists():
        report.results.append(
            (
                raw,
                FileNotFoundError(f"Mnemo DB not found: {raw}"),
            )
        )
        return

    try:
        result = merge_from_path(local, path)
        report.results.append((raw, result))
    except Exception as exc:
        report.results.append((raw, exc))
