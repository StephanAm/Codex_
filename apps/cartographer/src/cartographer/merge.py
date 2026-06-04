# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Read-only merge: pulls data from a source Mnemo DB into the local mirror.

This is a self-contained adaptation of codex_core's merge logic.  Cartographer
never writes back to the source — it only reads from it.
"""

import os
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MergeResult:
    notes_added: int = 0
    notes_updated: int = 0
    notes_deleted: int = 0
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

    @property
    def total_changes(self) -> int:
        return (
            self.notes_added
            + self.notes_updated
            + self.notes_deleted
            + self.kinds_added
            + self.kinds_updated
            + self.kinds_deleted
            + self.instances_added
            + self.instances_updated
            + self.instances_deleted
            + self.atlas_nodes_added
            + self.atlas_nodes_updated
            + self.atlas_nodes_deleted
            + self.atlas_pages_added
            + self.atlas_pages_updated
            + self.atlas_pages_deleted
        )


def merge_from_bytes(local: sqlite3.Connection, remote_bytes: bytes) -> MergeResult:
    """Merge a remote DB delivered as raw bytes (e.g. downloaded from Drive or local folder)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        f.write(remote_bytes)
        tmp = f.name
    try:
        source = sqlite3.connect(tmp)
        source.row_factory = sqlite3.Row
        return merge(local, source)
    finally:
        source.close()
        os.unlink(tmp)


def merge_from_path(local: sqlite3.Connection, path: Path) -> MergeResult:
    """Merge a source DB opened directly from *path* (read-only)."""
    uri = path.as_uri() + "?mode=ro"
    source = sqlite3.connect(uri, uri=True)
    source.row_factory = sqlite3.Row
    try:
        return merge(local, source)
    finally:
        source.close()


def merge(local: sqlite3.Connection, source: sqlite3.Connection) -> MergeResult:
    """Merge all content from *source* (a Mnemo DB) into *local* (the mirror).

    Tombstones are applied first so a deletion on the source is never overridden
    by a subsequent insert.  Within each table, last-write-wins on updated_at.
    """
    result = MergeResult()

    # Delete order matters: instances before kinds (RESTRICT FK).
    _apply_instance_tombstones(local, source, result)
    _apply_kind_tombstones(local, source, result)
    _merge_instance_kinds(local, source, result)
    _merge_instances(local, source, result)

    _apply_note_tombstones(local, source, result)
    _merge_notes(local, source, result)

    # Atlas: delete pages before nodes, insert nodes before pages.
    _apply_atlas_page_tombstones(local, source, result)
    _apply_atlas_node_tombstones(local, source, result)
    _merge_atlas_nodes(local, source, result)
    _merge_atlas_pages(local, source, result)
    _copy_all_atlas_page_annotations(local, source)

    local.commit()
    return result


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


def _apply_note_tombstones(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    for row in source.execute("SELECT uuid, deleted_at FROM deleted_notes"):
        cur = local.execute("DELETE FROM notes WHERE uuid = ?", (row["uuid"],))
        if cur.rowcount:
            result.notes_deleted += 1
        local.execute(
            "INSERT OR IGNORE INTO deleted_notes (uuid, deleted_at) VALUES (?, ?)",
            (row["uuid"], row["deleted_at"]),
        )


def _merge_notes(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_notes")}

    for row in source.execute("SELECT * FROM notes"):
        uuid = row["uuid"]
        if not uuid or uuid in tombstoned:
            continue

        local_row = local.execute("SELECT id, updated_at FROM notes WHERE uuid = ?", (uuid,)).fetchone()

        if local_row is None:
            local.execute(
                "INSERT INTO notes (uuid, body, created_at, updated_at, time_stamp) VALUES (?, ?, ?, ?, ?)",
                (uuid, row["body"], row["created_at"], row["updated_at"], row["time_stamp"]),
            )
            local_id = local.execute("SELECT id FROM notes WHERE uuid = ?", (uuid,)).fetchone()["id"]
            _copy_note_tags(source, local, row["id"], local_id)
            _copy_note_references(source, local, row["id"], local_id)
            result.notes_added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            local_id = local_row["id"]
            local.execute(
                "UPDATE notes SET body = ?, updated_at = ?, time_stamp = ? WHERE uuid = ?",
                (row["body"], row["updated_at"], row["time_stamp"], uuid),
            )
            local.execute("DELETE FROM note_tags WHERE note_id = ?", (local_id,))
            local.execute("DELETE FROM note_references WHERE note_id = ?", (local_id,))
            _copy_note_tags(source, local, row["id"], local_id)
            _copy_note_references(source, local, row["id"], local_id)
            result.notes_updated += 1


def _copy_note_tags(
    source: sqlite3.Connection, local: sqlite3.Connection, source_note_id: int, local_note_id: int
) -> None:
    for row in source.execute(
        "SELECT t.name FROM tags t JOIN note_tags nt ON nt.tag_id = t.id WHERE nt.note_id = ?",
        (source_note_id,),
    ):
        name = row["name"]
        local.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        tag_id = local.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
            (local_note_id, tag_id),
        )


def _copy_note_references(
    source: sqlite3.Connection, local: sqlite3.Connection, source_note_id: int, local_note_id: int
) -> None:
    for row in source.execute(
        'SELECT r.name FROM "references" r JOIN note_references nr ON nr.reference_id = r.id WHERE nr.note_id = ?',
        (source_note_id,),
    ):
        name = row["name"]
        local.execute('INSERT OR IGNORE INTO "references" (name) VALUES (?)', (name,))
        ref_id = local.execute('SELECT id FROM "references" WHERE name = ?', (name,)).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO note_references (note_id, reference_id) VALUES (?, ?)",
            (local_note_id, ref_id),
        )


# ---------------------------------------------------------------------------
# Instance kinds + instances
# ---------------------------------------------------------------------------


def _apply_instance_tombstones(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    for row in source.execute("SELECT uuid, deleted_at FROM deleted_instances"):
        cur = local.execute("DELETE FROM instances WHERE uuid = ?", (row["uuid"],))
        if cur.rowcount:
            result.instances_deleted += 1
        local.execute(
            "INSERT OR IGNORE INTO deleted_instances (uuid, deleted_at) VALUES (?, ?)",
            (row["uuid"], row["deleted_at"]),
        )


def _apply_kind_tombstones(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    for row in source.execute("SELECT uuid, deleted_at FROM deleted_instance_kinds"):
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


def _merge_instance_kinds(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_instance_kinds")}

    for row in source.execute("SELECT * FROM instance_kinds"):
        uuid = row["uuid"]
        if not uuid or uuid in tombstoned:
            continue

        local_row = local.execute("SELECT id, updated_at FROM instance_kinds WHERE uuid = ?", (uuid,)).fetchone()

        if local_row is None:
            name_conflict = local.execute("SELECT 1 FROM instance_kinds WHERE name = ?", (row["name"],)).fetchone()
            safe_name = f"{row['name']}_{uuid[:8]}" if name_conflict else row["name"]
            local.execute(
                "INSERT INTO instance_kinds (uuid, name, plural, description, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (uuid, safe_name, row["plural"], row["description"], row["created_at"], row["updated_at"]),
            )
            result.kinds_added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            name_conflict = local.execute(
                "SELECT 1 FROM instance_kinds WHERE name = ? AND uuid != ?", (row["name"], uuid)
            ).fetchone()
            safe_name = f"{row['name']}_{uuid[:8]}" if name_conflict else row["name"]
            local.execute(
                "UPDATE instance_kinds SET name = ?, plural = ?, description = ?, updated_at = ? WHERE uuid = ?",
                (safe_name, row["plural"], row["description"], row["updated_at"], uuid),
            )
            result.kinds_updated += 1


def _merge_instances(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_instances")}

    for row in source.execute("SELECT * FROM instances"):
        uuid = row["uuid"]
        if not uuid or uuid in tombstoned:
            continue

        # Remap source instance_kind_id → local instance_kind_id via UUID.
        source_kind = source.execute(
            "SELECT uuid FROM instance_kinds WHERE id = ?", (row["instance_kind_id"],)
        ).fetchone()
        if not source_kind:
            continue
        local_kind = local.execute("SELECT id FROM instance_kinds WHERE uuid = ?", (source_kind["uuid"],)).fetchone()
        if not local_kind:
            continue

        local_row = local.execute("SELECT id, updated_at FROM instances WHERE uuid = ?", (uuid,)).fetchone()

        if local_row is None:
            local.execute(
                "INSERT INTO instances (uuid, name, description, instance_kind_id, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (uuid, row["name"], row["description"], local_kind["id"], row["created_at"], row["updated_at"]),
            )
            local_id = local.execute("SELECT id FROM instances WHERE uuid = ?", (uuid,)).fetchone()["id"]
            _copy_instance_references(source, local, row["id"], local_id)
            result.instances_added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            local_id = local_row["id"]
            local.execute(
                "UPDATE instances SET name = ?, description = ?, instance_kind_id = ?, updated_at = ? WHERE uuid = ?",
                (row["name"], row["description"], local_kind["id"], row["updated_at"], uuid),
            )
            local.execute("DELETE FROM instance_references WHERE instance_id = ?", (local_id,))
            _copy_instance_references(source, local, row["id"], local_id)
            result.instances_updated += 1


def _copy_instance_references(
    source: sqlite3.Connection, local: sqlite3.Connection, source_instance_id: int, local_instance_id: int
) -> None:
    for row in source.execute(
        'SELECT r.name FROM "references" r'
        " JOIN instance_references ir ON ir.reference_id = r.id"
        " WHERE ir.instance_id = ?",
        (source_instance_id,),
    ):
        name = row["name"]
        local.execute('INSERT OR IGNORE INTO "references" (name) VALUES (?)', (name,))
        ref_id = local.execute('SELECT id FROM "references" WHERE name = ?', (name,)).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO instance_references (instance_id, reference_id) VALUES (?, ?)",
            (local_instance_id, ref_id),
        )


# ---------------------------------------------------------------------------
# Atlas
# ---------------------------------------------------------------------------


def _apply_atlas_page_tombstones(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    for row in source.execute("SELECT uuid, deleted_at FROM deleted_atlas_pages"):
        cur = local.execute("DELETE FROM atlas_pages WHERE uuid = ?", (row["uuid"],))
        if cur.rowcount:
            result.atlas_pages_deleted += 1
        local.execute(
            "INSERT OR IGNORE INTO deleted_atlas_pages (uuid, deleted_at) VALUES (?, ?)",
            (row["uuid"], row["deleted_at"]),
        )


def _apply_atlas_node_tombstones(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    for row in source.execute("SELECT uuid, deleted_at FROM deleted_atlas_nodes"):
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


def _merge_atlas_nodes(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_atlas_nodes")}

    for row in source.execute("SELECT * FROM atlas_nodes"):
        uuid = row["uuid"]
        if not uuid or uuid in tombstoned:
            continue

        local_parent_id = None
        if row["parent_id"] is not None:
            source_parent = source.execute("SELECT uuid FROM atlas_nodes WHERE id = ?", (row["parent_id"],)).fetchone()
            if source_parent:
                local_parent = local.execute(
                    "SELECT id FROM atlas_nodes WHERE uuid = ?", (source_parent["uuid"],)
                ).fetchone()
                if local_parent is None:
                    continue  # parent not present yet; will resolve on next sync
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


def _merge_atlas_pages(local: sqlite3.Connection, source: sqlite3.Connection, result: MergeResult) -> None:
    tombstoned = {r["uuid"] for r in local.execute("SELECT uuid FROM deleted_atlas_pages")}

    for row in source.execute("SELECT * FROM atlas_pages"):
        uuid = row["uuid"]
        if not uuid or uuid in tombstoned:
            continue

        source_node = source.execute("SELECT uuid FROM atlas_nodes WHERE id = ?", (row["node_id"],)).fetchone()
        if not source_node:
            continue
        local_node = local.execute("SELECT id FROM atlas_nodes WHERE uuid = ?", (source_node["uuid"],)).fetchone()
        if not local_node:
            continue
        local_node_id = local_node["id"]

        local_row = local.execute("SELECT id, updated_at FROM atlas_pages WHERE uuid = ?", (uuid,)).fetchone()

        if local_row is None:
            existing = local.execute(
                "SELECT id, updated_at FROM atlas_pages WHERE node_id = ?", (local_node_id,)
            ).fetchone()
            if existing:
                # Two different page UUIDs claim the same node — last-write-wins.
                if row["updated_at"] > existing["updated_at"]:
                    local.execute("DELETE FROM atlas_pages WHERE node_id = ?", (local_node_id,))
                    _insert_atlas_page(local, uuid, local_node_id, row)
                    result.atlas_pages_updated += 1
            else:
                _insert_atlas_page(local, uuid, local_node_id, row)
                result.atlas_pages_added += 1
        elif row["updated_at"] > local_row["updated_at"]:
            local.execute(
                "UPDATE atlas_pages SET title = ?, body = ?, updated_at = ?, date_annotation = ? WHERE uuid = ?",
                (row["title"], row["body"], row["updated_at"], row["date_annotation"], uuid),
            )
            result.atlas_pages_updated += 1


def _insert_atlas_page(local: sqlite3.Connection, uuid: str, local_node_id: int, row: sqlite3.Row) -> None:
    local.execute(
        "INSERT INTO atlas_pages"
        " (uuid, node_id, title, body, created_at, updated_at, date_annotation)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uuid, local_node_id, row["title"], row["body"], row["created_at"], row["updated_at"], row["date_annotation"]),
    )


def _copy_all_atlas_page_annotations(local: sqlite3.Connection, source: sqlite3.Connection) -> None:
    """Sync atlas_page_tags and atlas_page_references for all pages present in local."""
    has_tags = _has_table(source, "atlas_page_tags")
    has_refs = _has_table(source, "atlas_page_references")
    if not has_tags and not has_refs:
        return
    for local_page in local.execute("SELECT id, uuid FROM atlas_pages").fetchall():
        source_page = source.execute("SELECT id FROM atlas_pages WHERE uuid = ?", (local_page["uuid"],)).fetchone()
        if not source_page:
            continue
        if has_tags:
            _copy_atlas_page_tags(source, local, source_page["id"], local_page["id"])
        if has_refs:
            _copy_atlas_page_references(source, local, source_page["id"], local_page["id"])


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _copy_atlas_page_tags(
    source: sqlite3.Connection, local: sqlite3.Connection, source_page_id: int, local_page_id: int
) -> None:
    local.execute("DELETE FROM atlas_page_tags WHERE page_id = ?", (local_page_id,))
    for row in source.execute(
        "SELECT t.name FROM tags t JOIN atlas_page_tags apt ON apt.tag_id = t.id WHERE apt.page_id = ?",
        (source_page_id,),
    ):
        name = row["name"]
        local.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        tag_id = local.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO atlas_page_tags (page_id, tag_id) VALUES (?, ?)",
            (local_page_id, tag_id),
        )


def _copy_atlas_page_references(
    source: sqlite3.Connection, local: sqlite3.Connection, source_page_id: int, local_page_id: int
) -> None:
    local.execute("DELETE FROM atlas_page_references WHERE page_id = ?", (local_page_id,))
    for row in source.execute(
        'SELECT r.name FROM "references" r'
        " JOIN atlas_page_references apr ON apr.reference_id = r.id"
        " WHERE apr.page_id = ?",
        (source_page_id,),
    ):
        name = row["name"]
        local.execute('INSERT OR IGNORE INTO "references" (name) VALUES (?)', (name,))
        ref_id = local.execute('SELECT id FROM "references" WHERE name = ?', (name,)).fetchone()["id"]
        local.execute(
            "INSERT OR IGNORE INTO atlas_page_references (page_id, reference_id) VALUES (?, ?)",
            (local_page_id, ref_id),
        )
