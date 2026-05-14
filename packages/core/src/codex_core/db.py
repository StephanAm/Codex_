import os
import sqlite3
from pathlib import Path

_DEFAULT_DB = Path.home() / ".note_taker" / "notes.db"


def get_db_path() -> Path:
    env = os.environ.get("NOTE_TAKER_DB")
    return Path(env) if env else _DEFAULT_DB


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            entity_type TEXT
        );
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS note_entities (
            note_id   INTEGER NOT NULL REFERENCES notes(id)    ON DELETE CASCADE,
            entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            PRIMARY KEY (note_id, entity_id)
        );
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()
