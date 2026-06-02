import os
from pathlib import Path

_DEFAULT_DB = Path.home() / ".cartographer" / "index.db"


def get_cartographer_db() -> Path:
    env = os.environ.get("CARTOGRAPHER_DB")
    return Path(env) if env else _DEFAULT_DB


def get_cartographer_bin() -> str:
    return os.environ.get("CARTOGRAPHER_BIN", "cartographer")


def get_scribe_backend() -> str:
    return os.environ.get("SCRIBE_BACKEND", "ollama")


def get_scribe_model() -> str:
    return os.environ.get("SCRIBE_MODEL", "llama3")


def get_scribe_top_k() -> int:
    try:
        return int(os.environ.get("SCRIBE_TOP_K", "10"))
    except ValueError:
        return 10


def get_ollama_url() -> str:
    return os.environ.get("SCRIBE_OLLAMA_URL", "http://localhost:11434")


def get_claude_bin() -> str:
    return os.environ.get("SCRIBE_CLAUDE_BIN", "claude")
