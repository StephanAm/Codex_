# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import sqlite3
import tempfile
from dataclasses import dataclass


@dataclass
class MergeResult:
    added: int
    updated: int
    deleted: int
    kinds_added: int = 0
    kinds_updated: int = 0
    kinds_deleted: int = 0
    instances_added: int = 0
    instances_updated: int = 0
    instances_deleted: int = 0
    atlas_nodes_added: int = 0
    atlas_nodes_updated: int = 0
    atlas_nodes_deleted: int = 0
    atlas_pages_added: int = 0
    atlas_pages_updated: int = 0
    atlas_pages_deleted: int = 0


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
    result = MergeResult(added=0, updated=0, deleted=0)

    # Apply instance tombstones first — RESTRICT FK means instances must be removed
    # before their kinds can be deleted.
    _apply_instance_tombstones(local, remote, result)
    _apply_kind_tombstones(local, remote, result)
    _merge_instance_kinds(local, remote, result)
    _merge_instances(local, remote, result)

    # Apply note tombstones so we never re-import a deleted note
    for row in remote.execute("SELECT uuid, deleted_at FROM deleted_notes"):
        uuid, deleted_at = row["uuid"], row["deleted_at"]
        cur = local.execute("DELETE FROM notes WHERE uuid = ?", (uuid,))
        if cur.rowcount:
            result.deleted += 1
        local.execute(
            "INSERT OR IGNORE INTO deleted_notes (uuid, deleted_at) VALUES (?, ?)",
            (uuid, deleted_at),
        )

    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_notes")}

    for row in remote.execute("SELECT * FROM notes"):
        uuid = row["uuid"]
        if uuid in tombstoned:
            continue

        local_row = local.execute("SELECT id, updated_at FROM notes WHERE uuid = ?", (uuid,)).fetchone()

        if local_row is None:
            local.execute(
                "INSERT INTO notes (uuid, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (uuid, row["body"], row["created_at"], row["updated_at"]),
            )
            local_id = local.execute("SELECT id FROM notes WHERE uuid = ?", (uuid,)).fetchone()["id"]
            _copy_tags(remote, local, row["id"], local_id)
            _copy_references(remote, local, row["id"], local_id)
            result.added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            local.execute(
                "UPDATE notes SET body = ?, updated_at = ? WHERE uuid = ?",
                (row["body"], row["updated_at"], uuid),
            )
            local_id = local_row["id"]
            local.execute("DELETE FROM note_tags WHERE note_id = ?", (local_id,))
            local.execute("DELETE FROM note_references WHERE note_id = ?", (local_id,))
            _copy_tags(remote, local, row["id"], local_id)
            _copy_references(remote, local, row["id"], local_id)
            result.updated += 1

    # Sync pins — last-write-wins on pins_updated_at
    remote_pins_ts = remote.execute("SELECT value FROM config WHERE key = 'pins_updated_at'").fetchone()
    if remote_pins_ts:
        local_pins_ts = local.execute("SELECT value FROM config WHERE key = 'pins_updated_at'").fetchone()
        if local_pins_ts is None or remote_pins_ts["value"] > local_pins_ts["value"]:
            for key in ("pins", "pins_updated_at"):
                row = remote.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
                if row:
                    local.execute(
                        "INSERT INTO config (key, value) VALUES (?, ?)"
                        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, row["value"]),
                    )

    # Atlas — pages first (child), then nodes (parent), then merge in dependency order
    _apply_atlas_page_tombstones(local, remote, result)
    _apply_atlas_node_tombstones(local, remote, result)
    _merge_atlas_nodes(local, remote, result)
    _merge_atlas_pages(local, remote, result)

    local.commit()
    return result


def _apply_instance_tombstones(
    local: sqlite3.Connection,
    remote: sqlite3.Connection,
    result: MergeResult,
) -> None:
    for row in remote.execute("SELECT uuid, deleted_at FROM deleted_instances"):
        cur = local.execute("DELETE FROM instances WHERE uuid = ?", (row["uuid"],))
        if cur.rowcount:
            result.instances_deleted += 1
        local.execute(
            "INSERT OR IGNORE INTO deleted_instances (uuid, deleted_at) VALUES (?, ?)",
            (row["uuid"], row["deleted_at"]),
        )


def _apply_kind_tombstones(
    local: sqlite3.Connection,
    remote: sqlite3.Connection,
    result: MergeResult,
) -> None:
    for row in remote.execute("SELECT uuid, deleted_at FROM deleted_instance_kinds"):
        try:
            cur = local.execute("DELETE FROM instance_kinds WHERE uuid = ?", (row["uuid"],))
            if cur.rowcount:
                result.kinds_deleted += 1
            local.execute(
                "INSERT OR IGNORE INTO deleted_instance_kinds (uuid, deleted_at) VALUES (?, ?)",
                (row["uuid"], row["deleted_at"]),
            )
        except sqlite3.IntegrityError:
            pass  # local instances still reference this kind; skip


def _merge_instance_kinds(
    local: sqlite3.Connection,
    remote: sqlite3.Connection,
    result: MergeResult,
) -> None:
    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_instance_kinds")}

    for row in remote.execute("SELECT * FROM instance_kinds"):
        uuid = row["uuid"]
        if not uuid or uuid in tombstoned:
            continue

        local_row = local.execute("SELECT id, updated_at FROM instance_kinds WHERE uuid = ?", (uuid,)).fetchone()

        if local_row is None:
            name_conflict = local.execute("SELECT 1 FROM instance_kinds WHERE name = ?", (row["name"],)).fetchone()
            safe_name = f"{row['name']}_{uuid[:8]}" if name_conflict else row["name"]
            local.execute(
                "INSERT INTO instance_kinds"
                " (uuid, name, plural, description, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (uuid, safe_name, row["plural"], row["description"], row["created_at"], row["updated_at"]),
            )
            result.kinds_added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            name_conflict = local.execute(
                "SELECT 1 FROM instance_kinds WHERE name = ? AND uuid != ?",
                (row["name"], uuid),
            ).fetchone()
            safe_name = f"{row['name']}_{uuid[:8]}" if name_conflict else row["name"]
            local.execute(
                "UPDATE instance_kinds SET name = ?, plural = ?, description = ?, updated_at = ? WHERE uuid = ?",
                (safe_name, row["plural"], row["description"], row["updated_at"], uuid),
            )
            result.kinds_updated += 1


def _merge_instances(
    local: sqlite3.Connection,
    remote: sqlite3.Connection,
    result: MergeResult,
) -> None:
    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_instances")}

    for row in remote.execute("SELECT * FROM instances"):
        uuid = row["uuid"]
        if not uuid or uuid in tombstoned:
            continue

        # Remap remote instance_kind_id → local instance_kind_id via kind UUID
        remote_kind = remote.execute(
            "SELECT uuid FROM instance_kinds WHERE id = ?", (row["instance_kind_id"],)
        ).fetchone()
        if not remote_kind:
            continue  # orphaned instance; skip
        local_kind = local.execute("SELECT id FROM instance_kinds WHERE uuid = ?", (remote_kind["uuid"],)).fetchone()
        if not local_kind:
            continue  # kind not present locally (e.g. name conflict prevented insert); skip
        local_kind_id = local_kind["id"]

        local_row = local.execute("SELECT id, updated_at FROM instances WHERE uuid = ?", (uuid,)).fetchone()

        if local_row is None:
            local.execute(
                "INSERT INTO instances"
                " (uuid, name, description, instance_kind_id, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (uuid, row["name"], row["description"], local_kind_id, row["created_at"], row["updated_at"]),
            )
            local_id = local.execute("SELECT id FROM instances WHERE uuid = ?", (uuid,)).fetchone()["id"]
            _copy_instance_references(remote, local, row["id"], local_id)
            result.instances_added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            local_id = local_row["id"]
            local.execute(
                "UPDATE instances SET name = ?, description = ?, instance_kind_id = ?, updated_at = ? WHERE uuid = ?",
                (row["name"], row["description"], local_kind_id, row["updated_at"], uuid),
            )
            local.execute("DELETE FROM instance_references WHERE instance_id = ?", (local_id,))
            _copy_instance_references(remote, local, row["id"], local_id)
            result.instances_updated += 1


def _copy_instance_references(
    remote: sqlite3.Connection,
    local: sqlite3.Connection,
    remote_instance_id: int,
    local_instance_id: int,
) -> None:
    for row in remote.execute(
        'SELECT r.name FROM "references" r'
        " JOIN instance_references ir ON ir.reference_id = r.id"
        " WHERE ir.instance_id = ?",
        (remote_instance_id,),
    ):
        name = row["name"]
        local.execute('INSERT OR IGNORE INTO "references" (name) VALUES (?)', (name,))
        ref_id = local.execute('SELECT id FROM "references" WHERE name = ?', (name,)).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO instance_references (instance_id, reference_id) VALUES (?, ?)",
            (local_instance_id, ref_id),
        )


def _copy_tags(
    remote: sqlite3.Connection,
    local: sqlite3.Connection,
    remote_note_id: int,
    local_note_id: int,
) -> None:
    for row in remote.execute(
        "SELECT t.name FROM tags t JOIN note_tags nt ON nt.tag_id = t.id WHERE nt.note_id = ?",
        (remote_note_id,),
    ):
        name = row["name"]
        local.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        tag_id = local.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
            (local_note_id, tag_id),
        )


def _copy_references(
    remote: sqlite3.Connection,
    local: sqlite3.Connection,
    remote_note_id: int,
    local_note_id: int,
) -> None:
    for row in remote.execute(
        'SELECT r.name FROM "references" r JOIN note_references nr ON nr.reference_id = r.id WHERE nr.note_id = ?',
        (remote_note_id,),
    ):
        name = row["name"]
        local.execute('INSERT OR IGNORE INTO "references" (name) VALUES (?)', (name,))
        reference_id = local.execute('SELECT id FROM "references" WHERE name = ?', (name,)).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO note_references (note_id, reference_id) VALUES (?, ?)",
            (local_note_id, reference_id),
        )


def _apply_atlas_page_tombstones(
    local: sqlite3.Connection,
    remote: sqlite3.Connection,
    result: MergeResult,
) -> None:
    for row in remote.execute("SELECT uuid, deleted_at FROM deleted_atlas_pages"):
        cur = local.execute("DELETE FROM atlas_pages WHERE uuid = ?", (row["uuid"],))
        if cur.rowcount:
            result.atlas_pages_deleted += 1
        local.execute(
            "INSERT OR IGNORE INTO deleted_atlas_pages (uuid, deleted_at) VALUES (?, ?)",
            (row["uuid"], row["deleted_at"]),
        )


def _apply_atlas_node_tombstones(
    local: sqlite3.Connection,
    remote: sqlite3.Connection,
    result: MergeResult,
) -> None:
    for row in remote.execute("SELECT uuid, deleted_at FROM deleted_atlas_nodes"):
        # Delete the node's page first if still present (no cascade)
        node_row = local.execute("SELECT id FROM atlas_nodes WHERE uuid = ?", (row["uuid"],)).fetchone()
        if node_row:
            local.execute("DELETE FROM atlas_pages WHERE node_id = ?", (node_row["id"],))
        cur = local.execute("DELETE FROM atlas_nodes WHERE uuid = ?", (row["uuid"],))
        if cur.rowcount:
            result.atlas_nodes_deleted += 1
        local.execute(
            "INSERT OR IGNORE INTO deleted_atlas_nodes (uuid, deleted_at) VALUES (?, ?)",
            (row["uuid"], row["deleted_at"]),
        )


def _merge_atlas_nodes(
    local: sqlite3.Connection,
    remote: sqlite3.Connection,
    result: MergeResult,
) -> None:
    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_atlas_nodes")}

    for row in remote.execute("SELECT * FROM atlas_nodes"):
        uuid = row["uuid"]
        if not uuid or uuid in tombstoned:
            continue

        # Remap remote parent_id → local parent_id via UUID
        local_parent_id = None
        if row["parent_id"] is not None:
            remote_parent = remote.execute("SELECT uuid FROM atlas_nodes WHERE id = ?", (row["parent_id"],)).fetchone()
            if remote_parent:
                local_parent = local.execute(
                    "SELECT id FROM atlas_nodes WHERE uuid = ?", (remote_parent["uuid"],)
                ).fetchone()
                if local_parent is None:
                    continue  # parent not present locally yet; skip (resolves on next sync)
                local_parent_id = local_parent["id"]

        local_row = local.execute("SELECT id, updated_at FROM atlas_nodes WHERE uuid = ?", (uuid,)).fetchone()

        if local_row is None:
            local.execute(
                "INSERT INTO atlas_nodes (uuid, name, parent_id, position, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (uuid, row["name"], local_parent_id, row["position"], row["created_at"], row["updated_at"]),
            )
            result.atlas_nodes_added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            local.execute(
                "UPDATE atlas_nodes SET name = ?, parent_id = ?, position = ?, updated_at = ? WHERE uuid = ?",
                (row["name"], local_parent_id, row["position"], row["updated_at"], uuid),
            )
            result.atlas_nodes_updated += 1


def _merge_atlas_pages(
    local: sqlite3.Connection,
    remote: sqlite3.Connection,
    result: MergeResult,
) -> None:
    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_atlas_pages")}

    for row in remote.execute("SELECT * FROM atlas_pages"):
        uuid = row["uuid"]
        if not uuid or uuid in tombstoned:
            continue

        # Remap remote node_id → local node_id via node UUID
        remote_node = remote.execute("SELECT uuid FROM atlas_nodes WHERE id = ?", (row["node_id"],)).fetchone()
        if not remote_node:
            continue
        local_node = local.execute("SELECT id FROM atlas_nodes WHERE uuid = ?", (remote_node["uuid"],)).fetchone()
        if not local_node:
            continue
        local_node_id = local_node["id"]

        local_row = local.execute("SELECT id, updated_at FROM atlas_pages WHERE uuid = ?", (uuid,)).fetchone()

        if local_row is None:
            # Check if node already has a page (conflict: different page UUIDs on same node)
            existing = local.execute(
                "SELECT id, updated_at FROM atlas_pages WHERE node_id = ?", (local_node_id,)
            ).fetchone()
            if existing:
                # Last-write-wins: replace if remote is newer
                if row["updated_at"] > existing["updated_at"]:
                    local.execute("DELETE FROM atlas_pages WHERE node_id = ?", (local_node_id,))
                    local.execute(
                        "INSERT INTO atlas_pages (uuid, node_id, title, body, created_at, updated_at)"
                        " VALUES (?, ?, ?, ?, ?, ?)",
                        (uuid, local_node_id, row["title"], row["body"], row["created_at"], row["updated_at"]),
                    )
                    result.atlas_pages_updated += 1
            else:
                local.execute(
                    "INSERT INTO atlas_pages (uuid, node_id, title, body, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (uuid, local_node_id, row["title"], row["body"], row["created_at"], row["updated_at"]),
                )
                result.atlas_pages_added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            local.execute(
                "UPDATE atlas_pages SET title = ?, body = ?, updated_at = ? WHERE uuid = ?",
                (row["title"], row["body"], row["updated_at"], uuid),
            )
            result.atlas_pages_updated += 1
