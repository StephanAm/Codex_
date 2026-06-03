"""
Cartographer retrieval pipeline.

Multi-corpus scored search: query parsing, per-corpus vector retrieval,
temporal decay, reference/tag boosts, and result assembly.
"""

from __future__ import annotations

import math
import re
import sqlite3
import struct
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cartographer.db import connect

if TYPE_CHECKING:
    from cartographer.embeddings.base import EmbeddingBackend

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUDGET_NOTES = 5
BUDGET_ATLAS = 5
BUDGET_DEFINITIONS = 2
MAX_RESULTS = 15
MIN_SIMILARITY = 0.65

DECAY_HALF_LIFE_DAYS = 90.0
REFERENCE_BOOST_HARD = 1.5
REFERENCE_BOOST_SOFT = 1.2
TAG_BOOST = 1.2

_CORPUS_NOTES = "note"
_CORPUS_ATLAS = "atlas_page"
_CORPUS_DEFS = frozenset({"instance_kind", "instance"})

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DateWindow:
    from_date: str  # ISO date string (inclusive)
    to_date: str  # ISO date string (exclusive upper bound)


@dataclass
class ParsedQuery:
    references_hard: list[str]  # explicit @mentions matched to known references
    references_soft: list[str]  # names inferred from query words
    tags: list[str]  # explicit #tags + inferred from query words
    date_window: DateWindow | None
    semantic_query: str


@dataclass
class ContextChunk:
    corpus_type: str
    content: str
    score: float
    title: str
    tags: list[str]
    references: list[str]
    time_stamp: str | None


@dataclass
class LLMContext:
    query: str
    semantic_query: str
    references: list[str]
    tags: list[str]
    date_window: DateWindow | None
    chunks: list[ContextChunk]


# ---------------------------------------------------------------------------
# Date window extraction
# ---------------------------------------------------------------------------

_DATE_REGEX_TABLE: list[tuple[str, str]] = [
    (r"\btoday\b", "today"),
    (r"\byesterday\b", "yesterday"),
    (r"\blast\s+(\d+)\s+days?\b", "last_n_days"),
    (r"\blast\s+(\d+)\s+weeks?\b", "last_n_weeks"),
    (r"\blast\s+(\d+)\s+months?\b", "last_n_months"),
    (r"\bthis\s+week\b", "this_week"),
    (r"\blast\s+week\b", "last_week"),
    (r"\bthis\s+month\b", "this_month"),
    (r"\blast\s+month\b", "last_month"),
    (r"\bthis\s+year\b", "this_year"),
    (r"\blast\s+year\b", "last_year"),
]

_STRIP_DATE_REGEXES = [pattern for pattern, _ in _DATE_REGEX_TABLE]


def _extract_date_window(query: str) -> DateWindow | None:
    today = datetime.now(UTC).date()

    for pattern, kind in _DATE_REGEX_TABLE:
        m = re.search(pattern, query, re.IGNORECASE)
        if not m:
            continue

        if kind == "today":
            from_d, to_d = today, today + timedelta(days=1)
        elif kind == "yesterday":
            from_d, to_d = today - timedelta(days=1), today
        elif kind == "last_n_days":
            n = int(m.group(1))
            from_d, to_d = today - timedelta(days=n), today + timedelta(days=1)
        elif kind == "last_n_weeks":
            n = int(m.group(1))
            from_d, to_d = today - timedelta(weeks=n), today + timedelta(days=1)
        elif kind == "last_n_months":
            n = int(m.group(1))
            from_d, to_d = today - timedelta(days=n * 30), today + timedelta(days=1)
        elif kind in ("last_week", "this_week"):
            from_d, to_d = today - timedelta(days=7), today + timedelta(days=1)
        elif kind in ("last_month", "this_month"):
            from_d, to_d = today - timedelta(days=30), today + timedelta(days=1)
        elif kind in ("last_year", "this_year"):
            from_d, to_d = today - timedelta(days=365), today + timedelta(days=1)
        else:
            continue

        return DateWindow(from_date=from_d.isoformat(), to_date=to_d.isoformat())

    return None


def _strip_structured_signals(raw_query: str, date_window: DateWindow | None) -> str:
    # Strip the @ sigil but keep the word — references are boosted separately,
    # but the name itself still carries semantic meaning.
    s = re.sub(r"@(\w+)", r"\1", raw_query)
    s = re.sub(r"#\w+", "", s)
    if date_window is not None:
        for pattern in _STRIP_DATE_REGEXES:
            s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# Step 1 — Parse Query
# ---------------------------------------------------------------------------


def parse_query(raw_query: str, conn: sqlite3.Connection) -> ParsedQuery:
    known_refs: set[str] = {row[0].lower() for row in conn.execute('SELECT name FROM "references"')}
    known_tags: set[str] = {row[0].lower() for row in conn.execute("SELECT name FROM tags")}

    hard_ref_raw = re.findall(r"@(\w+)", raw_query, re.IGNORECASE)
    references_hard = [r.lower() for r in hard_ref_raw if r.lower() in known_refs]

    hard_tag_raw = re.findall(r"#(\w+)", raw_query, re.IGNORECASE)
    tags_explicit = [t.lower() for t in hard_tag_raw if t.lower() in known_tags]

    # Soft inference: query words (after removing structured tokens) vs known names
    bare = re.sub(r"[@#]\w+", "", raw_query)
    words = set(re.findall(r"\b[a-zA-Z]\w*\b", bare.lower()))
    references_soft = [r for r in known_refs if r in words and r not in references_hard]
    tags_soft = [t for t in known_tags if t in words and t not in tags_explicit]

    date_window = _extract_date_window(raw_query)
    semantic_query = _strip_structured_signals(raw_query, date_window)

    return ParsedQuery(
        references_hard=references_hard,
        references_soft=references_soft,
        tags=tags_explicit + tags_soft,
        date_window=date_window,
        semantic_query=semantic_query or raw_query,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cosine(query_vec: list[float], norm_q: float, blob: bytes, n_dims: int) -> float:
    b = struct.unpack(f"{n_dims}f", blob)
    dot = float(sum(x * y for x, y in zip(query_vec, b)))
    norm_b = math.sqrt(float(sum(x * x for x in b)))
    if norm_q == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_q * norm_b)


def _split_csv(s: str | None) -> list[str]:
    if not s:
        return []
    return [x.strip().lower() for x in s.split(",") if x.strip()]


# ---------------------------------------------------------------------------
# Step 3 — Retrieve Candidates Per Corpus
# ---------------------------------------------------------------------------


def _retrieve_notes(
    conn: sqlite3.Connection,
    model: str,
    query_vec: list[float],
    norm_q: float,
    n_dims: int,
    parsed: ParsedQuery,
) -> list[dict[str, Any]]:
    params: list[Any] = [model, n_dims * 4]
    where_extra = ""

    if parsed.date_window:
        where_extra += " AND COALESCE(n.time_stamp, n.created_at) >= ? AND COALESCE(n.time_stamp, n.created_at) < ?"
        params.extend([parsed.date_window.from_date, parsed.date_window.to_date])

    if parsed.references_hard:
        placeholders = ",".join("?" * len(parsed.references_hard))
        where_extra += (
            f" AND n.id IN ("
            f"SELECT nr.note_id FROM note_references nr"
            f' JOIN "references" r ON r.id = nr.reference_id'
            f" WHERE LOWER(r.name) IN ({placeholders}))"
        )
        params.extend(parsed.references_hard)

    rows = conn.execute(
        f"""
        SELECT e.source_uuid, e.vector, n.time_stamp, n.created_at, n.body,
               (SELECT GROUP_CONCAT(t.name, ',')
                FROM note_tags nt JOIN tags t ON t.id = nt.tag_id
                WHERE nt.note_id = n.id) AS tag_names,
               (SELECT GROUP_CONCAT(r.name, ',')
                FROM note_references nr JOIN "references" r ON r.id = nr.reference_id
                WHERE nr.note_id = n.id) AS ref_names
        FROM embeddings e
        JOIN notes n ON n.uuid = e.source_uuid
        WHERE e.model = ? AND e.chunk_index = 0 AND e.source_type = 'note'
          AND LENGTH(e.vector) = ?{where_extra}
        """,
        params,
    ).fetchall()

    scored: list[dict[str, Any]] = []
    for row in rows:
        sim = _cosine(query_vec, norm_q, row["vector"], n_dims)
        body = (row["body"] or "").strip()
        lines = body.split("\n", 1)
        title = lines[0][:80]
        scored.append(
            {
                "uuid": row["source_uuid"],
                "corpus": _CORPUS_NOTES,
                "similarity": sim,
                "time_stamp": row["time_stamp"],
                "created_at": row["created_at"],
                "tags": _split_csv(row["tag_names"]),
                "references": _split_csv(row["ref_names"]),
                "body": body,
                "title": title,
            }
        )

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:BUDGET_NOTES]


def _build_ancestor_annotations(conn: sqlite3.Connection) -> dict[int, dict[str, list[str]]]:
    """Return {page_id: {"tags": [...], "refs": [...]}} with inherited ancestors merged in."""
    # Build node → parent map and node → page map
    node_parent: dict[int, int | None] = {
        row["id"]: row["parent_id"] for row in conn.execute("SELECT id, parent_id FROM atlas_nodes").fetchall()
    }
    node_to_page: dict[int, int] = {
        row["node_id"]: row["id"] for row in conn.execute("SELECT id, node_id FROM atlas_pages").fetchall()
    }

    # Load per-page annotations
    page_tags: dict[int, list[str]] = {}
    for row in conn.execute("SELECT apt.page_id, t.name FROM atlas_page_tags apt JOIN tags t ON t.id = apt.tag_id"):
        page_tags.setdefault(row["page_id"], []).append(row["name"])

    page_refs: dict[int, list[str]] = {}
    for row in conn.execute(
        'SELECT apr.page_id, r.name FROM atlas_page_references apr JOIN "references" r ON r.id = apr.reference_id'
    ):
        page_refs.setdefault(row["page_id"], []).append(row["name"])

    result: dict[int, dict[str, list[str]]] = {}
    for node_id, page_id in node_to_page.items():
        tags: list[str] = []
        refs: list[str] = []
        seen_tags: set[str] = set()
        seen_refs: set[str] = set()

        # Walk from this node up to the root, collecting annotations
        current: int | None = node_id
        while current is not None:
            pid = node_to_page.get(current)
            if pid is not None:
                for t in page_tags.get(pid, []):
                    if t not in seen_tags:
                        tags.append(t)
                        seen_tags.add(t)
                for r in page_refs.get(pid, []):
                    if r not in seen_refs:
                        refs.append(r)
                        seen_refs.add(r)
            current = node_parent.get(current)

        result[page_id] = {"tags": tags, "refs": refs}

    return result


def _retrieve_atlas(
    conn: sqlite3.Connection,
    model: str,
    query_vec: list[float],
    norm_q: float,
    n_dims: int,
    ancestor_annotations: dict[int, dict[str, list[str]]],
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT e.source_uuid, e.vector, ap.id, ap.title, ap.body
        FROM embeddings e
        JOIN atlas_pages ap ON ap.uuid = e.source_uuid
        WHERE e.model = ? AND e.chunk_index = 0 AND e.source_type = 'atlas_page'
          AND LENGTH(e.vector) = ?
        """,
        [model, n_dims * 4],
    ).fetchall()

    scored: list[dict[str, Any]] = []
    for row in rows:
        sim = _cosine(query_vec, norm_q, row["vector"], n_dims)
        ann = ancestor_annotations.get(row["id"], {"tags": [], "refs": []})
        scored.append(
            {
                "uuid": row["source_uuid"],
                "corpus": _CORPUS_ATLAS,
                "similarity": sim,
                "time_stamp": None,
                "created_at": None,
                "tags": ann["tags"],
                "references": ann["refs"],
                "body": (row["body"] or "").strip(),
                "title": row["title"] or "",
            }
        )

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:BUDGET_ATLAS]


def _retrieve_definitions(
    conn: sqlite3.Connection,
    model: str,
    query_vec: list[float],
    norm_q: float,
    n_dims: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT e.source_uuid, e.source_type, e.vector,
               CASE e.source_type
                   WHEN 'instance_kind' THEN ik.name
                   WHEN 'instance'      THEN i.name
               END AS item_name,
               CASE e.source_type
                   WHEN 'instance_kind' THEN ik.description
                   WHEN 'instance'      THEN i.description
               END AS item_description
        FROM embeddings e
        LEFT JOIN instance_kinds ik
               ON ik.uuid = e.source_uuid AND e.source_type = 'instance_kind'
        LEFT JOIN instances i
               ON i.uuid = e.source_uuid AND e.source_type = 'instance'
        WHERE e.model = ? AND e.chunk_index = 0
          AND e.source_type IN ('instance_kind', 'instance')
          AND LENGTH(e.vector) = ?
        """,
        [model, n_dims * 4],
    ).fetchall()

    scored: list[dict[str, Any]] = []
    for row in rows:
        sim = _cosine(query_vec, norm_q, row["vector"], n_dims)
        scored.append(
            {
                "uuid": row["source_uuid"],
                "corpus": row["source_type"],
                "similarity": sim,
                "time_stamp": None,
                "created_at": None,
                "tags": [],
                "references": [],
                "body": (row["item_description"] or "").strip(),
                "title": row["item_name"] or "",
            }
        )

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:BUDGET_DEFINITIONS]


# ---------------------------------------------------------------------------
# Step 4 — Score Candidates
# ---------------------------------------------------------------------------


def _score(c: dict[str, Any], parsed: ParsedQuery, now: datetime) -> float:
    base = c["similarity"]

    if c["corpus"] == _CORPUS_NOTES:
        anchor_str = c["time_stamp"] or c["created_at"]
        if anchor_str:
            try:
                anchor = datetime.fromisoformat(anchor_str)
                if anchor.tzinfo is None:
                    anchor = anchor.replace(tzinfo=UTC)
                age_days = max(0.0, (now - anchor).total_seconds() / 86400.0)
                decay = math.exp(-math.log(2) * age_days / DECAY_HALF_LIFE_DAYS)
            except ValueError:
                decay = 1.0
        else:
            decay = 1.0
    else:
        decay = 1.0

    c_refs = set(c["references"])
    if c_refs & set(parsed.references_hard):
        ref_boost = REFERENCE_BOOST_HARD
    elif c_refs & set(parsed.references_soft):
        ref_boost = REFERENCE_BOOST_SOFT
    else:
        ref_boost = 1.0

    tag_boost = TAG_BOOST if (set(c["tags"]) & set(parsed.tags)) else 1.0

    return float(base * decay * ref_boost * tag_boost)


# ---------------------------------------------------------------------------
# Step 5 — Filter, Re-rank, Assemble
# ---------------------------------------------------------------------------


def _assemble(candidates: list[dict[str, Any]], parsed: ParsedQuery, now: datetime) -> list[dict[str, Any]]:
    for c in candidates:
        c["final_score"] = _score(c, parsed, now)

    candidates = [c for c in candidates if c["final_score"] >= MIN_SIMILARITY]
    candidates.sort(key=lambda x: x["final_score"], reverse=True)

    # Guarantee at least one representative per corpus
    results: list[dict[str, Any]] = []
    remaining = list(candidates)
    for corpus in [_CORPUS_NOTES, _CORPUS_ATLAS, *sorted(_CORPUS_DEFS)]:
        top = next((c for c in remaining if c["corpus"] == corpus), None)
        if top is not None:
            results.append(top)
            remaining.remove(top)

    results.extend(remaining[: MAX_RESULTS - len(results)])
    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Step 6 — Build LLM Context
# ---------------------------------------------------------------------------


def _build_context(results: list[dict[str, Any]], parsed: ParsedQuery, raw_query: str) -> LLMContext:
    chunks = [
        ContextChunk(
            corpus_type=c["corpus"],
            content=c["body"],
            score=c["final_score"],
            title=c["title"],
            tags=c["tags"],
            references=c["references"],
            time_stamp=c["time_stamp"],
        )
        for c in results
    ]

    all_refs = list(dict.fromkeys(parsed.references_hard + parsed.references_soft))

    return LLMContext(
        query=raw_query,
        semantic_query=parsed.semantic_query,
        references=all_refs,
        tags=parsed.tags,
        date_window=parsed.date_window,
        chunks=chunks,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def search(
    query: str,
    backend: EmbeddingBackend,
    db_path: Path | None = None,
) -> LLMContext:
    conn = connect(db_path)
    now = datetime.now(UTC)

    parsed = parse_query(query, conn)

    query_vec = backend.embed([parsed.semantic_query])[0]
    n_dims = len(query_vec)
    norm_q = math.sqrt(sum(x * x for x in query_vec))

    ancestor_annotations = _build_ancestor_annotations(conn)

    candidates = (
        _retrieve_notes(conn, backend.model_name, query_vec, norm_q, n_dims, parsed)
        + _retrieve_atlas(conn, backend.model_name, query_vec, norm_q, n_dims, ancestor_annotations)
        + _retrieve_definitions(conn, backend.model_name, query_vec, norm_q, n_dims)
    )

    results = _assemble(candidates, parsed, now)
    return _build_context(results, parsed, query)
