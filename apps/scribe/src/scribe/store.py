# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Read-only access to the Cartographer SQLite DB for note retrieval."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NoteRecord:
    id: int
    body: str
    time_stamp: str  # ISO 8601 — COALESCE(time_stamp, created_at)
    tags: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


def fetch_notes_in_range(from_date: str, to_date: str, db_path: Path) -> list[NoteRecord]:
    """Return notes whose semantic date falls within [from_date, to_date] (inclusive, YYYY-MM-DD)."""
    if not db_path.exists():
        raise RuntimeError(
            f"Cartographer DB not found at {db_path}. Run `cartographer sync` to build the local mirror."
        )

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT n.id,
               n.body,
               COALESCE(n.time_stamp, n.created_at) AS time_stamp,
               (SELECT GROUP_CONCAT(t.name, ',')
                FROM note_tags nt JOIN tags t ON t.id = nt.tag_id
                WHERE nt.note_id = n.id) AS tag_names,
               (SELECT GROUP_CONCAT(r.name, ',')
                FROM note_references nr JOIN "references" r ON r.id = nr.reference_id
                WHERE nr.note_id = n.id) AS ref_names
        FROM notes n
        WHERE DATE(COALESCE(n.time_stamp, n.created_at)) >= ?
          AND DATE(COALESCE(n.time_stamp, n.created_at)) <= ?
        ORDER BY COALESCE(n.time_stamp, n.created_at) ASC
        """,
        (from_date, to_date),
    ).fetchall()

    conn.close()

    return [
        NoteRecord(
            id=int(row["id"]),
            body=row["body"] or "",
            time_stamp=row["time_stamp"] or "",
            tags=_split(row["tag_names"]),
            references=_split(row["ref_names"]),
        )
        for row in rows
    ]


def fetch_notes_by_tag(tag: str, from_date: str, to_date: str, db_path: Path) -> list[NoteRecord]:
    """Return notes tagged with `tag` whose semantic date falls within [from_date, to_date] (inclusive, YYYY-MM-DD)."""
    if not db_path.exists():
        raise RuntimeError(
            f"Cartographer DB not found at {db_path}. Run `cartographer sync` to build the local mirror."
        )

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT n.id,
               n.body,
               COALESCE(n.time_stamp, n.created_at) AS time_stamp,
               (SELECT GROUP_CONCAT(t.name, ',')
                FROM note_tags nt JOIN tags t ON t.id = nt.tag_id
                WHERE nt.note_id = n.id) AS tag_names,
               (SELECT GROUP_CONCAT(r.name, ',')
                FROM note_references nr JOIN "references" r ON r.id = nr.reference_id
                WHERE nr.note_id = n.id) AS ref_names
        FROM notes n
        WHERE DATE(COALESCE(n.time_stamp, n.created_at)) >= ?
          AND DATE(COALESCE(n.time_stamp, n.created_at)) <= ?
          AND n.id IN (
              SELECT nt.note_id FROM note_tags nt
              JOIN tags t ON t.id = nt.tag_id
              WHERE t.name = ?
          )
        ORDER BY COALESCE(n.time_stamp, n.created_at) ASC
        """,
        (from_date, to_date, tag),
    ).fetchall()

    conn.close()

    return [
        NoteRecord(
            id=int(row["id"]),
            body=row["body"] or "",
            time_stamp=row["time_stamp"] or "",
            tags=_split(row["tag_names"]),
            references=_split(row["ref_names"]),
        )
        for row in rows
    ]


def fetch_notes_by_ref(
    ref: str,
    db_path: Path,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[NoteRecord]:
    """Return notes mentioning @ref, optionally filtered to a date range."""
    if not db_path.exists():
        raise RuntimeError(
            f"Cartographer DB not found at {db_path}. Run `cartographer sync` to build the local mirror."
        )

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT n.id,
               n.body,
               COALESCE(n.time_stamp, n.created_at) AS time_stamp,
               (SELECT GROUP_CONCAT(t.name, ',')
                FROM note_tags nt JOIN tags t ON t.id = nt.tag_id
                WHERE nt.note_id = n.id) AS tag_names,
               (SELECT GROUP_CONCAT(r.name, ',')
                FROM note_references nr JOIN "references" r ON r.id = nr.reference_id
                WHERE nr.note_id = n.id) AS ref_names
        FROM notes n
        WHERE n.id IN (
            SELECT nr.note_id FROM note_references nr
            JOIN "references" r ON r.id = nr.reference_id
            WHERE r.name = ?
        )
    """
    params: list[str] = [ref]

    if from_date:
        query += " AND DATE(COALESCE(n.time_stamp, n.created_at)) >= ?"
        params.append(from_date)
    if to_date:
        query += " AND DATE(COALESCE(n.time_stamp, n.created_at)) <= ?"
        params.append(to_date)

    query += " ORDER BY COALESCE(n.time_stamp, n.created_at) ASC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [
        NoteRecord(
            id=int(row["id"]),
            body=row["body"] or "",
            time_stamp=row["time_stamp"] or "",
            tags=_split(row["tag_names"]),
            references=_split(row["ref_names"]),
        )
        for row in rows
    ]


@dataclass
class KindRecord:
    id: int
    name: str
    plural: str
    description: str


@dataclass
class InstanceRecord:
    id: int
    name: str
    description: str
    references: list[str] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)


def fetch_kinds(db_path: Path) -> list[KindRecord]:
    """Return all Kinds from the Cartographer DB, ordered by name."""
    if not db_path.exists():
        raise RuntimeError(f"Cartographer DB not found at {db_path}. Run `carto sync pull` to build the local mirror.")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name, plural, description FROM instance_kinds ORDER BY name").fetchall()
    conn.close()
    return [KindRecord(id=int(r["id"]), name=r["name"], plural=r["plural"], description=r["description"]) for r in rows]


def fetch_instances(kind_id: int, db_path: Path) -> list[InstanceRecord]:
    """Return all Instances of a Kind, with their references and properties, ordered by name."""
    if not db_path.exists():
        raise RuntimeError(f"Cartographer DB not found at {db_path}. Run `carto sync pull` to build the local mirror.")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT i.id,
               i.name,
               i.description,
               (SELECT GROUP_CONCAT(r.name, ',')
                FROM instance_references ir JOIN "references" r ON r.id = ir.reference_id
                WHERE ir.instance_id = i.id) AS ref_names
        FROM instances i
        WHERE i.instance_kind_id = ?
        ORDER BY i.name
        """,
        (kind_id,),
    ).fetchall()

    # Fetch all properties for this kind's instances in one query (name-ordered so
    # the resulting dict is stable).
    props_by_id: dict[int, dict[str, str]] = {}
    has_props = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='instance_properties'").fetchone()
    if has_props:
        for pr in conn.execute(
            """
            SELECT ip.instance_id, ip.name, ip.value
            FROM instance_properties ip
            JOIN instances i ON i.id = ip.instance_id
            WHERE i.instance_kind_id = ?
            ORDER BY ip.name
            """,
            (kind_id,),
        ):
            props_by_id.setdefault(int(pr["instance_id"]), {})[pr["name"]] = pr["value"]

    conn.close()
    return [
        InstanceRecord(
            id=int(r["id"]),
            name=r["name"],
            description=r["description"] or "",
            references=_split(r["ref_names"]),
            properties=props_by_id.get(int(r["id"]), {}),
        )
        for r in rows
    ]


def _split(csv: str | None) -> list[str]:
    if not csv:
        return []
    return [x.strip() for x in csv.split(",") if x.strip()]
