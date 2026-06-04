# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Chunk retrieval by note ID.

Given a set of note integer IDs, scores the full embedding index independently
against each note's stored vector, collects the top-K results per note, then
unions and deduplicates by chunk_id (keeping the highest score). This guarantees
every input note is represented in the context pool, rather than being drowned
out by a centroid dominated by other notes.
"""

from __future__ import annotations

import math
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cartographer.db import connect


@dataclass
class RetrievedChunk:
    chunk_id: str  # source_uuid from the embeddings table
    note_id: int | None  # integer note ID for note chunks; None for atlas/kinds/instances
    text: str
    score: float


def retrieve(
    note_ids: list[int],
    top_k: int,
    db_path: Path | None = None,
) -> list[RetrievedChunk]:
    """Return chunks semantically related to the given notes.

    Scores the index independently per note and takes the top_k nearest
    neighbours for each. Results are unioned and deduplicated by chunk_id
    (highest score wins). The final list is sorted by score descending.

    top_k is a per-note budget, not a global cap.
    """
    if not note_ids:
        return []

    conn = connect(db_path)
    placeholders = ",".join("?" * len(note_ids))

    # Fetch stored vectors for the input notes (chunk 0 = primary representation)
    note_rows = conn.execute(
        f"SELECT n.uuid, e.vector, e.model"
        f" FROM notes n"
        f" JOIN embeddings e ON e.source_uuid = n.uuid"
        f"   AND e.source_type = 'note' AND e.chunk_index = 0"
        f" WHERE n.id IN ({placeholders})",
        note_ids,
    ).fetchall()

    if not note_rows:
        return []

    model: str = note_rows[0]["model"]
    n_dims: int = len(note_rows[0]["vector"]) // 4
    input_uuids = {row["uuid"] for row in note_rows}

    # Fetch all candidate embeddings once (excludes input notes)
    all_rows: list[Any] = conn.execute(
        "SELECT e.source_uuid, e.source_type, e.vector,"
        "       n.id           AS note_int_id,"
        "       n.body         AS note_body,"
        "       ap.title       AS page_title,"
        "       ap.body        AS page_body,"
        "       ik.name        AS kind_name,"
        "       ik.description AS kind_desc,"
        "       inst.name      AS inst_name,"
        "       inst.description AS inst_desc"
        " FROM embeddings e"
        " LEFT JOIN notes n"
        "        ON n.uuid = e.source_uuid AND e.source_type = 'note'"
        " LEFT JOIN atlas_pages ap"
        "        ON ap.uuid = e.source_uuid AND e.source_type = 'atlas_page'"
        " LEFT JOIN instance_kinds ik"
        "        ON ik.uuid = e.source_uuid AND e.source_type = 'instance_kind'"
        " LEFT JOIN instances inst"
        "        ON inst.uuid = e.source_uuid AND e.source_type = 'instance'"
        " WHERE e.model = ? AND e.chunk_index = 0 AND LENGTH(e.vector) = ?",
        [model, n_dims * 4],
    ).fetchall()

    candidates = [r for r in all_rows if r["source_uuid"] not in input_uuids]

    # Score each candidate once per input note; keep per-note top-K in a
    # chunk_id → RetrievedChunk map (highest score wins on collision).
    seen: dict[str, RetrievedChunk] = {}

    for note_row in note_rows:
        query_vec = list(struct.unpack(f"{n_dims}f", note_row["vector"]))

        scored: list[tuple[float, Any]] = []
        for row in candidates:
            sim = _cosine(query_vec, row["vector"], n_dims)
            scored.append((sim, row))

        scored.sort(key=lambda t: t[0], reverse=True)

        for sim, row in scored[:top_k]:
            chunk = _make_chunk(row, sim)
            if chunk is None:
                continue
            existing = seen.get(chunk.chunk_id)
            if existing is None or sim > existing.score:
                seen[chunk.chunk_id] = chunk

    results = sorted(seen.values(), key=lambda c: c.score, reverse=True)
    results += _lookup_note_ref_definitions(conn, note_ids)
    return results


# ---------------------------------------------------------------------------
# Registry definition lookup
# ---------------------------------------------------------------------------


def _lookup_note_ref_definitions(
    conn: sqlite3.Connection,
    note_ids: list[int],
) -> list[RetrievedChunk]:
    """Return Instance and Kind definition chunks for all @refs attached to the input notes."""
    if not note_ids:
        return []

    placeholders = ",".join("?" * len(note_ids))
    rows = conn.execute(
        f"""
        SELECT DISTINCT
               i.uuid  AS inst_uuid,
               i.name  AS inst_name,
               i.description AS inst_desc,
               ik.uuid AS kind_uuid,
               ik.name AS kind_name,
               ik.plural AS kind_plural,
               ik.description AS kind_desc
        FROM notes n
        JOIN note_references nr ON nr.note_id = n.id
        JOIN "references" r ON r.id = nr.reference_id
        JOIN instance_references ir ON ir.reference_id = r.id
        JOIN instances i ON i.id = ir.instance_id
        JOIN instance_kinds ik ON ik.id = i.instance_kind_id
        WHERE n.id IN ({placeholders})
        """,
        note_ids,
    ).fetchall()

    chunks: list[RetrievedChunk] = []
    seen_uuids: set[str] = set()

    for row in rows:
        if row["inst_uuid"] not in seen_uuids:
            seen_uuids.add(row["inst_uuid"])
            kind = (row["kind_name"] or "").strip()
            name = (row["inst_name"] or "").strip()
            desc = (row["inst_desc"] or "").strip()
            text = f"[{kind}] {name}\n{desc}".strip() if desc else f"[{kind}] {name}"
            chunks.append(RetrievedChunk(chunk_id=row["inst_uuid"], note_id=None, text=text, score=1.0))

        if row["kind_uuid"] not in seen_uuids:
            seen_uuids.add(row["kind_uuid"])
            name = (row["kind_name"] or "").strip()
            plural = (row["kind_plural"] or "").strip()
            desc = (row["kind_desc"] or "").strip()
            label = f"{name} ({plural})" if plural and plural != name else name
            text = f"{label}: {desc}" if desc else label
            chunks.append(RetrievedChunk(chunk_id=row["kind_uuid"], note_id=None, text=text, score=1.0))

    return chunks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(row: Any, sim: float) -> RetrievedChunk | None:
    source_type: str = row["source_type"]

    if source_type == "note":
        text = (row["note_body"] or "").strip()
        note_id: int | None = int(row["note_int_id"]) if row["note_int_id"] is not None else None
    elif source_type == "atlas_page":
        title = (row["page_title"] or "").strip()
        body = (row["page_body"] or "").strip()
        text = f"{title}\n{body}".strip() if title else body
        note_id = None
    elif source_type == "instance_kind":
        name = (row["kind_name"] or "").strip()
        desc = (row["kind_desc"] or "").strip()
        text = f"{name}: {desc}" if desc else name
        note_id = None
    elif source_type == "instance":
        name = (row["inst_name"] or "").strip()
        desc = (row["inst_desc"] or "").strip()
        text = f"{name}: {desc}" if desc else name
        note_id = None
    else:
        return None

    return RetrievedChunk(chunk_id=row["source_uuid"], note_id=note_id, text=text, score=round(sim, 6))


def _cosine(a: list[float], b_blob: bytes, n_dims: int) -> float:
    b = struct.unpack(f"{n_dims}f", b_blob)
    dot = float(sum(x * y for x, y in zip(a, b)))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(float(x) * float(x) for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
