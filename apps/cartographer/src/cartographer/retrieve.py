"""
Chunk retrieval by note ID.

Given a set of note integer IDs, averages their stored embedding vectors
(no re-embedding needed) and returns the top-K most similar chunks from
the full index, excluding the input notes themselves.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cartographer.db import connect


@dataclass
class RetrievedChunk:
    chunk_id: str       # source_uuid from the embeddings table
    note_id: int | None # integer note ID for note chunks; None for atlas/kinds/instances
    text: str
    score: float


def retrieve(
    note_ids: list[int],
    top_k: int,
    db_path: Path | None = None,
) -> list[RetrievedChunk]:
    """Return up to top_k chunks semantically related to the given notes.

    Uses the stored embedding vectors for the input notes to build a query
    vector (centroid), then ranks all other indexed chunks by cosine similarity.
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

    raw_vecs = [list(struct.unpack(f"{n_dims}f", row["vector"])) for row in note_rows]
    query_vec = _centroid(raw_vecs)
    input_uuids = {row["uuid"] for row in note_rows}

    # Fetch all indexed chunks (all corpora, primary chunk only)
    all_rows: list[Any] = conn.execute(
        "SELECT e.source_uuid, e.source_type, e.vector,"
        "       n.id          AS note_int_id,"
        "       n.body        AS note_body,"
        "       ap.title      AS page_title,"
        "       ap.body       AS page_body,"
        "       ik.name       AS kind_name,"
        "       ik.description AS kind_desc,"
        "       inst.name     AS inst_name,"
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

    scored: list[RetrievedChunk] = []
    for row in all_rows:
        if row["source_uuid"] in input_uuids:
            continue

        sim = _cosine(query_vec, row["vector"], n_dims)
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
            continue

        scored.append(RetrievedChunk(
            chunk_id=row["source_uuid"],
            note_id=note_id,
            text=text,
            score=round(sim, 6),
        ))

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cosine(a: list[float], b_blob: bytes, n_dims: int) -> float:
    b = struct.unpack(f"{n_dims}f", b_blob)
    dot = float(sum(x * y for x, y in zip(a, b)))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(float(x) * float(x) for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _centroid(vecs: list[list[float]]) -> list[float]:
    n = len(vecs[0])
    total = [0.0] * n
    for v in vecs:
        for i, x in enumerate(v):
            total[i] += x
    count = len(vecs)
    return [x / count for x in total]
