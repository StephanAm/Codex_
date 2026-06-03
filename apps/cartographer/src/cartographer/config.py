"""
Configuration accessors for Cartographer's source settings.

All values are stored in the `config` table as key-value pairs.
"""

from pathlib import Path

from cartographer.db import connect

_VALID_SOURCE_TYPES = ("google_drive", "local_folder", "mnemo_local")

_CODEX_DIR = Path.home() / ".codex_"
_DEFAULT_SOURCE_TYPE = "google_drive"
_DEFAULT_DRIVE_FOLDER = "note-taker-sync"
_DEFAULT_MNEMO_DB = str(Path.home() / ".codex_" / "mnemo_" / "notes.db")
_DEFAULT_EMBEDDING_BACKEND = "fastembed"
_DEFAULT_OLLAMA_URL = "http://localhost:11434"


def _get(key: str, default: str, db_path: Path | None = None) -> str:
    conn = connect(db_path)
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else default


def _set(key: str, value: str, db_path: Path | None = None) -> None:
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Source type
# ---------------------------------------------------------------------------


def get_source_type(db_path: Path | None = None) -> str:
    return _get("source_type", _DEFAULT_SOURCE_TYPE, db_path)


def set_source_type(source_type: str, db_path: Path | None = None) -> None:
    if source_type not in _VALID_SOURCE_TYPES:
        raise ValueError(f"Unknown source type {source_type!r}. Choose one of: {', '.join(_VALID_SOURCE_TYPES)}")
    _set("source_type", source_type, db_path)


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------


def get_drive_folder(db_path: Path | None = None) -> str:
    return _get("google_drive_folder", _DEFAULT_DRIVE_FOLDER, db_path)


def set_drive_folder(name: str, db_path: Path | None = None) -> None:
    _set("google_drive_folder", name.strip(), db_path)


def get_drive_credentials_path(db_path: Path | None = None) -> Path:
    raw = _get("google_drive_credentials_path", str(_CODEX_DIR / "credentials.json"), db_path)
    return Path(raw)


def set_drive_credentials_path(path: Path, db_path: Path | None = None) -> None:
    _set("google_drive_credentials_path", str(path), db_path)


def get_drive_token_path(db_path: Path | None = None) -> Path:
    raw = _get("google_drive_token_path", str(_CODEX_DIR / "token.json"), db_path)
    return Path(raw)


def set_drive_token_path(path: Path, db_path: Path | None = None) -> None:
    _set("google_drive_token_path", str(path), db_path)


# ---------------------------------------------------------------------------
# Local folder
# ---------------------------------------------------------------------------


def get_local_folder_path(db_path: Path | None = None) -> str:
    return _get("local_folder_path", "", db_path)


def set_local_folder_path(path: str, db_path: Path | None = None) -> None:
    _set("local_folder_path", path.strip(), db_path)


# ---------------------------------------------------------------------------
# Mnemo local DB
# ---------------------------------------------------------------------------


def get_mnemo_db_path(db_path: Path | None = None) -> str:
    return _get("mnemo_db_path", _DEFAULT_MNEMO_DB, db_path)


def set_mnemo_db_path(path: str, db_path: Path | None = None) -> None:
    _set("mnemo_db_path", path.strip(), db_path)


# ---------------------------------------------------------------------------
# Remote DB name (the fixed filename used in the remote adapter location)
# ---------------------------------------------------------------------------


def get_remote_name(db_path: Path | None = None) -> str:
    return _get("remote_name", "cartographer", db_path)


def set_remote_name(name: str, db_path: Path | None = None) -> None:
    _set("remote_name", name.strip(), db_path)


# ---------------------------------------------------------------------------
# Embedding backend
# ---------------------------------------------------------------------------


def get_embedding_backend(db_path: Path | None = None) -> str:
    return _get("embedding_backend", _DEFAULT_EMBEDDING_BACKEND, db_path)


def set_embedding_backend(backend: str, db_path: Path | None = None) -> None:
    from cartographer.embeddings import VALID_BACKENDS

    if backend not in VALID_BACKENDS:
        raise ValueError(f"Unknown backend {backend!r}. Choose one of: {', '.join(VALID_BACKENDS)}")
    _set("embedding_backend", backend, db_path)


def get_embedding_model(db_path: Path | None = None) -> str:
    return _get("embedding_model", "", db_path)


def set_embedding_model(model: str, db_path: Path | None = None) -> None:
    _set("embedding_model", model.strip(), db_path)


def get_ollama_url(db_path: Path | None = None) -> str:
    return _get("ollama_url", _DEFAULT_OLLAMA_URL, db_path)


def set_ollama_url(url: str, db_path: Path | None = None) -> None:
    _set("ollama_url", url.strip(), db_path)
