from note_taker.parser import normalise, parse


def test_extracts_tag() -> None:
    result = parse("planning the #sprint")
    assert result.tags == ["sprint"]
    assert result.references == []


def test_extracts_reference() -> None:
    result = parse("meeting with @alice")
    assert result.references == ["alice"]
    assert result.tags == []


def test_extracts_both() -> None:
    result = parse("discussed #roadmap with @alice and @bob")
    assert result.tags == ["roadmap"]
    assert result.references == ["alice", "bob"]


def test_deduplicates_tags() -> None:
    result = parse("#foo bar #foo")
    assert result.tags == ["foo"]


def test_deduplicates_references() -> None:
    result = parse("@alice called @alice back")
    assert result.references == ["alice"]


def test_normalises_to_lowercase() -> None:
    result = parse("#Meeting @Alice")
    assert result.tags == ["meeting"]
    assert result.references == ["alice"]


def test_preserves_order() -> None:
    result = parse("#beta #alpha #gamma")
    assert result.tags == ["beta", "alpha", "gamma"]


def test_no_tags_or_references() -> None:
    result = parse("just plain text")
    assert result.tags == []
    assert result.references == []


def test_empty_string() -> None:
    result = parse("")
    assert result.tags == []
    assert result.references == []


def test_todo_colon_adds_todo_tag() -> None:
    result = parse("Fix the thing TODO: update the docs")
    assert "todo" in result.tags


def test_todo_colon_case_insensitive() -> None:
    result = parse("todo: call @alice back")
    assert "todo" in result.tags


def test_todo_tag_not_duplicated_when_explicit() -> None:
    result = parse("#todo also TODO: do the thing")
    assert result.tags.count("todo") == 1


def test_todo_colon_not_matched_mid_word() -> None:
    result = parse("pseudocode: not a todo marker")
    assert "todo" not in result.tags


def test_todo_space_colon() -> None:
    result = parse("TODO : fix this")
    assert "todo" in result.tags


def test_todo_dash() -> None:
    result = parse("TODO- fix this")
    assert "todo" in result.tags


def test_todo_space_dash() -> None:
    result = parse("TODO - fix this")
    assert "todo" in result.tags


def test_normalise_todo_colon() -> None:
    assert normalise("TODO: fix this") == "#todo fix this"


def test_normalise_todo_space_colon() -> None:
    assert normalise("TODO : fix this") == "#todo fix this"


def test_normalise_todo_dash() -> None:
    assert normalise("TODO- fix this") == "#todo fix this"


def test_normalise_todo_space_dash() -> None:
    assert normalise("TODO - fix this") == "#todo fix this"


def test_normalise_todo_case_insensitive() -> None:
    assert normalise("todo: fix this") == "#todo fix this"


def test_normalise_todo_multiple() -> None:
    assert normalise("TODO: one\nTODO: two") == "#todo one\n#todo two"


def test_normalise_leaves_unrelated_text() -> None:
    assert normalise("just some text") == "just some text"
