# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Integration tests for the Google Drive storage adapter.

These tests hit the real Google Drive API and are skipped automatically
when credentials or the google-drive extra are not present.
Run them explicitly with:

    uv run pytest -m integration

Prerequisites:
  - ~/.note_taker/credentials.json  (OAuth client secrets from Google Cloud Console)
  - The google-drive extra installed: uv pip install 'codex-core[google-drive]'
"""

from collections.abc import Generator
from pathlib import Path

import pytest

_CREDS = Path.home() / ".note_taker" / "credentials.json"
_TOKEN = Path.home() / ".note_taker" / "token.json"
_TEST_DEVICE = "__integration_test__"

if not _CREDS.exists():
    pytest.skip("Google Drive credentials not found", allow_module_level=True)

try:
    from codex_core.sync.google_drive import GoogleDriveAdapter
except ImportError:
    pytest.skip("google-drive extra not installed", allow_module_level=True)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def adapter() -> GoogleDriveAdapter:
    return GoogleDriveAdapter(_CREDS, _TOKEN)


@pytest.fixture(autouse=True)
def cleanup_test_device(adapter: GoogleDriveAdapter) -> "Generator[None, None, None]":
    yield
    try:
        svc = adapter._get_service()
        folder_id = adapter._get_folder_id()
        filename = f"{_TEST_DEVICE}.db"
        results = (
            svc.files()
            .list(
                q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
                fields="files(id)",
            )
            .execute()
        )
        for f in results.get("files", []):
            svc.files().delete(fileId=f["id"]).execute()
    except Exception:
        pass


def test_list_devices_returns_list(adapter: GoogleDriveAdapter) -> None:
    devices = adapter.list_devices()
    assert isinstance(devices, list)


def test_upload_then_download_roundtrip(adapter: GoogleDriveAdapter, tmp_path: Path) -> None:
    from codex_core.db import connect
    from codex_core.store import add_note

    db = tmp_path / "test.db"
    add_note("integration test note #test", db_path=db)

    adapter.upload(_TEST_DEVICE, db)
    assert _TEST_DEVICE in adapter.list_devices()

    downloaded = adapter.download(_TEST_DEVICE)
    assert len(downloaded) > 0

    restored = tmp_path / "restored.db"
    restored.write_bytes(downloaded)
    notes = connect(restored).execute("SELECT body FROM notes").fetchall()
    assert any("integration test note" in row[0] for row in notes)


def test_download_nonexistent_device_raises(adapter: GoogleDriveAdapter) -> None:
    with pytest.raises(FileNotFoundError):
        adapter.download("__device_that_does_not_exist__")


def test_upload_overwrites_previous_version(adapter: GoogleDriveAdapter, tmp_path: Path) -> None:
    from codex_core.db import connect
    from codex_core.store import add_note

    db_v1 = tmp_path / "v1.db"
    add_note("version one", db_path=db_v1)
    adapter.upload(_TEST_DEVICE, db_v1)

    db_v2 = tmp_path / "v2.db"
    add_note("version two", db_path=db_v2)
    adapter.upload(_TEST_DEVICE, db_v2)

    assert adapter.list_devices().count(_TEST_DEVICE) == 1

    downloaded = adapter.download(_TEST_DEVICE)
    restored = tmp_path / "restored.db"
    restored.write_bytes(downloaded)
    bodies = [r[0] for r in connect(restored).execute("SELECT body FROM notes")]
    assert any("version two" in b for b in bodies)
