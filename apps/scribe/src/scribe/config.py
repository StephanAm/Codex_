"""
Scribe configuration.

Resolution order (highest to lowest priority):
  1. Environment variable
  2. ~/.codex_/scribe/config.toml
  3. Built-in default
"""

from __future__ import annotations

import os
from pathlib import Path

import tomllib

SCRIBE_DIR = Path.home() / ".codex_" / "scribe"
CONFIG_FILE = SCRIBE_DIR / "config.toml"

_DEFAULT_CONFIG = """\
[cartographer]
db  = "{cartographer_db}"
bin = "cartographer"

[llm]
backend    = "claude"
model      = ""
ollama_url = "http://localhost:11434"
claude_bin = "claude"

[retrieval]
top_k = 10
"""

_cache: dict[str, object] | None = None


def _load() -> dict[str, object]:
    global _cache
    if _cache is None:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "rb") as f:
                _cache = tomllib.load(f)
        else:
            _cache = {}
    return _cache


def _str(section: str, key: str, env_var: str, default: str) -> str:
    env = os.environ.get(env_var)
    if env:
        return env
    cfg = _load()
    val = cfg.get(section, {})
    assert isinstance(val, dict)
    return str(val.get(key, default))


def _int(section: str, key: str, env_var: str, default: int) -> int:
    env = os.environ.get(env_var)
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    cfg = _load()
    val = cfg.get(section, {})
    assert isinstance(val, dict)
    try:
        return int(val.get(key, default))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------


def get_cartographer_db() -> Path:
    raw = _str("cartographer", "db", "CARTOGRAPHER_DB", str(Path.home() / ".codex_" / "cartographer" / "index.db"))
    return Path(raw).expanduser()


def get_cartographer_bin() -> str:
    return _str("cartographer", "bin", "CARTOGRAPHER_BIN", "cartographer")


def get_scribe_backend() -> str:
    return _str("llm", "backend", "SCRIBE_BACKEND", "claude")


def get_scribe_model() -> str:
    return _str("llm", "model", "SCRIBE_MODEL", "")


def get_ollama_url() -> str:
    return _str("llm", "ollama_url", "SCRIBE_OLLAMA_URL", "http://localhost:11434")


def get_claude_bin() -> str:
    return _str("llm", "claude_bin", "SCRIBE_CLAUDE_BIN", "claude")


def get_scribe_top_k() -> int:
    return _int("retrieval", "top_k", "SCRIBE_TOP_K", 10)


# ---------------------------------------------------------------------------
# Config file helpers
# ---------------------------------------------------------------------------


def write_default_config() -> None:
    """Write a default config.toml to SCRIBE_DIR. Raises FileExistsError if already present."""
    SCRIBE_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        raise FileExistsError(CONFIG_FILE)
    cartographer_db = str(Path.home() / ".codex_" / "cartographer" / "index.db")
    CONFIG_FILE.write_text(
        _DEFAULT_CONFIG.format(cartographer_db=cartographer_db),
        encoding="utf-8",
    )


def resolved_config() -> dict[str, object]:
    """Return the fully resolved config as a plain dict (for display)."""
    return {
        "cartographer": {
            "db": str(get_cartographer_db()),
            "bin": get_cartographer_bin(),
        },
        "llm": {
            "backend": get_scribe_backend(),
            "model": get_scribe_model(),
            "ollama_url": get_ollama_url(),
            "claude_bin": get_claude_bin(),
        },
        "retrieval": {
            "top_k": get_scribe_top_k(),
        },
    }
