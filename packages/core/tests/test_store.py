from pathlib import Path

import pytest

from note_taker.store import (
    add_note,
    delete_note,
    list_entities,
    list_notes,
    search_notes,
    set_entity_type,
    update_note,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


def test_add_returns_note_with_id(db: Path) -> None:
    note = add_note("hello world", db_path=db)
    assert note.id is not None
    assert note.body == "hello world"


def test_add_parses_tags_and_entities(db: Path) -> None:
    note = add_note("@alice reviewed the #backend PR", db_path=db)
    assert note.tags == ["backend"]
    assert note.entities == ["alice"]


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


def test_list_filter_by_entity(db: Path) -> None:
    add_note("met with @alice", db_path=db)
    add_note("called @bob", db_path=db)
    results = list_notes(entity="alice", db_path=db)
    assert len(results) == 1
    assert "alice" in results[0].entities


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


def test_entities_accumulated_across_notes(db: Path) -> None:
    add_note("@alice and @bob #meeting", db_path=db)
    add_note("@alice again", db_path=db)
    entities = list_entities(db_path=db)
    names = [e.name for e in entities]
    assert "alice" in names
    assert "bob" in names
    # alice appears twice in notes but only once in entities
    assert names.count("alice") == 1


def test_set_entity_type(db: Path) -> None:
    add_note("@alice", db_path=db)
    assert set_entity_type("alice", "person", db_path=db) is True
    entities = list_entities(db_path=db)
    alice = next(e for e in entities if e.name == "alice")
    assert alice.entity_type == "person"


def test_set_entity_type_unknown_entity(db: Path) -> None:
    assert set_entity_type("nobody", "person", db_path=db) is False


def test_update_note_body(db: Path) -> None:
    note = add_note("original text #old", db_path=db)
    updated = update_note(note.id, "revised text #new @alice", db_path=db)
    assert updated is not None
    assert updated.body == "revised text #new @alice"
    assert updated.tags == ["new"]
    assert updated.entities == ["alice"]


def test_update_note_replaces_tags(db: Path) -> None:
    note = add_note("note #alpha #beta", db_path=db)
    updated = update_note(note.id, "note #gamma", db_path=db)
    assert updated is not None
    assert updated.tags == ["gamma"]
    assert "alpha" not in updated.tags
    assert "beta" not in updated.tags


def test_update_note_nonexistent(db: Path) -> None:
    assert update_note(9999, "anything", db_path=db) is None
