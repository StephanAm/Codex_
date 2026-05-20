import os
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MergeResult:
    added: int
    updated: int
    deleted: int


def merge_remote(local_conn: sqlite3.Connection, remote_bytes: bytes) -> MergeResult:
    """Merge a remote DB (as raw bytes) into the local connection."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        f.write(remote_bytes)
        tmp = f.name
    try:
        remote = sqlite3.connect(tmp)
        remote.row_factory = sqlite3.Row
        return _merge(local_conn, remote)
    finally:
        remote.close()
        os.unlink(tmp)


def _merge(local: sqlite3.Connection, remote: sqlite3.Connection) -> MergeResult:
    added = updated = deleted = 0

    # Apply tombstones first so we never re-import a deleted note
    for row in remote.execute("SELECT uuid, deleted_at FROM deleted_notes"):
        uuid, deleted_at = row["uuid"], row["deleted_at"]
        cur = local.execute("DELETE FROM notes WHERE uuid = ?", (uuid,))
        if cur.rowcount:
            deleted += 1
        local.execute(
            "INSERT OR IGNORE INTO deleted_notes (uuid, deleted_at) VALUES (?, ?)",
            (uuid, deleted_at),
        )

    tombstoned = {
        r["uuid"] for r in local.execute("SELECT uuid FROM deleted_notes")
    }

    for row in remote.execute("SELECT * FROM notes"):
        uuid = row["uuid"]
        if uuid in tombstoned:
            continue

        local_row = local.execute(
            "SELECT id, updated_at FROM notes WHERE uuid = ?", (uuid,)
        ).fetchone()

        if local_row is None:
            local.execute(
                "INSERT INTO notes (uuid, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (uuid, row["body"], row["created_at"], row["updated_at"]),
            )
            local_id = local.execute(
                "SELECT id FROM notes WHERE uuid = ?", (uuid,)
            ).fetchone()["id"]
            _copy_tags(remote, local, row["id"], local_id)
            _copy_entities(remote, local, row["id"], local_id)
            added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            local.execute(
                "UPDATE notes SET body = ?, updated_at = ? WHERE uuid = ?",
                (row["body"], row["updated_at"], uuid),
            )
            local_id = local_row["id"]
            local.execute("DELETE FROM note_tags WHERE note_id = ?", (local_id,))
            local.execute("DELETE FROM note_entities WHERE note_id = ?", (local_id,))
            _copy_tags(remote, local, row["id"], local_id)
            _copy_entities(remote, local, row["id"], local_id)
            updated += 1

    # Sync pins — last-write-wins on pins_updated_at
    remote_pins_ts = remote.execute(
        "SELECT value FROM config WHERE key = 'pins_updated_at'"
    ).fetchone()
    if remote_pins_ts:
        local_pins_ts = local.execute(
            "SELECT value FROM config WHERE key = 'pins_updated_at'"
        ).fetchone()
        if local_pins_ts is None or remote_pins_ts["value"] > local_pins_ts["value"]:
            for key in ("pins", "pins_updated_at"):
                row = remote.execute(
                    "SELECT value FROM config WHERE key = ?", (key,)
                ).fetchone()
                if row:
                    local.execute(
                        "INSERT INTO config (key, value) VALUES (?, ?)"
                        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, row["value"]),
                    )

    local.commit()
    return MergeResult(added=added, updated=updated, deleted=deleted)


def _copy_tags(
    remote: sqlite3.Connection,
    local: sqlite3.Connection,
    remote_note_id: int,
    local_note_id: int,
) -> None:
    for row in remote.execute(
        "SELECT t.name FROM tags t"
        " JOIN note_tags nt ON nt.tag_id = t.id"
        " WHERE nt.note_id = ?",
        (remote_note_id,),
    ):
        name = row["name"]
        local.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        tag_id = local.execute(
            "SELECT id FROM tags WHERE name = ?", (name,)
        ).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
            (local_note_id, tag_id),
        )


def _copy_entities(
    remote: sqlite3.Connection,
    local: sqlite3.Connection,
    remote_note_id: int,
    local_note_id: int,
) -> None:
    for row in remote.execute(
        "SELECT e.name, e.entity_type FROM entities e"
        " JOIN note_entities ne ON ne.entity_id = e.id"
        " WHERE ne.note_id = ?",
        (remote_note_id,),
    ):
        name = row["name"]
        local.execute("INSERT OR IGNORE INTO entities (name) VALUES (?)", (name,))
        if row["entity_type"]:
            local.execute(
                "UPDATE entities SET entity_type = ? WHERE name = ? AND entity_type IS NULL",
                (row["entity_type"], name),
            )
        entity_id = local.execute(
            "SELECT id FROM entities WHERE name = ?", (name,)
        ).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO note_entities (note_id, entity_id) VALUES (?, ?)",
            (local_note_id, entity_id),
        )
