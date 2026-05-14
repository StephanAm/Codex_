import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

_ICONS: dict[int, str] = {
    logging.DEBUG: "🐛",
    logging.INFO: "ℹ️ ",
    logging.WARNING: "⚠️ ",
    logging.ERROR: "❌",
    logging.CRITICAL: "🔥",
}

_COLORS = [
    "\033[31m",  # red
    "\033[32m",  # green
    "\033[33m",  # yellow
    "\033[34m",  # blue
    "\033[35m",  # magenta
    "\033[36m",  # cyan
    "\033[91m",  # bright red
    "\033[92m",  # bright green
    "\033[93m",  # bright yellow
    "\033[94m",  # bright blue
    "\033[95m",  # bright magenta
    "\033[96m",  # bright cyan
]
_RESET = "\033[0m"

_LOG_FILE = Path("app.log")
_file_handler: logging.FileHandler | None = None
_registry: dict[str, logging.Logger] = {}


def _color_for(name: str) -> str:
    return _COLORS[hash(name) % len(_COLORS)]


class _ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        icon = _ICONS.get(record.levelno, "•")
        colored_name = f"{_color_for(record.name)}{record.name}{_RESET}"
        return f"{icon} {colored_name} {record.getMessage()}"


class _FileFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        return f"{ts} {record.levelname} {record.name} {record.getMessage()}"


def _get_file_handler() -> logging.FileHandler:
    global _file_handler
    if _file_handler is None:
        _file_handler = logging.FileHandler(_LOG_FILE)
        _file_handler.setFormatter(_FileFormatter())
        _file_handler.setLevel(logging.DEBUG)
    return _file_handler


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, creating and registering it on first call."""
    if name in _registry:
        return _registry[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(_ConsoleFormatter())
    console.setLevel(logging.DEBUG)
    logger.addHandler(console)
    logger.addHandler(_get_file_handler())

    _registry[name] = logger
    return logger
