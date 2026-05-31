import os
import sqlite3
from datetime import UTC, datetime
from importlib.metadata import version as _pkg_version
from pathlib import Path

try:
    _APP_VERSION = _pkg_version("cartographer")
except Exception:
    _APP_VERSION = "unknown"

_DEFAULT_DB = Path.home() / ".cartographer" / "index.db"


def get_db_path() -> Path:
    env = os.environ.get("CARTOGRAPHER_DB")
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
    # -------------------------------------------------------------------------
    # Mirror tables — exact schema from codex_core so the merge logic can run
    # unchanged against both the local mirror and any source Mnemo DB.
    # -------------------------------------------------------------------------
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid       TEXT NOT NULL UNIQUE,
            body       TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            time_stamp TEXT
        );
        CREATE TABLE IF NOT EXISTS tags (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS "references" (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS note_references (
            note_id      INTEGER NOT NULL REFERENCES notes(id)        ON DELETE CASCADE,
            reference_id INTEGER NOT NULL REFERENCES "references"(id) ON DELETE CASCADE,
            PRIMARY KEY (note_id, reference_id)
        );
        CREATE TABLE IF NOT EXISTS deleted_notes (
            uuid       TEXT PRIMARY KEY,
            deleted_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS instance_kinds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid        TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL UNIQUE,
            plural      TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            created_at  TEXT,
            updated_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS instances (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid             TEXT NOT NULL UNIQUE,
            name             TEXT NOT NULL,
            description      TEXT NOT NULL DEFAULT '',
            instance_kind_id INTEGER NOT NULL REFERENCES instance_kinds(id) ON DELETE RESTRICT,
            created_at       TEXT,
            updated_at       TEXT
        );
        CREATE TABLE IF NOT EXISTS instance_references (
            instance_id  INTEGER NOT NULL REFERENCES instances(id)    ON DELETE CASCADE,
            reference_id INTEGER NOT NULL REFERENCES "references"(id) ON DELETE CASCADE,
            PRIMARY KEY (instance_id, reference_id)
        );
        CREATE TABLE IF NOT EXISTS deleted_instance_kinds (
            uuid       TEXT PRIMARY KEY,
            deleted_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deleted_instances (
            uuid       TEXT PRIMARY KEY,
            deleted_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS atlas_nodes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid       TEXT NOT NULL UNIQUE,
            name       TEXT NOT NULL DEFAULT '',
            parent_id  INTEGER REFERENCES atlas_nodes(id) ON DELETE SET NULL,
            position   INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS atlas_pages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid       TEXT NOT NULL UNIQUE,
            node_id    INTEGER NOT NULL UNIQUE REFERENCES atlas_nodes(id),
            title      TEXT NOT NULL DEFAULT '',
            body       TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deleted_atlas_nodes (
            uuid       TEXT PRIMARY KEY,
            deleted_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deleted_atlas_pages (
            uuid       TEXT PRIMARY KEY,
            deleted_at TEXT NOT NULL
        );

        -- -----------------------------------------------------------------------
        -- Cartographer configuration (source type, adapter settings, etc.)
        -- -----------------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        -- -----------------------------------------------------------------------
        -- Vector indexing
        -- -----------------------------------------------------------------------

        -- One row per indexed chunk; vector stored as a raw float-array blob.
        CREATE TABLE IF NOT EXISTS embeddings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source_uuid TEXT NOT NULL,
            source_type TEXT NOT NULL CHECK (source_type IN ('note', 'atlas_page')),
            chunk_index INTEGER NOT NULL DEFAULT 0,
            model       TEXT NOT NULL,
            vector      BLOB NOT NULL,
            indexed_at  TEXT NOT NULL,
            UNIQUE (source_uuid, source_type, chunk_index, model)
        );

        -- Tracks source_updated_at seen at index time so stale entries can be
        -- detected without re-reading the source DB.
        CREATE TABLE IF NOT EXISTS index_state (
            source_uuid       TEXT NOT NULL,
            source_type       TEXT NOT NULL CHECK (source_type IN ('note', 'atlas_page')),
            source_updated_at TEXT NOT NULL,
            indexed_at        TEXT NOT NULL,
            PRIMARY KEY (source_uuid, source_type)
        );

        CREATE TABLE IF NOT EXISTS db_meta (
            id             INTEGER PRIMARY KEY CHECK (id = 1),
            schema_version TEXT NOT NULL,
            created_at     TEXT NOT NULL
        );
    """)

    if not conn.execute("SELECT 1 FROM db_meta").fetchone():
        conn.execute(
            "INSERT INTO db_meta (id, schema_version, created_at) VALUES (1, ?, ?)",
            (_APP_VERSION, datetime.now(UTC).isoformat()),
        )

    # Drop the old sync_sources table (replaced by config keys in v0.2+).
    conn.execute("DROP TABLE IF EXISTS sync_sources")

    conn.execute("UPDATE db_meta SET schema_version = ?", (_APP_VERSION,))
    conn.commit()
