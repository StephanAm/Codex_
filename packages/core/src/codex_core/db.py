import os
import sqlite3
from datetime import datetime, timezone
from importlib.metadata import version as _pkg_version
from pathlib import Path
from uuid import uuid4

try:
    _APP_VERSION = _pkg_version("note-taker")
except Exception:
    _APP_VERSION = "unknown"

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
        CREATE TABLE IF NOT EXISTS "references" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS note_references (
            note_id      INTEGER NOT NULL REFERENCES notes(id)         ON DELETE CASCADE,
            reference_id INTEGER NOT NULL REFERENCES "references"(id)  ON DELETE CASCADE,
            PRIMARY KEY (note_id, reference_id)
        );
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deleted_notes (
            uuid       TEXT PRIMARY KEY,
            deleted_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS db_meta (
            id             INTEGER PRIMARY KEY CHECK (id = 1),
            schema_version TEXT NOT NULL,
            created_at     TEXT NOT NULL
        );
    """)

    # Seed db_meta on first creation
    if not conn.execute("SELECT 1 FROM db_meta").fetchone():
        conn.execute(
            "INSERT INTO db_meta (id, schema_version, created_at) VALUES (1, ?, ?)",
            (_APP_VERSION, datetime.now(timezone.utc).isoformat()),
        )

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

    # Migrate entities → references (existing DBs only; keyed on note_entities, not entities,
    # so the new entities table added later doesn't re-trigger this block)
    has_entities = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='note_entities'"
    ).fetchone()
    if has_entities:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS "references" (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            INSERT OR IGNORE INTO "references" (id, name)
                SELECT id, name FROM entities;
            CREATE TABLE IF NOT EXISTS note_references (
                note_id      INTEGER NOT NULL REFERENCES notes(id)         ON DELETE CASCADE,
                reference_id INTEGER NOT NULL REFERENCES "references"(id)  ON DELETE CASCADE,
                PRIMARY KEY (note_id, reference_id)
            );
            INSERT OR IGNORE INTO note_references (note_id, reference_id)
                SELECT note_id, entity_id FROM note_entities;
            DROP TABLE IF EXISTS note_entities;
            DROP TABLE IF EXISTS entities;
        """)

    # Rename entity_types → instance_kinds and entities → instances on existing DBs
    has_entity_types = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='entity_types'"
    ).fetchone()
    if has_entity_types:
        conn.executescript("""
            ALTER TABLE entity_types RENAME TO instance_kinds;
            ALTER TABLE entities RENAME TO instances;
        """)

    # Rename types → instance_kinds on existing DBs
    has_types = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='types'"
    ).fetchone()
    if has_types:
        conn.executescript("ALTER TABLE types RENAME TO instance_kinds;")

    # Rename type_id → instance_kind_id on existing DBs
    instances_cols = {row[1] for row in conn.execute("PRAGMA table_info(instances)")}
    if "type_id" in instances_cols:
        conn.executescript(
            "ALTER TABLE instances RENAME COLUMN type_id TO instance_kind_id;"
        )

    # Add plural column to instance_kinds if missing (existing DBs)
    ik_cols = {row[1] for row in conn.execute("PRAGMA table_info(instance_kinds)")}
    if ik_cols and "plural" not in ik_cols:
        conn.execute("ALTER TABLE instance_kinds ADD COLUMN plural TEXT NOT NULL DEFAULT ''")

    # Instance kinds and instances tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS instance_kinds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            plural      TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS instances (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            description     TEXT NOT NULL DEFAULT '',
            instance_kind_id INTEGER NOT NULL REFERENCES instance_kinds(id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS instance_references (
            instance_id  INTEGER NOT NULL REFERENCES instances(id)    ON DELETE CASCADE,
            reference_id INTEGER NOT NULL REFERENCES "references"(id) ON DELETE CASCADE,
            PRIMARY KEY (instance_id, reference_id)
        );
    """)

    # Always stamp the current app version so the DB reflects the last migration
    conn.execute("UPDATE db_meta SET schema_version = ?", (_APP_VERSION,))

    conn.commit()
