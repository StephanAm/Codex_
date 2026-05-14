from note_taker.parser import parse


def test_extracts_tag() -> None:
    result = parse("planning the #sprint")
    assert result.tags == ["sprint"]
    assert result.entities == []


def test_extracts_entity() -> None:
    result = parse("meeting with @alice")
    assert result.entities == ["alice"]
    assert result.tags == []


def test_extracts_both() -> None:
    result = parse("discussed #roadmap with @alice and @bob")
    assert result.tags == ["roadmap"]
    assert result.entities == ["alice", "bob"]


def test_deduplicates_tags() -> None:
    result = parse("#foo bar #foo")
    assert result.tags == ["foo"]


def test_deduplicates_entities() -> None:
    result = parse("@alice called @alice back")
    assert result.entities == ["alice"]


def test_normalises_to_lowercase() -> None:
    result = parse("#Meeting @Alice")
    assert result.tags == ["meeting"]
    assert result.entities == ["alice"]


def test_preserves_order() -> None:
    result = parse("#beta #alpha #gamma")
    assert result.tags == ["beta", "alpha", "gamma"]


def test_no_tags_or_entities() -> None:
    result = parse("just plain text")
    assert result.tags == []
    assert result.entities == []


def test_empty_string() -> None:
    result = parse("")
    assert result.tags == []
    assert result.entities == []
