import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .dates import normalize_dates
from .db import connect
from .models import Instance, InstanceKind, Reference, Note
from .parser import normalise, parse


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
    references = [
        r["name"]
        for r in conn.execute(
            'SELECT r.name FROM "references" r'
            " JOIN note_references nr ON nr.reference_id = r.id"
            " WHERE nr.note_id = ?",
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
        references=references,
    )


def _attach_tags_references(
    conn: sqlite3.Connection,
    note_id: int | None,
    tags: list[str],
    references: list[str],
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
    for reference in references:
        conn.execute('INSERT OR IGNORE INTO "references" (name) VALUES (?)', (reference,))
        reference_id = conn.execute(
            'SELECT id FROM "references" WHERE name = ?', (reference,)
        ).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO note_references (note_id, reference_id) VALUES (?, ?)",
            (note_id, reference_id),
        )


def add_note(
    body: str,
    extra_tags: list[str] | None = None,
    extra_references: list[str] | None = None,
    db_path: Path | None = None,
) -> Note:
    conn = connect(db_path)
    body = normalise(normalize_dates(body).text)
    parsed = parse(body)
    tags = list(dict.fromkeys(parsed.tags + [t.lower() for t in (extra_tags or [])]))
    references = list(dict.fromkeys(parsed.references + [r.lower() for r in (extra_references or [])]))
    now = datetime.now(timezone.utc).isoformat()

    cur = conn.execute(
        "INSERT INTO notes (uuid, body, created_at, updated_at, time_stamp) VALUES (?, ?, ?, ?, ?)",
        (str(uuid4()), body, now, now, now),
    )
    note_id = cur.lastrowid
    _attach_tags_references(conn, note_id, tags, references)
    conn.commit()
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return _load_note(conn, row)


def list_notes(
    tag: str | None = None,
    reference: str | None = None,
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
    elif reference:
        rows = conn.execute(
            'SELECT n.* FROM notes n'
            ' JOIN note_references nr ON nr.note_id = n.id'
            ' JOIN "references" r ON r.id = nr.reference_id'
            ' WHERE r.name = ?'
            ' ORDER BY n.created_at DESC LIMIT ?',
            (reference.lower(), limit),
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


def get_note(note_id: int, db_path: Path | None = None) -> Note | None:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if row is None:
        return None
    return _load_note(conn, row)


def update_note(
    note_id: int,
    body: str,
    extra_tags: list[str] | None = None,
    extra_references: list[str] | None = None,
    db_path: Path | None = None,
) -> Note | None:
    conn = connect(db_path)
    body = normalise(normalize_dates(body).text)
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "UPDATE notes SET body = ?, updated_at = ? WHERE id = ?", (body, now, note_id)
    )
    if cur.rowcount == 0:
        conn.commit()
        return None

    parsed = parse(body)
    tags = list(dict.fromkeys(parsed.tags + [t.lower() for t in (extra_tags or [])]))
    references = list(dict.fromkeys(parsed.references + [r.lower() for r in (extra_references or [])]))
    conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
    conn.execute("DELETE FROM note_references WHERE note_id = ?", (note_id,))
    _attach_tags_references(conn, note_id, tags, references)
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


def list_references(db_path: Path | None = None) -> list[Reference]:
    conn = connect(db_path)
    rows = conn.execute('SELECT * FROM "references" ORDER BY name').fetchall()
    return [Reference(id=r["id"], name=r["name"]) for r in rows]


def _load_instance_kind(row: sqlite3.Row) -> InstanceKind:
    return InstanceKind(id=row["id"], name=row["name"], plural=row["plural"], description=row["description"])


def _load_instance(conn: sqlite3.Connection, row: sqlite3.Row) -> Instance:
    kind_row = conn.execute(
        "SELECT * FROM instance_kinds WHERE id = ?", (row["instance_kind_id"],)
    ).fetchone()
    return Instance(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        type=_load_instance_kind(kind_row),
    )


def create_type(
    name: str, plural: str = "", description: str = "", db_path: Path | None = None
) -> InstanceKind:
    conn = connect(db_path)
    cur = conn.execute(
        "INSERT INTO instance_kinds (name, plural, description) VALUES (?, ?, ?)",
        (name.strip(), plural.strip(), description.strip()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM instance_kinds WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return _load_instance_kind(row)


def get_type(instance_kind_id: int, db_path: Path | None = None) -> InstanceKind | None:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM instance_kinds WHERE id = ?", (instance_kind_id,)).fetchone()
    return _load_instance_kind(row) if row else None


def list_types(db_path: Path | None = None) -> list[InstanceKind]:
    conn = connect(db_path)
    rows = conn.execute("SELECT * FROM instance_kinds ORDER BY name").fetchall()
    return [_load_instance_kind(r) for r in rows]


def update_type(
    instance_kind_id: int,
    name: str,
    plural: str,
    description: str,
    db_path: Path | None = None,
) -> InstanceKind | None:
    conn = connect(db_path)
    cur = conn.execute(
        "UPDATE instance_kinds SET name = ?, plural = ?, description = ? WHERE id = ?",
        (name.strip(), plural.strip(), description.strip(), instance_kind_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    row = conn.execute("SELECT * FROM instance_kinds WHERE id = ?", (instance_kind_id,)).fetchone()
    return _load_instance_kind(row)


def delete_type(instance_kind_id: int, db_path: Path | None = None) -> bool:
    conn = connect(db_path)
    cur = conn.execute("DELETE FROM instance_kinds WHERE id = ?", (instance_kind_id,))
    conn.commit()
    return cur.rowcount > 0


def create_instance(
    name: str,
    instance_kind_id: int,
    description: str = "",
    db_path: Path | None = None,
) -> Instance:
    conn = connect(db_path)
    cur = conn.execute(
        "INSERT INTO instances (name, description, instance_kind_id) VALUES (?, ?, ?)",
        (name.strip(), description.strip(), instance_kind_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM instances WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return _load_instance(conn, row)


def get_instance(instance_id: int, db_path: Path | None = None) -> Instance | None:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)).fetchone()
    return _load_instance(conn, row) if row else None


def list_instances(
    instance_kind_id: int | None = None, db_path: Path | None = None
) -> list[Instance]:
    conn = connect(db_path)
    if instance_kind_id is not None:
        rows = conn.execute(
            "SELECT * FROM instances WHERE instance_kind_id = ? ORDER BY name",
            (instance_kind_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM instances ORDER BY name").fetchall()
    return [_load_instance(conn, r) for r in rows]


def update_instance(
    instance_id: int,
    name: str,
    description: str,
    instance_kind_id: int,
    db_path: Path | None = None,
) -> Instance | None:
    conn = connect(db_path)
    cur = conn.execute(
        "UPDATE instances SET name = ?, description = ?, instance_kind_id = ? WHERE id = ?",
        (name.strip(), description.strip(), instance_kind_id, instance_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    row = conn.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)).fetchone()
    return _load_instance(conn, row)


def delete_instance(instance_id: int, db_path: Path | None = None) -> bool:
    conn = connect(db_path)
    cur = conn.execute("DELETE FROM instances WHERE id = ?", (instance_id,))
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


def get_pins(db_path: Path | None = None) -> list[str]:
    conn = connect(db_path)
    row = conn.execute("SELECT value FROM config WHERE key = 'pins'").fetchone()
    if row is None or not row["value"]:
        return []
    return [u for u in row["value"].split(",") if u]


def get_pins_updated_at(db_path: Path | None = None) -> str:
    conn = connect(db_path)
    row = conn.execute(
        "SELECT value FROM config WHERE key = 'pins_updated_at'"
    ).fetchone()
    return str(row["value"]) if row else ""


def set_pins(uuids: list[str], db_path: Path | None = None) -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('pins', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (",".join(uuids),),
    )
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('pins_updated_at', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (now,),
    )
    conn.commit()
