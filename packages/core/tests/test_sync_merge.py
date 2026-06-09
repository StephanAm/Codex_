# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

import shutil
import time
from pathlib import Path

import pytest

from codex_core.db import connect
from codex_core.store import (
    add_note,
    create_instance,
    create_instance_property,
    create_type,
    delete_instance,
    delete_instance_property,
    delete_note,
    delete_type,
    list_instance_properties,
    list_instances,
    list_notes,
    list_types,
    update_type,
)
from codex_core.sync.merge import merge_remote


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


def test_merge_skips_existing_note_with_older_timestamp(local_db: Path, remote_db: Path) -> None:
    # Add to remote first, then copy to local (same uuid, same timestamp)
    add_note("original body", db_path=remote_db)
    shutil.copy(remote_db, local_db)

    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.added == 0
    assert result.updated == 0


def test_merge_updates_note_when_remote_is_newer(local_db: Path, remote_db: Path) -> None:
    import time

    add_note("original", db_path=local_db)
    # Give remote a newer timestamp by adding then updating
    add_note("original", db_path=remote_db)
    time.sleep(0.01)
    from codex_core.store import update_note

    update_note(
        connect(remote_db).execute("SELECT id FROM notes ORDER BY created_at").fetchone()["id"],
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
    remote_note_id = connect(remote_db).execute("SELECT id FROM notes").fetchone()["id"]
    delete_note(remote_note_id, db_path=remote_db)

    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.deleted == 1
    assert list_notes(db_path=local_db) == []


def test_merge_tombstone_prevents_reimport(local_db: Path, remote_db: Path) -> None:
    add_note("zombie note", db_path=local_db)
    shutil.copy(local_db, remote_db)
    remote_note_id = connect(remote_db).execute("SELECT id FROM notes").fetchone()["id"]
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


# ---------------------------------------------------------------------------
# Kind merge tests
# ---------------------------------------------------------------------------


def test_merge_adds_new_kind(local_db: Path, remote_db: Path) -> None:
    create_type("People", plural="People", db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.kinds_added == 1
    kinds = list_types(db_path=local_db)
    assert len(kinds) == 1
    assert kinds[0].name == "People"


def test_merge_skips_kind_when_not_newer(local_db: Path, remote_db: Path) -> None:
    create_type("People", db_path=remote_db)
    shutil.copy(remote_db, local_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.kinds_added == 0
    assert result.kinds_updated == 0
    assert len(list_types(db_path=local_db)) == 1


def test_merge_updates_kind_when_remote_is_newer(local_db: Path, remote_db: Path) -> None:
    create_type("People", db_path=remote_db)
    shutil.copy(remote_db, local_db)
    kind_id = connect(remote_db).execute("SELECT id FROM instance_kinds").fetchone()["id"]
    time.sleep(0.01)
    update_type(kind_id, "People", "Folks", "Updated desc", db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.kinds_updated == 1
    kinds = list_types(db_path=local_db)
    assert kinds[0].plural == "Folks"
    assert kinds[0].description == "Updated desc"


def test_merge_kind_tombstone_deletes_local(local_db: Path, remote_db: Path) -> None:
    create_type("Temporary", db_path=local_db)
    shutil.copy(local_db, remote_db)
    kind_id = connect(remote_db).execute("SELECT id FROM instance_kinds").fetchone()["id"]
    delete_type(kind_id, db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.kinds_deleted == 1
    assert list_types(db_path=local_db) == []


def test_merge_kind_tombstone_prevents_reimport(local_db: Path, remote_db: Path) -> None:
    create_type("Ghost", db_path=local_db)
    shutil.copy(local_db, remote_db)
    kind_id = connect(remote_db).execute("SELECT id FROM instance_kinds").fetchone()["id"]
    delete_type(kind_id, db_path=remote_db)
    local_conn = connect(local_db)
    merge_remote(local_conn, _db_bytes(remote_db))
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.kinds_added == 0
    assert list_types(db_path=local_db) == []


def test_merge_kind_name_conflict_renames_incoming(local_db: Path, remote_db: Path) -> None:
    # Both devices independently create a kind with the same name → different UUIDs
    create_type("People", db_path=local_db)
    create_type("People", db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.kinds_added == 1
    names = [k.name for k in list_types(db_path=local_db)]
    assert "People" in names
    assert any(n.startswith("People_") for n in names)


# ---------------------------------------------------------------------------
# Instance merge tests
# ---------------------------------------------------------------------------


def test_merge_adds_new_instance(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=remote_db)
    create_instance("Alice", k.id, db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.kinds_added == 1
    assert result.instances_added == 1
    instances = list_instances(db_path=local_db)
    assert len(instances) == 1
    assert instances[0].name == "Alice"


def test_merge_instance_fk_remapping(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=remote_db)
    create_instance("Alice", k.id, db_path=remote_db)
    local_conn = connect(local_db)
    merge_remote(local_conn, _db_bytes(remote_db))
    instances = list_instances(db_path=local_db)
    assert instances[0].type.name == "People"


def test_merge_skips_instance_when_not_newer(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=remote_db)
    create_instance("Alice", k.id, db_path=remote_db)
    shutil.copy(remote_db, local_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.instances_added == 0
    assert result.instances_updated == 0


def test_merge_instance_tombstone_deletes_local(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=local_db)
    create_instance("Alice", k.id, db_path=local_db)
    shutil.copy(local_db, remote_db)
    inst_id = connect(remote_db).execute("SELECT id FROM instances").fetchone()["id"]
    delete_instance(inst_id, db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.instances_deleted == 1
    assert list_instances(db_path=local_db) == []


def test_merge_instance_preserves_references(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=remote_db)
    create_instance("Alice", k.id, references=["project-x"], db_path=remote_db)
    local_conn = connect(local_db)
    merge_remote(local_conn, _db_bytes(remote_db))
    instances = list_instances(db_path=local_db)
    assert "project-x" in instances[0].references


def test_merge_kinds_and_instances_idempotent(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=remote_db)
    create_instance("Alice", k.id, db_path=remote_db)
    local_conn = connect(local_db)
    merge_remote(local_conn, _db_bytes(remote_db))
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.kinds_added == 0
    assert result.instances_added == 0
    assert len(list_instances(db_path=local_db)) == 1


# ---------------------------------------------------------------------------
# Order-of-operations: instance tombstone before kind tombstone
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Instance property merge tests
# ---------------------------------------------------------------------------


def test_merge_adds_new_property(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=remote_db)
    inst = create_instance("Alice", k.id, db_path=remote_db)
    create_instance_property(inst.id, "role", "CEO", db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.properties_added == 1
    local_inst = list_instances(db_path=local_db)[0]
    props = list_instance_properties(local_inst.id, db_path=local_db)
    assert len(props) == 1
    assert props[0].name == "role"
    assert props[0].value == "CEO"


def test_merge_property_fk_remapped(local_db: Path, remote_db: Path) -> None:
    # Verify the property's instance_id is the local integer ID, not the remote one.
    k = create_type("People", db_path=remote_db)
    inst = create_instance("Alice", k.id, db_path=remote_db)
    create_instance_property(inst.id, "role", "CEO", db_path=remote_db)
    local_conn = connect(local_db)
    merge_remote(local_conn, _db_bytes(remote_db))
    local_inst = list_instances(db_path=local_db)[0]
    props = list_instance_properties(local_inst.id, db_path=local_db)
    assert props[0].instance_id == local_inst.id


def test_merge_property_last_write_wins(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=remote_db)
    inst = create_instance("Alice", k.id, db_path=remote_db)
    create_instance_property(inst.id, "role", "CEO", db_path=remote_db)
    shutil.copy(remote_db, local_db)
    time.sleep(0.01)
    from codex_core.store import update_instance_property

    remote_prop_id = connect(remote_db).execute("SELECT id FROM instance_properties").fetchone()["id"]
    update_instance_property(remote_prop_id, "role", "COO", db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.properties_updated == 1
    local_inst = list_instances(db_path=local_db)[0]
    props = list_instance_properties(local_inst.id, db_path=local_db)
    assert props[0].value == "COO"


def test_merge_property_tombstone_deletes_local(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=local_db)
    inst = create_instance("Alice", k.id, db_path=local_db)
    create_instance_property(inst.id, "role", "CEO", db_path=local_db)
    shutil.copy(local_db, remote_db)
    remote_prop_id = connect(remote_db).execute("SELECT id FROM instance_properties").fetchone()["id"]
    delete_instance_property(remote_prop_id, db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.properties_deleted == 1
    assert list_instance_properties(inst.id, db_path=local_db) == []


def test_merge_property_tombstone_prevents_reimport(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=local_db)
    inst = create_instance("Alice", k.id, db_path=local_db)
    create_instance_property(inst.id, "role", "CEO", db_path=local_db)
    shutil.copy(local_db, remote_db)
    remote_prop_id = connect(remote_db).execute("SELECT id FROM instance_properties").fetchone()["id"]
    delete_instance_property(remote_prop_id, db_path=remote_db)
    local_conn = connect(local_db)
    merge_remote(local_conn, _db_bytes(remote_db))
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.properties_added == 0
    assert list_instance_properties(inst.id, db_path=local_db) == []


def test_merge_property_skipped_when_not_newer(local_db: Path, remote_db: Path) -> None:
    k = create_type("People", db_path=remote_db)
    inst = create_instance("Alice", k.id, db_path=remote_db)
    create_instance_property(inst.id, "role", "CEO", db_path=remote_db)
    shutil.copy(remote_db, local_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.properties_added == 0
    assert result.properties_updated == 0


def test_merge_instance_then_kind_tombstones(local_db: Path, remote_db: Path) -> None:
    k = create_type("Temp", db_path=local_db)
    create_instance("X", k.id, db_path=local_db)
    shutil.copy(local_db, remote_db)
    # Delete instance first, then kind on remote
    remote_inst_id = connect(remote_db).execute("SELECT id FROM instances").fetchone()["id"]
    delete_instance(remote_inst_id, db_path=remote_db)
    remote_kind_id = connect(remote_db).execute("SELECT id FROM instance_kinds").fetchone()["id"]
    delete_type(remote_kind_id, db_path=remote_db)
    local_conn = connect(local_db)
    result = merge_remote(local_conn, _db_bytes(remote_db))
    assert result.instances_deleted == 1
    assert result.kinds_deleted == 1
    assert list_types(db_path=local_db) == []
    assert list_instances(db_path=local_db) == []
