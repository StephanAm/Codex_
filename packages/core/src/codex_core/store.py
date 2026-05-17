import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .db import connect
from .models import Entity, Note
from .parser import parse


def _load_note(conn: sqlite3.Connection, row: sqlite3.Row) -> Note:
    note_id = row["id"]
    tags = [
        r["name"]
        for r in conn.execute(
            "SELECT t.name FROM tags t"
            " JOIN note_tags nt ON nt.tag_id = t.id"
            " WHERE nt.note_id = ?",
            (note_id,),
        )
    ]
    entities = [
        r["name"]
        for r in conn.execute(
            "SELECT e.name FROM entities e"
            " JOIN note_entities ne ON ne.entity_id = e.id"
            " WHERE ne.note_id = ?",
            (note_id,),
        )
    ]
    return Note(
        id=note_id,
        uuid=row["uuid"],
        body=row["body"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        time_stamp=datetime.fromisoformat(row["time_stamp"]),
        tags=tags,
        entities=entities,
    )


def _attach_tags_entities(
    conn: sqlite3.Connection,
    note_id: int | None,
    tags: list[str],
    entities: list[str],
) -> None:
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        tag_id = conn.execute(
            "SELECT id FROM tags WHERE name = ?", (tag,)
        ).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
            (note_id, tag_id),
        )
    for entity in entities:
        conn.execute("INSERT OR IGNORE INTO entities (name) VALUES (?)", (entity,))
        entity_id = conn.execute(
            "SELECT id FROM entities WHERE name = ?", (entity,)
        ).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO note_entities (note_id, entity_id) VALUES (?, ?)",
            (note_id, entity_id),
        )


def add_note(
    body: str,
    extra_tags: list[str] | None = None,
    extra_entities: list[str] | None = None,
    db_path: Path | None = None,
) -> Note:
    conn = connect(db_path)
    parsed = parse(body)
    tags = list(dict.fromkeys(parsed.tags + [t.lower() for t in (extra_tags or [])]))
    entities = list(dict.fromkeys(parsed.entities + [e.lower() for e in (extra_entities or [])]))
    now = datetime.now(timezone.utc).isoformat()

    cur = conn.execute(
        "INSERT INTO notes (uuid, body, created_at, updated_at, time_stamp) VALUES (?, ?, ?, ?, ?)",
        (str(uuid4()), body, now, now, now),
    )
    note_id = cur.lastrowid
    _attach_tags_entities(conn, note_id, tags, entities)
    conn.commit()
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return _load_note(conn, row)


def list_notes(
    tag: str | None = None,
    entity: str | None = None,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[Note]:
    conn = connect(db_path)

    if tag:
        rows = conn.execute(
            "SELECT n.* FROM notes n"
            " JOIN note_tags nt ON nt.note_id = n.id"
            " JOIN tags t ON t.id = nt.tag_id"
            " WHERE t.name = ?"
            " ORDER BY n.created_at DESC LIMIT ?",
            (tag.lower(), limit),
        ).fetchall()
    elif entity:
        rows = conn.execute(
            "SELECT n.* FROM notes n"
            " JOIN note_entities ne ON ne.note_id = n.id"
            " JOIN entities e ON e.id = ne.entity_id"
            " WHERE e.name = ?"
            " ORDER BY n.created_at DESC LIMIT ?",
            (entity.lower(), limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()

    return [_load_note(conn, r) for r in rows]


def search_notes(query: str, db_path: Path | None = None) -> list[Note]:
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT * FROM notes WHERE body LIKE ? ORDER BY created_at DESC",
        (f"%{query}%",),
    ).fetchall()
    return [_load_note(conn, r) for r in rows]


def update_note(
    note_id: int,
    body: str,
    extra_tags: list[str] | None = None,
    extra_entities: list[str] | None = None,
    db_path: Path | None = None,
) -> Note | None:
    conn = connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "UPDATE notes SET body = ?, updated_at = ? WHERE id = ?", (body, now, note_id)
    )
    if cur.rowcount == 0:
        conn.commit()
        return None

    parsed = parse(body)
    tags = list(dict.fromkeys(parsed.tags + [t.lower() for t in (extra_tags or [])]))
    entities = list(dict.fromkeys(parsed.entities + [e.lower() for e in (extra_entities or [])]))
    conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
    conn.execute("DELETE FROM note_entities WHERE note_id = ?", (note_id,))
    _attach_tags_entities(conn, note_id, tags, entities)
    conn.commit()
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return _load_note(conn, row)


def delete_note(note_id: int, db_path: Path | None = None) -> bool:
    conn = connect(db_path)
    row = conn.execute("SELECT uuid FROM notes WHERE id = ?", (note_id,)).fetchone()
    if row is None:
        return False
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.execute(
        "INSERT OR IGNORE INTO deleted_notes (uuid, deleted_at) VALUES (?, ?)",
        (row["uuid"], now),
    )
    conn.commit()
    return True


def list_tags(db_path: Path | None = None) -> list[str]:
    conn = connect(db_path)
    rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
    return [r["name"] for r in rows]


def list_entities(db_path: Path | None = None) -> list[Entity]:
    conn = connect(db_path)
    rows = conn.execute("SELECT * FROM entities ORDER BY name").fetchall()
    return [
        Entity(id=r["id"], name=r["name"], entity_type=r["entity_type"]) for r in rows
    ]


def set_entity_type(name: str, entity_type: str, db_path: Path | None = None) -> bool:
    conn = connect(db_path)
    cur = conn.execute(
        "UPDATE entities SET entity_type = ? WHERE name = ?",
        (entity_type, name.lower()),
    )
    conn.commit()
    return cur.rowcount > 0


def get_sync_folder(db_path: Path | None = None) -> str:
    conn = connect(db_path)
    row = conn.execute(
        "SELECT value FROM config WHERE key = 'sync_google_drive_folder'"
    ).fetchone()
    return str(row["value"]) if row else "note-taker-sync"


def set_sync_folder(name: str, db_path: Path | None = None) -> None:
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('sync_google_drive_folder', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (name.strip(),),
    )
    conn.commit()


def get_sync_adapter(db_path: Path | None = None) -> str:
    conn = connect(db_path)
    row = conn.execute(
        "SELECT value FROM config WHERE key = 'sync_adapter'"
    ).fetchone()
    return str(row["value"]) if row else "google_drive"


def set_sync_adapter(adapter: str, db_path: Path | None = None) -> None:
    if adapter not in ("google_drive", "local_folder"):
        raise ValueError(f"Unknown adapter {adapter!r}. Choose 'google_drive' or 'local_folder'.")
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('sync_adapter', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (adapter,),
    )
    conn.commit()


def get_sync_local_path(db_path: Path | None = None) -> str:
    conn = connect(db_path)
    row = conn.execute(
        "SELECT value FROM config WHERE key = 'sync_local_folder_path'"
    ).fetchone()
    return str(row["value"]) if row else ""


def set_sync_local_path(path: str, db_path: Path | None = None) -> None:
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('sync_local_folder_path', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (path.strip(),),
    )
    conn.commit()


def get_autosync_debounce_ms(db_path: Path | None = None) -> int:
    conn = connect(db_path)
    row = conn.execute(
        "SELECT value FROM config WHERE key = 'autosync_debounce_ms'"
    ).fetchone()
    return int(row["value"]) if row else 600_000


def set_autosync_debounce_ms(ms: int, db_path: Path | None = None) -> None:
    if ms < 1000:
        raise ValueError("Debounce interval must be at least 1000ms.")
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('autosync_debounce_ms', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (ms,),
    )
    conn.commit()


def get_default_tags(db_path: Path | None = None) -> list[str]:
    conn = connect(db_path)
    row = conn.execute(
        "SELECT value FROM config WHERE key = 'default_tags'"
    ).fetchone()
    if row is None or not row["value"]:
        return []
    return [t for t in row["value"].split(",") if t]


def set_default_tags(tags: list[str], db_path: Path | None = None) -> None:
    conn = connect(db_path)
    value = ",".join(t.lower().strip() for t in tags if t.strip())
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('default_tags', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (value,),
    )
    conn.commit()
