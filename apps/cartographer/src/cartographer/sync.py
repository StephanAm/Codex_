"""
Sync: pulls all available Mnemo DBs from the configured source into the local mirror.

Cartographer is read-only with respect to every source — it never writes to them.

Three source types:
  google_drive  — download all *.db files from a shared Google Drive folder (default)
  local_folder  — read all *.db files from a local sync folder
  mnemo_local   — read the local Mnemo instance's DB directly by path
"""

from dataclasses import dataclass, field
from pathlib import Path

from cartographer.config import (
    get_drive_credentials_path,
    get_drive_folder,
    get_drive_token_path,
    get_local_folder_path,
    get_mnemo_db_path,
    get_source_type,
)
from cartographer.db import connect, touch_updated_at
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


# ---------------------------------------------------------------------------
# Per-source-type sync implementations
# ---------------------------------------------------------------------------


def _sync_google_drive(local: object, report: SyncReport, db_path: Path | None) -> None:
    import sqlite3

    from cartographer.adapters.google_drive import GoogleDriveAdapter

    assert isinstance(local, sqlite3.Connection)

    adapter = GoogleDriveAdapter(
        credentials_path=get_drive_credentials_path(db_path),
        token_path=get_drive_token_path(db_path),
        folder_name=get_drive_folder(db_path),
    )
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
    import sqlite3

    from cartographer.adapters.local_folder import LocalFolderAdapter

    assert isinstance(local, sqlite3.Connection)

    raw = get_local_folder_path(db_path)
    if not raw:
        report.results.append(
            (
                "local_folder",
                ValueError("Local folder path is not configured. Run: cartographer sync config local-path <PATH>"),
            )
        )
        return

    adapter = LocalFolderAdapter(Path(raw))
    for device_id in adapter.list_devices():
        try:
            data = adapter.download(device_id)
            result = merge_from_bytes(local, data)
            report.results.append((device_id, result))
        except Exception as exc:
            report.results.append((device_id, exc))


def _sync_mnemo_local(local: object, report: SyncReport, db_path: Path | None) -> None:
    import sqlite3

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
