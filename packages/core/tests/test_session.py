from pathlib import Path
from unittest.mock import patch

import pytest

from note_taker.session import clear_session_context, get_session_context, set_session_context


@pytest.fixture(autouse=True)
def isolated_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session_file = tmp_path / "session.json"
    monkeypatch.setattr("note_taker.session._session_path", lambda: session_file)


def test_get_returns_empty_when_no_file() -> None:
    tags, references = get_session_context()
    assert tags == []
    assert references == []


def test_set_and_get_roundtrip() -> None:
    set_session_context(["oneonone", "meeting"], ["bronwyn"])
    tags, references = get_session_context()
    assert tags == ["oneonone", "meeting"]
    assert references == ["bronwyn"]


def test_clear_removes_context() -> None:
    set_session_context(["oneonone"], ["bronwyn"])
    clear_session_context()
    tags, references = get_session_context()
    assert tags == []
    assert references == []


def test_clear_is_idempotent_when_no_file() -> None:
    clear_session_context()  # should not raise
    tags, references = get_session_context()
    assert tags == []
    assert references == []


def test_set_overwrites_previous_context() -> None:
    set_session_context(["alpha"], ["alice"])
    set_session_context(["beta"], ["bob"])
    tags, references = get_session_context()
    assert tags == ["beta"]
    assert references == ["bob"]
