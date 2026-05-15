import os
import sqlite3
from pathlib import Path
from uuid import uuid4

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
        CREATE TABLE IF NOT EXISTS deleted_notes (
            uuid       TEXT PRIMARY KEY,
            deleted_at TEXT NOT NULL
        );
    """)

    # Add uuid and updated_at to notes if this is an existing DB
    existing = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
    if "uuid" not in existing:
        conn.execute("ALTER TABLE notes ADD COLUMN uuid TEXT")
    if "updated_at" not in existing:
        conn.execute("ALTER TABLE notes ADD COLUMN updated_at TEXT")
    if "time_stamp" not in existing:
        conn.execute("ALTER TABLE notes ADD COLUMN time_stamp TEXT")

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_notes_uuid ON notes(uuid)"
    )

    # Backfill any rows that predate this migration
    for row in conn.execute("SELECT id FROM notes WHERE uuid IS NULL").fetchall():
        conn.execute("UPDATE notes SET uuid = ? WHERE id = ?", (str(uuid4()), row[0]))
    conn.execute("UPDATE notes SET updated_at = created_at WHERE updated_at IS NULL")
    conn.execute("UPDATE notes SET time_stamp = created_at WHERE time_stamp IS NULL")

    conn.commit()
