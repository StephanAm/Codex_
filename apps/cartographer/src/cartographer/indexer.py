"""
Vector indexing pipeline for Cartographer.

Iterates over notes and atlas_pages in the local mirror DB, computes embeddings
for items that are new or stale (content or model changed), and stores the
results in the embeddings + index_state tables.
"""

import struct
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from cartographer.db import connect

if TYPE_CHECKING:
    from cartographer.embeddings.base import EmbeddingBackend


@dataclass
class IndexReport:
    notes_indexed: int = 0
    notes_skipped: int = 0
    atlas_pages_indexed: int = 0
    atlas_pages_skipped: int = 0
    kinds_indexed: int = 0
    kinds_skipped: int = 0
    instances_indexed: int = 0
    instances_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_indexed(self) -> int:
        return self.notes_indexed + self.atlas_pages_indexed + self.kinds_indexed + self.instances_indexed


def _encode(v: list[float]) -> bytes:
    return struct.pack(f"{len(v)}f", *v)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _note_text(body: str, tags: list[str]) -> str:
    prefix = " ".join(f"#{t}" for t in tags)
    return f"{prefix}\n{body}" if prefix else body


def _page_text(title: str, body: str) -> str:
    return f"{title}\n{body}" if title else body


def _kind_text(name: str, plural: str, description: str) -> str:
    parts = [name]
    if plural and plural != name:
        parts.append(f"({plural})")
    if description:
        parts.append(description)
    return " ".join(parts)


def _instance_text(kind_name: str, name: str, description: str) -> str:
    header = f"[{kind_name}] {name}" if kind_name else name
    return f"{header}\n{description}" if description else header


def run_index(
    backend: "EmbeddingBackend",
    db_path: Path | None = None,
    force: bool = False,
    batch_size: int = 32,
) -> IndexReport:
    conn = connect(db_path)
    report = IndexReport()

    # Current index state keyed by (uuid, source_type) → (source_updated_at, model)
    idx: dict[tuple[str, str], tuple[str, str]] = {
        (row["source_uuid"], row["source_type"]): (row["source_updated_at"], row["model"])
        for row in conn.execute(
            "SELECT source_uuid, source_type, source_updated_at, model FROM index_state"
        ).fetchall()
    }

    model_name = backend.model_name

    # --- Notes ---
    tags_map: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT n.uuid AS note_uuid, t.name AS tag"
        " FROM note_tags nt"
        " JOIN notes n ON n.id = nt.note_id"
        " JOIN tags t ON t.id = nt.tag_id"
    ).fetchall():
        tags_map.setdefault(row["note_uuid"], []).append(row["tag"])

    notes_rows = conn.execute("SELECT uuid, body, updated_at FROM notes").fetchall()
    notes_to_index = []
    for row in notes_rows:
        cached = idx.get((row["uuid"], "note"))
        if not force and cached and cached[0] == row["updated_at"] and cached[1] == model_name:
            report.notes_skipped += 1
        else:
            notes_to_index.append(row)

    # --- Atlas pages ---
    pages_rows = conn.execute(
        "SELECT uuid, title, body, updated_at FROM atlas_pages"
    ).fetchall()
    pages_to_index = []
    for row in pages_rows:
        cached = idx.get((row["uuid"], "atlas_page"))
        if not force and cached and cached[0] == row["updated_at"] and cached[1] == model_name:
            report.atlas_pages_skipped += 1
        else:
            pages_to_index.append(row)

    # --- Instance kinds ---
    kinds_rows = conn.execute(
        "SELECT uuid, name, plural, description, updated_at FROM instance_kinds"
    ).fetchall()
    kinds_to_index = []
    for row in kinds_rows:
        cached = idx.get((row["uuid"], "instance_kind"))
        updated = row["updated_at"] or ""
        if not force and cached and cached[0] == updated and cached[1] == model_name:
            report.kinds_skipped += 1
        else:
            kinds_to_index.append(row)

    # --- Instances (join kind name for context) ---
    instances_rows = conn.execute(
        "SELECT i.uuid, i.name, i.description, i.updated_at, k.name AS kind_name"
        " FROM instances i"
        " JOIN instance_kinds k ON k.id = i.instance_kind_id"
    ).fetchall()
    instances_to_index = []
    for row in instances_rows:
        cached = idx.get((row["uuid"], "instance"))
        updated = row["updated_at"] or ""
        if not force and cached and cached[0] == updated and cached[1] == model_name:
            report.instances_skipped += 1
        else:
            instances_to_index.append(row)

    def _store_batch(
        batch: list,
        source_type: str,
        texts: list[str],
        vectors: list[list[float]],
    ) -> None:
        now = _now()
        for row, vector in zip(batch, vectors):
            blob = _encode(vector)
            conn.execute(
                "INSERT INTO embeddings"
                " (source_uuid, source_type, chunk_index, model, vector, indexed_at)"
                " VALUES (?, ?, 0, ?, ?, ?)"
                " ON CONFLICT(source_uuid, source_type, chunk_index, model) DO UPDATE SET"
                " vector = excluded.vector, indexed_at = excluded.indexed_at",
                (row["uuid"], source_type, model_name, blob, now),
            )
            conn.execute(
                "INSERT INTO index_state"
                " (source_uuid, source_type, source_updated_at, model, indexed_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(source_uuid, source_type) DO UPDATE SET"
                " source_updated_at = excluded.source_updated_at,"
                " model = excluded.model,"
                " indexed_at = excluded.indexed_at",
                (row["uuid"], source_type, row["updated_at"] or "", model_name, now),
            )
        conn.commit()

    def _run_batches(
        items: list,
        source_type: str,
        text_fn,  # callable(row) -> str
    ) -> tuple[int, list[str]]:
        indexed = 0
        errors: list[str] = []
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            texts = [text_fn(row) for row in batch]
            try:
                vectors = backend.embed(texts)
            except Exception as exc:
                for row in batch:
                    errors.append(f"{source_type} {row['uuid']}: {exc}")
                continue
            _store_batch(batch, source_type, texts, vectors)
            indexed += len(batch)
        return indexed, errors

    n, errs = _run_batches(
        notes_to_index,
        "note",
        lambda row: _note_text(row["body"] or "", tags_map.get(row["uuid"], [])),
    )
    report.notes_indexed = n
    report.errors.extend(errs)

    p, errs = _run_batches(
        pages_to_index,
        "atlas_page",
        lambda row: _page_text(row["title"] or "", row["body"] or ""),
    )
    report.atlas_pages_indexed = p
    report.errors.extend(errs)

    k, errs = _run_batches(
        kinds_to_index,
        "instance_kind",
        lambda row: _kind_text(row["name"] or "", row["plural"] or "", row["description"] or ""),
    )
    report.kinds_indexed = k
    report.errors.extend(errs)

    i, errs = _run_batches(
        instances_to_index,
        "instance",
        lambda row: _instance_text(row["kind_name"] or "", row["name"] or "", row["description"] or ""),
    )
    report.instances_indexed = i
    report.errors.extend(errs)

    return report
