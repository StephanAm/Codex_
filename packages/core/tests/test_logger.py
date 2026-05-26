import logging

import pytest

from codex_core.logger import _color_for, _ConsoleFormatter, _FileFormatter, get_logger


def test_get_logger_returns_logger() -> None:
    logger = get_logger("test.basic")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.basic"


def test_get_logger_singleton() -> None:
    a = get_logger("test.singleton")
    b = get_logger("test.singleton")
    assert a is b


def test_get_logger_different_names_are_distinct() -> None:
    a = get_logger("test.module_a")
    b = get_logger("test.module_b")
    assert a is not b


def test_get_logger_has_two_handlers() -> None:
    logger = get_logger("test.handlers")
    assert len(logger.handlers) == 2


def test_color_for_same_name_is_stable() -> None:
    assert _color_for("myapp") == _color_for("myapp")


def test_color_for_different_names_can_differ() -> None:
    colors = {_color_for(f"module_{i}") for i in range(20)}
    assert len(colors) > 1


def test_console_formatter_contains_message() -> None:
    formatter = _ConsoleFormatter()
    record = logging.LogRecord(
        name="myapp",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    assert "hello world" in output
    assert "myapp" in output


def test_file_formatter_is_iso8601() -> None:
    formatter = _FileFormatter()
    record = logging.LogRecord(
        name="myapp",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="something happened",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    # ISO 8601 UTC timestamps contain 'T' and '+00:00'
    assert "T" in output
    assert "+00:00" in output
    assert "WARNING" in output
    assert "something happened" in output


@pytest.mark.parametrize(
    "level,expected_icon",
    [
        (logging.DEBUG, "🐛"),
        (logging.WARNING, "⚠️"),
        (logging.ERROR, "❌"),
        (logging.CRITICAL, "🔥"),
    ],
)
def test_console_formatter_icons(level: int, expected_icon: str) -> None:
    formatter = _ConsoleFormatter()
    record = logging.LogRecord(
        name="x",
        level=level,
        pathname="",
        lineno=0,
        msg="msg",
        args=(),
        exc_info=None,
    )
    assert expected_icon in formatter.format(record)
