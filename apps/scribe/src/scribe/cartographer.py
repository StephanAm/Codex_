# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Subprocess wrappers for `carto retrieve` and `carto search`."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    note_id: int | None
    text: str
    score: float


@dataclass
class SearchChunk:
    corpus_type: str
    content: str
    score: float
    title: str
    tags: list[str]
    references: list[str]
    time_stamp: str | None


def retrieve_chunks(note_ids: list[int], top_k: int, bin_path: str) -> list[Chunk]:
    """Call `carto retrieve` and return parsed chunks.

    Returns an empty list immediately if note_ids is empty.
    Raises RuntimeError on non-zero exit or unparseable output.
    """
    if not note_ids:
        return []

    ids_csv = ",".join(str(i) for i in note_ids)
    cmd = [bin_path, "retrieve", "--note-ids", ids_csv, "--top-k", str(top_k)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(f"Cartographer binary not found: {bin_path!r}. Set CARTOGRAPHER_BIN to the correct path.")

    if result.returncode != 0:
        detail = result.stderr.strip() or "(no stderr)"
        raise RuntimeError(f"`carto retrieve` failed (exit {result.returncode}): {detail}")

    try:
        data = json.loads(result.stdout)
        return [
            Chunk(
                chunk_id=c["chunk_id"],
                note_id=c.get("note_id"),
                text=c.get("text", ""),
                score=float(c.get("score", 0.0)),
            )
            for c in data.get("chunks", [])
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Failed to parse `carto retrieve` output: {exc}") from exc


def search_query(query: str, top_k: int, bin_path: str) -> list[SearchChunk]:
    """Call `carto search --json` and return parsed context chunks.

    Raises RuntimeError on non-zero exit or unparseable output.
    """
    cmd = [bin_path, "search", "--json", "--top-k", str(top_k), query]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(f"Cartographer binary not found: {bin_path!r}. Set CARTOGRAPHER_BIN to the correct path.")

    if result.returncode != 0:
        detail = result.stderr.strip() or "(no stderr)"
        raise RuntimeError(f"`carto search` failed (exit {result.returncode}): {detail}")

    try:
        data = json.loads(result.stdout)
        return [
            SearchChunk(
                corpus_type=c.get("corpus_type", ""),
                content=c.get("content", ""),
                score=float(c.get("score", 0.0)),
                title=c.get("title", ""),
                tags=c.get("tags", []),
                references=c.get("references", []),
                time_stamp=c.get("time_stamp"),
            )
            for c in data.get("chunks", [])
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Failed to parse `carto search` output: {exc}") from exc
