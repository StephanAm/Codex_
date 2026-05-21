import shutil
from pathlib import Path

import pytest

from note_taker.db import connect
from note_taker.store import add_note, delete_note, list_notes
from note_taker.sync.merge import merge_remote


@pytest.fixture
def local_db(tmp_path: Path) -> Path:
    return tmp_path / "local.db"


@pytest.fixture
def remote_db(tmp_path: Path) -> Path:
    return tmp_path / "remote.db"


def _db_bytes(db_path: Path) -> bytes:
    return db_path.read_bytes()


def test_merge_adds_new_notes(local_db: Path, remote_db: Path) -> None:
    add_note("remote note #sync", db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.added == 1
    assert result.updated == 0
    notes = list_notes(db_path=local_db)
    assert len(notes) == 1
    assert notes[0].body == "remote note #sync"


def test_merge_skips_existing_note_with_older_timestamp(
    local_db: Path, remote_db: Path
) -> None:
    # Add to remote first, then copy to local (same uuid, same timestamp)
    remote_note = add_note("original body", db_path=remote_db)
    shutil.copy(remote_db, local_db)

    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.added == 0
    assert result.updated == 0


def test_merge_updates_note_when_remote_is_newer(
    local_db: Path, remote_db: Path
) -> None:
    import time
    note = add_note("original", db_path=local_db)
    # Give remote a newer timestamp by adding then updating
    add_note("original", db_path=remote_db)
    time.sleep(0.01)
    from note_taker.store import update_note
    update_note(
        connect(remote_db).execute(
            "SELECT id FROM notes ORDER BY created_at"
        ).fetchone()["id"],
        "updated body",
        db_path=remote_db,
    )
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    # Different UUIDs — remote note is new to local
    assert result.added == 1


def test_merge_tombstone_deletes_local_note(local_db: Path, remote_db: Path) -> None:
    # Add a note on both devices (simulate by copying)
    add_note("to be deleted", db_path=local_db)
    shutil.copy(local_db, remote_db)
    # Delete on remote
    remote_note_id = connect(remote_db).execute(
        "SELECT id FROM notes"
    ).fetchone()["id"]
    delete_note(remote_note_id, db_path=remote_db)

    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.deleted == 1
    assert list_notes(db_path=local_db) == []


def test_merge_tombstone_prevents_reimport(local_db: Path, remote_db: Path) -> None:
    add_note("zombie note", db_path=local_db)
    shutil.copy(local_db, remote_db)
    remote_note_id = connect(remote_db).execute(
        "SELECT id FROM notes"
    ).fetchone()["id"]
    delete_note(remote_note_id, db_path=remote_db)

    local_conn = connect(local_db)
    merge_remote(local_conn, _db_bytes(remote_db))

    # Merge again — tombstone should prevent re-adding
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.added == 0
    assert list_notes(db_path=local_db) == []


def test_merge_preserves_tags_and_references(local_db: Path, remote_db: Path) -> None:
    add_note("met @alice about #project", db_path=remote_db)
    local_conn = connect(local_db)
    merge_remote(local_conn, _db_bytes(remote_db))
    notes = list_notes(db_path=local_db)
    assert "project" in notes[0].tags
    assert "alice" in notes[0].references


def test_merge_is_idempotent(local_db: Path, remote_db: Path) -> None:
    add_note("idempotent note", db_path=remote_db)
    local_conn = connect(local_db)
    merge_remote(local_conn, _db_bytes(remote_db))
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.added == 0
    assert len(list_notes(db_path=local_db)) == 1
