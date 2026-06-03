import re
import sqlite3
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from .dates import normalize_dates
from .db import connect
from .models import AtlasNode, AtlasPage, Instance, InstanceKind, Note, Reference
from .parser import normalise, parse


def _load_note(conn: sqlite3.Connection, row: sqlite3.Row) -> Note:
    note_id = row["id"]
    tags = [
        r["name"]
        for r in conn.execute(
            "SELECT t.name FROM tags t JOIN note_tags nt ON nt.tag_id = t.id WHERE nt.note_id = ?",
            (note_id,),
        )
    ]
    references = [
        r["name"]
        for r in conn.execute(
            'SELECT r.name FROM "references" r JOIN note_references nr ON nr.reference_id = r.id WHERE nr.note_id = ?',
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
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)",
            (note_id, tag_id),
        )
    for reference in references:
        conn.execute('INSERT OR IGNORE INTO "references" (name) VALUES (?)', (reference,))
        reference_id = conn.execute('SELECT id FROM "references" WHERE name = ?', (reference,)).fetchone()["id"]
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
    now = datetime.now(UTC).isoformat()

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
            "SELECT n.* FROM notes n"
            " JOIN note_references nr ON nr.note_id = n.id"
            ' JOIN "references" r ON r.id = nr.reference_id'
            " WHERE r.name = ?"
            " ORDER BY n.created_at DESC LIMIT ?",
            (reference.lower(), limit),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()

    return [_load_note(conn, r) for r in rows]


def search_notes(query: str, db_path: Path | None = None) -> list[Note]:
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT * FROM notes WHERE body LIKE ? ORDER BY created_at DESC",
        (f"%{query}%",),
    ).fetchall()
    return [_load_note(conn, r) for r in rows]


def _notes_for_instance(conn: sqlite3.Connection, instance: "Instance") -> list[Note]:
    if not instance.references:
        return []
    placeholders = ",".join("?" * len(instance.references))
    rows = conn.execute(
        "SELECT DISTINCT n.* FROM notes n"
        " JOIN note_references nr ON nr.note_id = n.id"
        ' JOIN "references" r ON r.id = nr.reference_id'
        f" WHERE r.name IN ({placeholders})"
        " ORDER BY n.time_stamp ASC",
        [r.lower() for r in instance.references],
    ).fetchall()
    return [_load_note(conn, row) for row in rows]


def _render_instance_kb(instance: "Instance", heading_level: int) -> str:
    prefix = "#" * heading_level
    lines: list[str] = [f"{prefix} {instance.name}", f"*{instance.type.name}*"]
    if instance.description:
        lines += ["", instance.description]
    return "\n".join(lines)


def export_kb_instance(name: str, db_path: Path | None = None) -> str:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM instances WHERE lower(name) = ?", (name.lower(),)).fetchone()
    if row is None:
        return ""
    instance = _load_instance(conn, row)
    return _render_instance_kb(instance, heading_level=1)


def export_kb_all(db_path: Path | None = None) -> str:
    conn = connect(db_path)
    kind_rows = conn.execute("SELECT * FROM instance_kinds ORDER BY name").fetchall()
    if not kind_rows:
        return ""
    sections: list[str] = []
    for kind_row in kind_rows:
        kind = _load_instance_kind(kind_row)
        instance_rows = conn.execute(
            "SELECT * FROM instances WHERE instance_kind_id = ? ORDER BY name", (kind_row["id"],)
        ).fetchall()
        heading = f"# {kind.plural or kind.name + 's'}"
        if not instance_rows:
            continue
        block = [heading]
        for row in instance_rows:
            instance = _load_instance(conn, row)
            block.append(_render_instance_kb(instance, heading_level=2))
        sections.append("\n\n".join(block))
    return "\n\n---\n\n".join(sections)


def export_kb_kind(kind_name: str, db_path: Path | None = None) -> str:
    conn = connect(db_path)
    kind_row = conn.execute("SELECT * FROM instance_kinds WHERE lower(name) = ?", (kind_name.lower(),)).fetchone()
    if kind_row is None:
        return ""
    kind = _load_instance_kind(kind_row)
    instance_rows = conn.execute(
        "SELECT * FROM instances WHERE instance_kind_id = ? ORDER BY name", (kind_row["id"],)
    ).fetchall()
    if not instance_rows:
        return f"# {kind.plural or kind.name + 's'}\n\n*No instances found.*"
    sections = [f"# {kind.plural or kind.name + 's'}"]
    for row in instance_rows:
        instance = _load_instance(conn, row)
        sections.append(_render_instance_kb(instance, heading_level=2))
    return "\n\n".join(sections)


def daily_report(start: date, end: date, db_path: Path | None = None) -> str:
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT * FROM notes WHERE date(time_stamp) BETWEEN ? AND ? ORDER BY time_stamp ASC",
        (start.isoformat(), end.isoformat()),
    ).fetchall()

    by_day: dict[date, list[Note]] = defaultdict(list)
    for row in rows:
        note = _load_note(conn, row)
        by_day[note.time_stamp.date()].append(note)

    sections: list[str] = []
    current = start
    from datetime import timedelta

    while current <= end:
        if current in by_day:
            heading = f"## {current.strftime('%A, %d %B %Y')}"
            notes_md = "\n\n".join(f"- {n.body}" for n in by_day[current])
            sections.append(f"{heading}\n\n{notes_md}")
        current += timedelta(days=1)

    return "\n\n".join(sections)


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
    now = datetime.now(UTC).isoformat()
    cur = conn.execute("UPDATE notes SET body = ?, updated_at = ? WHERE id = ?", (body, now, note_id))
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
    now = datetime.now(UTC).isoformat()
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
    return InstanceKind(
        id=row["id"],
        name=row["name"],
        plural=row["plural"],
        description=row["description"],
        uuid=row["uuid"] or "",
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


def _load_instance(conn: sqlite3.Connection, row: sqlite3.Row) -> Instance:
    kind_row = conn.execute("SELECT * FROM instance_kinds WHERE id = ?", (row["instance_kind_id"],)).fetchone()
    refs = [
        r["name"]
        for r in conn.execute(
            'SELECT ref.name FROM "references" ref'
            " JOIN instance_references ir ON ir.reference_id = ref.id"
            " WHERE ir.instance_id = ?",
            (row["id"],),
        )
    ]
    return Instance(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        type=_load_instance_kind(kind_row),
        references=refs,
        uuid=row["uuid"] or "",
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


def _attach_instance_references(conn: sqlite3.Connection, instance_id: int, references: list[str]) -> None:
    conn.execute("DELETE FROM instance_references WHERE instance_id = ?", (instance_id,))
    for ref in references:
        ref = ref.lower()
        conn.execute('INSERT OR IGNORE INTO "references" (name) VALUES (?)', (ref,))
        ref_id = conn.execute('SELECT id FROM "references" WHERE name = ?', (ref,)).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO instance_references (instance_id, reference_id) VALUES (?, ?)",
            (instance_id, ref_id),
        )


def create_type(name: str, plural: str = "", description: str = "", db_path: Path | None = None) -> InstanceKind:
    conn = connect(db_path)
    now = datetime.now(UTC).isoformat()
    cur = conn.execute(
        "INSERT INTO instance_kinds (name, plural, description, uuid, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (name.strip(), plural.strip(), description.strip(), str(uuid4()), now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM instance_kinds WHERE id = ?", (cur.lastrowid,)).fetchone()
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
    now = datetime.now(UTC).isoformat()
    cur = conn.execute(
        "UPDATE instance_kinds SET name = ?, plural = ?, description = ?, updated_at = ? WHERE id = ?",
        (name.strip(), plural.strip(), description.strip(), now, instance_kind_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    row = conn.execute("SELECT * FROM instance_kinds WHERE id = ?", (instance_kind_id,)).fetchone()
    return _load_instance_kind(row)


def delete_type(instance_kind_id: int, db_path: Path | None = None) -> bool:
    conn = connect(db_path)
    row = conn.execute("SELECT uuid FROM instance_kinds WHERE id = ?", (instance_kind_id,)).fetchone()
    if row is None:
        return False
    kind_uuid = row["uuid"]
    now = datetime.now(UTC).isoformat()
    cur = conn.execute("DELETE FROM instance_kinds WHERE id = ?", (instance_kind_id,))
    if cur.rowcount and kind_uuid:
        conn.execute(
            "INSERT OR IGNORE INTO deleted_instance_kinds (uuid, deleted_at) VALUES (?, ?)",
            (kind_uuid, now),
        )
    conn.commit()
    return cur.rowcount > 0


def create_instance(
    name: str,
    instance_kind_id: int,
    description: str = "",
    references: list[str] | None = None,
    db_path: Path | None = None,
) -> Instance:
    conn = connect(db_path)
    now = datetime.now(UTC).isoformat()
    cur = conn.execute(
        "INSERT INTO instances (name, description, instance_kind_id, uuid, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (name.strip(), description.strip(), instance_kind_id, str(uuid4()), now, now),
    )
    auto_ref = name.strip().replace(" ", "").lower()
    all_refs = list(dict.fromkeys([auto_ref] + [r.lower() for r in (references or [])]))
    _attach_instance_references(conn, cur.lastrowid, all_refs)  # type: ignore[arg-type]
    conn.commit()
    row = conn.execute("SELECT * FROM instances WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _load_instance(conn, row)


def get_instance(instance_id: int, db_path: Path | None = None) -> Instance | None:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)).fetchone()
    return _load_instance(conn, row) if row else None


def list_instances(instance_kind_id: int | None = None, db_path: Path | None = None) -> list[Instance]:
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
    references: list[str] | None = None,
    db_path: Path | None = None,
) -> Instance | None:
    conn = connect(db_path)
    now = datetime.now(UTC).isoformat()
    cur = conn.execute(
        "UPDATE instances SET name = ?, description = ?, instance_kind_id = ?, updated_at = ? WHERE id = ?",
        (name.strip(), description.strip(), instance_kind_id, now, instance_id),
    )
    if cur.rowcount == 0:
        conn.commit()
        return None
    _attach_instance_references(conn, instance_id, references or [])
    conn.commit()
    row = conn.execute("SELECT * FROM instances WHERE id = ?", (instance_id,)).fetchone()
    return _load_instance(conn, row)


def delete_instance(instance_id: int, db_path: Path | None = None) -> bool:
    conn = connect(db_path)
    row = conn.execute("SELECT uuid FROM instances WHERE id = ?", (instance_id,)).fetchone()
    if row is None:
        return False
    inst_uuid = row["uuid"]
    now = datetime.now(UTC).isoformat()
    cur = conn.execute("DELETE FROM instances WHERE id = ?", (instance_id,))
    if cur.rowcount and inst_uuid:
        conn.execute(
            "INSERT OR IGNORE INTO deleted_instances (uuid, deleted_at) VALUES (?, ?)",
            (inst_uuid, now),
        )
    conn.commit()
    return cur.rowcount > 0


def get_sync_folder(db_path: Path | None = None) -> str:
    conn = connect(db_path)
    row = conn.execute("SELECT value FROM config WHERE key = 'sync_google_drive_folder'").fetchone()
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
    row = conn.execute("SELECT value FROM config WHERE key = 'sync_adapter'").fetchone()
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
    row = conn.execute("SELECT value FROM config WHERE key = 'sync_local_folder_path'").fetchone()
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
    row = conn.execute("SELECT value FROM config WHERE key = 'autosync_debounce_ms'").fetchone()
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
    row = conn.execute("SELECT value FROM config WHERE key = 'default_tags'").fetchone()
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
    row = conn.execute("SELECT value FROM config WHERE key = 'pins_updated_at'").fetchone()
    return str(row["value"]) if row else ""


def set_pins(uuids: list[str], db_path: Path | None = None) -> None:
    from datetime import datetime

    now = datetime.now(UTC).isoformat()
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('pins', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (",".join(uuids),),
    )
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('pins_updated_at', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (now,),
    )
    conn.commit()


def _resolve_date_annotation(value: str | None, granularity: str | None) -> str | None:
    """Resolve a ~expression to an ISO date string formatted to the given granularity.

    If *value* does not start with ``~``, it is returned unchanged so callers
    can pass already-normalised values (e.g. ``2025-06``) without re-processing.
    """
    if not value:
        return None
    if not value.startswith("~"):
        return value
    normalized = normalize_dates(value).text
    m = re.search(r"~\{(\d{4}-\d{2}-\d{2})", normalized)
    if not m:
        return None  # expression didn't resolve — discard rather than store garbage
    iso_date = m.group(1)  # YYYY-MM-DD
    if granularity == "week":
        d = date.fromisoformat(iso_date)
        cal = d.isocalendar()
        return f"{cal.year}-W{cal.week:02d}"
    if granularity == "month":
        return iso_date[:7]
    if granularity == "year":
        return iso_date[:4]
    return iso_date  # "day" or unrecognised granularity → full date


# ── Atlas ──────────────────────────────────────────────────────────────────────


def _load_atlas_node(row: sqlite3.Row) -> AtlasNode:
    return AtlasNode(
        id=row["id"],
        uuid=row["uuid"],
        name=row["name"],
        parent_id=row["parent_id"],
        position=row["position"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _load_atlas_page(conn: sqlite3.Connection, row: sqlite3.Row) -> AtlasPage:
    page_id = row["id"]
    tags = [
        r["name"]
        for r in conn.execute(
            "SELECT t.name FROM tags t JOIN atlas_page_tags apt ON apt.tag_id = t.id WHERE apt.page_id = ?",
            (page_id,),
        )
    ]
    references = [
        r["name"]
        for r in conn.execute(
            'SELECT r.name FROM "references" r'
            " JOIN atlas_page_references apr ON apr.reference_id = r.id WHERE apr.page_id = ?",
            (page_id,),
        )
    ]
    date_annotation = row["date_annotation"]
    return AtlasPage(
        id=page_id,
        uuid=row["uuid"],
        node_id=row["node_id"],
        title=row["title"],
        body=row["body"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        tags=tags,
        references=references,
        dates=[date_annotation] if date_annotation else [],
    )


def _attach_page_tags_references(
    conn: sqlite3.Connection,
    page_id: int,
    tags: list[str],
    references: list[str],
) -> None:
    conn.execute("DELETE FROM atlas_page_tags WHERE page_id = ?", (page_id,))
    conn.execute("DELETE FROM atlas_page_references WHERE page_id = ?", (page_id,))
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()["id"]
        conn.execute("INSERT OR IGNORE INTO atlas_page_tags (page_id, tag_id) VALUES (?, ?)", (page_id, tag_id))
    for ref in references:
        conn.execute('INSERT OR IGNORE INTO "references" (name) VALUES (?)', (ref,))
        ref_id = conn.execute('SELECT id FROM "references" WHERE name = ?', (ref,)).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO atlas_page_references (page_id, reference_id) VALUES (?, ?)",
            (page_id, ref_id),
        )


def create_atlas_node(
    name: str,
    parent_id: int | None = None,
    position: int = 0,
    db_path: Path | None = None,
) -> AtlasNode:
    conn = connect(db_path)
    now = datetime.now(UTC).isoformat()
    cur = conn.execute(
        "INSERT INTO atlas_nodes (uuid, name, parent_id, position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid4()), name.strip(), parent_id, position, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM atlas_nodes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _load_atlas_node(row)


def list_atlas_nodes(db_path: Path | None = None) -> list[AtlasNode]:
    conn = connect(db_path)
    rows = conn.execute("SELECT * FROM atlas_nodes ORDER BY parent_id NULLS FIRST, position ASC").fetchall()
    return [_load_atlas_node(r) for r in rows]


def get_atlas_node(node_id: int, db_path: Path | None = None) -> AtlasNode | None:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM atlas_nodes WHERE id = ?", (node_id,)).fetchone()
    return _load_atlas_node(row) if row else None


def update_atlas_node(node_id: int, name: str, db_path: Path | None = None) -> AtlasNode | None:
    conn = connect(db_path)
    now = datetime.now(UTC).isoformat()
    cur = conn.execute(
        "UPDATE atlas_nodes SET name = ?, updated_at = ? WHERE id = ?",
        (name.strip(), now, node_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    row = conn.execute("SELECT * FROM atlas_nodes WHERE id = ?", (node_id,)).fetchone()
    return _load_atlas_node(row)


def move_atlas_node(
    node_id: int,
    new_parent_id: int | None,
    new_position: int,
    db_path: Path | None = None,
) -> AtlasNode | None:
    conn = connect(db_path)
    now = datetime.now(UTC).isoformat()
    cur = conn.execute(
        "UPDATE atlas_nodes SET parent_id = ?, position = ?, updated_at = ? WHERE id = ?",
        (new_parent_id, new_position, now, node_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        return None
    row = conn.execute("SELECT * FROM atlas_nodes WHERE id = ?", (node_id,)).fetchone()
    return _load_atlas_node(row)


def reorder_atlas_nodes(
    updates: list[tuple[int, int | None, int]],
    db_path: Path | None = None,
) -> None:
    conn = connect(db_path)
    now = datetime.now(UTC).isoformat()
    for node_id, parent_id, position in updates:
        conn.execute(
            "UPDATE atlas_nodes SET parent_id = ?, position = ?, updated_at = ? WHERE id = ?",
            (parent_id, position, now, node_id),
        )
    conn.commit()


def delete_atlas_node(node_id: int, db_path: Path | None = None) -> bool:
    conn = connect(db_path)
    row = conn.execute("SELECT uuid FROM atlas_nodes WHERE id = ?", (node_id,)).fetchone()
    if row is None:
        return False
    node_uuid = row["uuid"]
    now = datetime.now(UTC).isoformat()
    # Explicitly delete page first (FK RESTRICT prevents deletion otherwise)
    page_row = conn.execute("SELECT uuid FROM atlas_pages WHERE node_id = ?", (node_id,)).fetchone()
    if page_row:
        conn.execute("DELETE FROM atlas_pages WHERE node_id = ?", (node_id,))
        conn.execute(
            "INSERT OR IGNORE INTO deleted_atlas_pages (uuid, deleted_at) VALUES (?, ?)",
            (page_row["uuid"], now),
        )
    cur = conn.execute("DELETE FROM atlas_nodes WHERE id = ?", (node_id,))
    if cur.rowcount:
        conn.execute(
            "INSERT OR IGNORE INTO deleted_atlas_nodes (uuid, deleted_at) VALUES (?, ?)",
            (node_uuid, now),
        )
    conn.commit()
    return cur.rowcount > 0


def create_atlas_page(
    node_id: int,
    title: str,
    body: str = "",
    extra_tags: list[str] | None = None,
    extra_references: list[str] | None = None,
    date_annotation: str | None = None,
    date_granularity: str | None = None,
    db_path: Path | None = None,
) -> AtlasPage:
    conn = connect(db_path)
    now = datetime.now(UTC).isoformat()
    resolved_date = _resolve_date_annotation(date_annotation, date_granularity)
    cur = conn.execute(
        "INSERT INTO atlas_pages (uuid, node_id, title, body, created_at, updated_at, date_annotation)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid4()), node_id, title.strip(), body, now, now, resolved_date),
    )
    page_id = cur.lastrowid
    assert page_id is not None
    parsed = parse(body)
    tags = list(dict.fromkeys(parsed.tags + [t.lower() for t in (extra_tags or [])]))
    references = list(dict.fromkeys(parsed.references + [r.lower() for r in (extra_references or [])]))
    _attach_page_tags_references(conn, page_id, tags, references)
    conn.commit()
    row = conn.execute("SELECT * FROM atlas_pages WHERE id = ?", (page_id,)).fetchone()
    return _load_atlas_page(conn, row)


def get_atlas_page_node_ids(db_path: Path | None = None) -> set[int]:
    conn = connect(db_path)
    rows = conn.execute("SELECT node_id FROM atlas_pages").fetchall()
    return {r["node_id"] for r in rows}


def get_atlas_page_by_node(node_id: int, db_path: Path | None = None) -> AtlasPage | None:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM atlas_pages WHERE node_id = ?", (node_id,)).fetchone()
    return _load_atlas_page(conn, row) if row else None


def update_atlas_page(
    page_id: int,
    title: str,
    body: str,
    extra_tags: list[str] | None = None,
    extra_references: list[str] | None = None,
    date_annotation: str | None = None,
    date_granularity: str | None = None,
    db_path: Path | None = None,
) -> AtlasPage | None:
    conn = connect(db_path)
    now = datetime.now(UTC).isoformat()
    resolved_date = _resolve_date_annotation(date_annotation, date_granularity)
    cur = conn.execute(
        "UPDATE atlas_pages SET title = ?, body = ?, updated_at = ?, date_annotation = ? WHERE id = ?",
        (title.strip(), body, now, resolved_date, page_id),
    )
    if cur.rowcount == 0:
        conn.commit()
        return None
    parsed = parse(body)
    tags = list(dict.fromkeys(parsed.tags + [t.lower() for t in (extra_tags or [])]))
    references = list(dict.fromkeys(parsed.references + [r.lower() for r in (extra_references or [])]))
    _attach_page_tags_references(conn, page_id, tags, references)
    conn.commit()
    row = conn.execute("SELECT * FROM atlas_pages WHERE id = ?", (page_id,)).fetchone()
    return _load_atlas_page(conn, row)


def delete_atlas_page(page_id: int, db_path: Path | None = None) -> bool:
    conn = connect(db_path)
    row = conn.execute("SELECT uuid FROM atlas_pages WHERE id = ?", (page_id,)).fetchone()
    if row is None:
        return False
    page_uuid = row["uuid"]
    now = datetime.now(UTC).isoformat()
    cur = conn.execute("DELETE FROM atlas_pages WHERE id = ?", (page_id,))
    if cur.rowcount:
        conn.execute(
            "INSERT OR IGNORE INTO deleted_atlas_pages (uuid, deleted_at) VALUES (?, ?)",
            (page_uuid, now),
        )
    conn.commit()
    return cur.rowcount > 0
