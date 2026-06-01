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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid            TEXT NOT NULL UNIQUE,
            node_id         INTEGER NOT NULL UNIQUE REFERENCES atlas_nodes(id),
            title           TEXT NOT NULL DEFAULT '',
            body            TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            date_annotation TEXT,
            instance_id     INTEGER REFERENCES instances(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS atlas_page_tags (
            page_id INTEGER NOT NULL REFERENCES atlas_pages(id) ON DELETE CASCADE,
            tag_id  INTEGER NOT NULL REFERENCES tags(id)        ON DELETE CASCADE,
            PRIMARY KEY (page_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS atlas_page_references (
            page_id      INTEGER NOT NULL REFERENCES atlas_pages(id)    ON DELETE CASCADE,
            reference_id INTEGER NOT NULL REFERENCES "references"(id)   ON DELETE CASCADE,
            PRIMARY KEY (page_id, reference_id)
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
            source_type TEXT NOT NULL CHECK (source_type IN ('note', 'atlas_page', 'instance_kind', 'instance')),
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
            source_type       TEXT NOT NULL CHECK (source_type IN ('note', 'atlas_page', 'instance_kind', 'instance')),
            source_updated_at TEXT NOT NULL,
            model             TEXT NOT NULL DEFAULT '',
            indexed_at        TEXT NOT NULL,
            PRIMARY KEY (source_uuid, source_type)
        );

        CREATE TABLE IF NOT EXISTS db_meta (
            id             INTEGER PRIMARY KEY CHECK (id = 1),
            schema_version TEXT NOT NULL,
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL
        );
    """)

    now = datetime.now(UTC).isoformat()

    if not conn.execute("SELECT 1 FROM db_meta").fetchone():
        conn.execute(
            "INSERT INTO db_meta (id, schema_version, created_at, updated_at) VALUES (1, ?, ?, ?)",
            (_APP_VERSION, now, now),
        )

    # Add updated_at to db_meta on existing DBs that predate this column.
    meta_cols = {row[1] for row in conn.execute("PRAGMA table_info(db_meta)")}
    if "updated_at" not in meta_cols:
        conn.execute("ALTER TABLE db_meta ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        conn.execute("UPDATE db_meta SET updated_at = created_at WHERE updated_at = ''")

    # Recreate embeddings + index_state when the CHECK constraint is too narrow
    # (predates instance_kind / instance source types) or the model column is missing.
    emb_sql = (
        conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='embeddings'"
        ).fetchone()
        or {"sql": ""}
    )["sql"] or ""
    if "instance_kind" not in emb_sql:
        conn.executescript("""
            ALTER TABLE embeddings  RENAME TO _emb_old;
            ALTER TABLE index_state RENAME TO _idx_old;

            CREATE TABLE embeddings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_uuid TEXT NOT NULL,
                source_type TEXT NOT NULL
                    CHECK (source_type IN ('note', 'atlas_page', 'instance_kind', 'instance')),
                chunk_index INTEGER NOT NULL DEFAULT 0,
                model       TEXT NOT NULL,
                vector      BLOB NOT NULL,
                indexed_at  TEXT NOT NULL,
                UNIQUE (source_uuid, source_type, chunk_index, model)
            );

            CREATE TABLE index_state (
                source_uuid       TEXT NOT NULL,
                source_type       TEXT NOT NULL
                    CHECK (source_type IN ('note', 'atlas_page', 'instance_kind', 'instance')),
                source_updated_at TEXT NOT NULL,
                model             TEXT NOT NULL DEFAULT '',
                indexed_at        TEXT NOT NULL,
                PRIMARY KEY (source_uuid, source_type)
            );

            INSERT INTO embeddings
                SELECT id, source_uuid, source_type, chunk_index, model, vector, indexed_at
                FROM _emb_old;

            INSERT INTO index_state
                SELECT source_uuid, source_type, source_updated_at,
                       COALESCE(model, ''), indexed_at
                FROM _idx_old;

            DROP TABLE _emb_old;
            DROP TABLE _idx_old;
        """)

    # Add date_annotation and instance_id to mirror atlas_pages if missing.
    ap_cols = {row[1] for row in conn.execute("PRAGMA table_info(atlas_pages)")}
    if "date_annotation" not in ap_cols:
        conn.execute("ALTER TABLE atlas_pages ADD COLUMN date_annotation TEXT")
    if "instance_id" not in ap_cols:
        conn.execute(
            "ALTER TABLE atlas_pages ADD COLUMN instance_id INTEGER REFERENCES instances(id) ON DELETE SET NULL"
        )

    # Drop the old sync_sources table (replaced by config keys in v0.2+).
    conn.execute("DROP TABLE IF EXISTS sync_sources")

    conn.execute("UPDATE db_meta SET schema_version = ?", (_APP_VERSION,))
    conn.commit()


def touch_updated_at(conn: sqlite3.Connection) -> None:
    """Stamp db_meta.updated_at with the current UTC time and commit."""
    conn.execute(
        "UPDATE db_meta SET updated_at = ?",
        (datetime.now(UTC).isoformat(),),
    )
    conn.commit()
