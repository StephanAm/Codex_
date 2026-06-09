# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

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
    get_default_tags,
    get_instance_property,
    list_instance_properties,
    list_notes,
    list_references,
    search_notes,
    set_default_tags,
    update_instance,
    update_instance_property,
    update_note,
    update_type,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


def test_add_returns_note_with_id(db: Path) -> None:
    note = add_note("hello world", db_path=db)
    assert note.id is not None
    assert note.body == "hello world"


def test_add_parses_tags_and_references(db: Path) -> None:
    note = add_note("@alice reviewed the #backend PR", db_path=db)
    assert note.tags == ["backend"]
    assert note.references == ["alice"]


def test_list_returns_most_recent_first(db: Path) -> None:
    add_note("first", db_path=db)
    add_note("second", db_path=db)
    notes = list_notes(db_path=db)
    assert notes[0].body == "second"
    assert notes[1].body == "first"


def test_list_filter_by_tag(db: Path) -> None:
    add_note("note one #important", db_path=db)
    add_note("note two #routine", db_path=db)
    results = list_notes(tag="important", db_path=db)
    assert len(results) == 1
    assert "important" in results[0].tags


def test_list_filter_by_reference(db: Path) -> None:
    add_note("met with @alice", db_path=db)
    add_note("called @bob", db_path=db)
    results = list_notes(reference="alice", db_path=db)
    assert len(results) == 1
    assert "alice" in results[0].references


def test_list_limit(db: Path) -> None:
    for i in range(5):
        add_note(f"note {i}", db_path=db)
    results = list_notes(limit=3, db_path=db)
    assert len(results) == 3


def test_search_by_body_text(db: Path) -> None:
    add_note("the quick brown fox", db_path=db)
    add_note("something unrelated", db_path=db)
    results = search_notes("quick", db_path=db)
    assert len(results) == 1
    assert "quick" in results[0].body


def test_search_no_match(db: Path) -> None:
    add_note("hello world", db_path=db)
    assert search_notes("zzznomatch", db_path=db) == []


def test_delete_existing_note(db: Path) -> None:
    note = add_note("to be deleted", db_path=db)
    assert delete_note(note.id, db_path=db) is True
    assert list_notes(db_path=db) == []


def test_delete_nonexistent_note(db: Path) -> None:
    assert delete_note(9999, db_path=db) is False


def test_references_accumulated_across_notes(db: Path) -> None:
    add_note("@alice and @bob #meeting", db_path=db)
    add_note("@alice again", db_path=db)
    refs = list_references(db_path=db)
    names = [r.name for r in refs]
    assert "alice" in names
    assert "bob" in names
    # alice appears twice in notes but only once in references
    assert names.count("alice") == 1


def test_update_note_body(db: Path) -> None:
    note = add_note("original text #old", db_path=db)
    updated = update_note(note.id, "revised text #new @alice", db_path=db)
    assert updated is not None
    assert updated.body == "revised text #new @alice"
    assert updated.tags == ["new"]
    assert updated.references == ["alice"]


def test_update_note_replaces_tags(db: Path) -> None:
    note = add_note("note #alpha #beta", db_path=db)
    updated = update_note(note.id, "note #gamma", db_path=db)
    assert updated is not None
    assert updated.tags == ["gamma"]
    assert "alpha" not in updated.tags
    assert "beta" not in updated.tags


def test_update_note_nonexistent(db: Path) -> None:
    assert update_note(9999, "anything", db_path=db) is None


def test_default_tags_empty_by_default(db: Path) -> None:
    assert get_default_tags(db_path=db) == []


def test_set_and_get_default_tags(db: Path) -> None:
    set_default_tags(["work", "daily"], db_path=db)
    assert get_default_tags(db_path=db) == ["work", "daily"]


def test_set_default_tags_overwrites(db: Path) -> None:
    set_default_tags(["alpha"], db_path=db)
    set_default_tags(["beta", "gamma"], db_path=db)
    assert get_default_tags(db_path=db) == ["beta", "gamma"]


def test_set_default_tags_lowercases(db: Path) -> None:
    set_default_tags(["Work", "DAILY"], db_path=db)
    assert get_default_tags(db_path=db) == ["work", "daily"]


# ---------------------------------------------------------------------------
# Kind (InstanceKind) sync field tests
# ---------------------------------------------------------------------------


def test_create_type_generates_uuid(db: Path) -> None:
    k = create_type("People", db_path=db)
    assert len(k.uuid) == 36


def test_create_type_sets_timestamps(db: Path) -> None:
    k = create_type("People", db_path=db)
    assert k.created_at != ""
    assert k.updated_at != ""
    assert k.created_at == k.updated_at


def test_update_type_advances_updated_at(db: Path) -> None:
    k = create_type("People", db_path=db)
    time.sleep(0.01)
    k2 = update_type(k.id, "Persons", "", "", db_path=db)
    assert k2 is not None
    assert k2.updated_at > k2.created_at


def test_delete_type_writes_tombstone(db: Path) -> None:
    k = create_type("Ghost", db_path=db)
    delete_type(k.id, db_path=db)
    row = connect(db).execute("SELECT * FROM deleted_instance_kinds WHERE uuid = ?", (k.uuid,)).fetchone()
    assert row is not None


def test_delete_nonexistent_type_returns_false(db: Path) -> None:
    assert delete_type(9999, db_path=db) is False


# ---------------------------------------------------------------------------
# Instance sync field tests
# ---------------------------------------------------------------------------


def test_create_instance_generates_uuid(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    assert len(inst.uuid) == 36


def test_create_instance_sets_timestamps(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    assert inst.created_at != ""
    assert inst.updated_at != ""
    assert inst.created_at == inst.updated_at


def test_update_instance_advances_updated_at(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    time.sleep(0.01)
    inst2 = update_instance(inst.id, "Alicia", "", k.id, db_path=db)
    assert inst2 is not None
    assert inst2.updated_at > inst2.created_at


def test_delete_instance_writes_tombstone(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    delete_instance(inst.id, db_path=db)
    row = connect(db).execute("SELECT * FROM deleted_instances WHERE uuid = ?", (inst.uuid,)).fetchone()
    assert row is not None


def test_create_instance_auto_references(db: Path) -> None:
    k = create_type("Person", db_path=db)
    inst = create_instance("John Smith", k.id, db_path=db)
    assert "johnsmith" in inst.references


def test_create_instance_auto_references_merged_with_explicit(db: Path) -> None:
    k = create_type("Team", db_path=db)
    inst = create_instance("Red Team", k.id, references=["custom"], db_path=db)
    assert "redteam" in inst.references
    assert "custom" in inst.references


def test_delete_nonexistent_instance_returns_false(db: Path) -> None:
    assert delete_instance(9999, db_path=db) is False


def test_set_default_tags_clear(db: Path) -> None:
    set_default_tags(["work"], db_path=db)
    set_default_tags([], db_path=db)
    assert get_default_tags(db_path=db) == []


# ---------------------------------------------------------------------------
# Instance properties
# ---------------------------------------------------------------------------


def test_create_instance_property(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    prop = create_instance_property(inst.id, "role", "CEO", db_path=db)
    assert prop.id > 0
    assert prop.uuid != ""
    assert prop.instance_id == inst.id
    assert prop.name == "role"
    assert prop.value == "CEO"
    assert prop.created_at != ""
    assert prop.created_at == prop.updated_at


def test_get_instance_property(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    prop = create_instance_property(inst.id, "role", "CEO", db_path=db)
    fetched = get_instance_property(prop.id, db_path=db)
    assert fetched is not None
    assert fetched.id == prop.id
    assert fetched.name == "role"


def test_get_instance_property_missing_returns_none(db: Path) -> None:
    assert get_instance_property(9999, db_path=db) is None


def test_list_instance_properties(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    other = create_instance("Bob", k.id, db_path=db)
    create_instance_property(inst.id, "role", "CEO", db_path=db)
    create_instance_property(inst.id, "birth_date", "1980-01-01", db_path=db)
    create_instance_property(other.id, "role", "CTO", db_path=db)
    props = list_instance_properties(inst.id, db_path=db)
    assert len(props) == 2
    assert all(p.instance_id == inst.id for p in props)
    assert [p.name for p in props] == ["birth_date", "role"]  # ordered by name


def test_update_instance_property(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    prop = create_instance_property(inst.id, "role", "CEO", db_path=db)
    time.sleep(0.01)
    updated = update_instance_property(prop.id, "role", "COO", db_path=db)
    assert updated is not None
    assert updated.value == "COO"
    assert updated.updated_at > prop.updated_at


def test_update_instance_property_missing_returns_none(db: Path) -> None:
    assert update_instance_property(9999, "x", "y", db_path=db) is None


def test_delete_instance_property_writes_tombstone(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    prop = create_instance_property(inst.id, "role", "CEO", db_path=db)
    result = delete_instance_property(prop.id, db_path=db)
    assert result is True
    assert get_instance_property(prop.id, db_path=db) is None
    row = connect(db).execute("SELECT * FROM deleted_instance_properties WHERE uuid = ?", (prop.uuid,)).fetchone()
    assert row is not None


def test_delete_instance_property_missing_returns_false(db: Path) -> None:
    assert delete_instance_property(9999, db_path=db) is False


def test_delete_instance_cascades_to_properties(db: Path) -> None:
    k = create_type("People", db_path=db)
    inst = create_instance("Alice", k.id, db_path=db)
    create_instance_property(inst.id, "role", "CEO", db_path=db)
    delete_instance(inst.id, db_path=db)
    props = list_instance_properties(inst.id, db_path=db)
    assert props == []
