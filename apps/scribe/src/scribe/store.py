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
            f"Cartographer DB not found at {db_path}. "
            "Run `cartographer sync` to build the local mirror."
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
            f"Cartographer DB not found at {db_path}. "
            "Run `cartographer sync` to build the local mirror."
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


def _split(csv: str | None) -> list[str]:
    if not csv:
        return []
    return [x.strip() for x in csv.split(",") if x.strip()]
