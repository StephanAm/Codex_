"""
Configuration accessors for Cartographer's source settings.

All values are stored in the `config` table as key-value pairs.
"""

from pathlib import Path

from cartographer.db import connect, get_db_path as _get_db_path

_VALID_SOURCE_TYPES = ("google_drive", "local_folder", "mnemo_local")

_CONFIG_DIR = Path.home() / ".cartographer"
_DEFAULT_SOURCE_TYPE = "google_drive"
_DEFAULT_DRIVE_FOLDER = "note-taker-sync"
_DEFAULT_MNEMO_DB = str(Path.home() / ".note_taker" / "notes.db")


def _get(key: str, default: str, db_path: Path | None = None) -> str:
    conn = connect(db_path)
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else default


def _set(key: str, value: str, db_path: Path | None = None) -> None:
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO config (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
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
        raise ValueError(
            f"Unknown source type {source_type!r}. "
            f"Choose one of: {', '.join(_VALID_SOURCE_TYPES)}"
        )
    _set("source_type", source_type, db_path)


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------

def get_drive_folder(db_path: Path | None = None) -> str:
    return _get("google_drive_folder", _DEFAULT_DRIVE_FOLDER, db_path)


def set_drive_folder(name: str, db_path: Path | None = None) -> None:
    _set("google_drive_folder", name.strip(), db_path)


def get_drive_credentials_path(db_path: Path | None = None) -> Path:
    raw = _get("google_drive_credentials_path", str(_CONFIG_DIR / "credentials.json"), db_path)
    return Path(raw)


def set_drive_credentials_path(path: Path, db_path: Path | None = None) -> None:
    _set("google_drive_credentials_path", str(path), db_path)


def get_drive_token_path(db_path: Path | None = None) -> Path:
    raw = _get("google_drive_token_path", str(_CONFIG_DIR / "token.json"), db_path)
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
