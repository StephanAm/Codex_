# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Patterns pipeline: recurring theme analysis over a note corpus."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scribe.cartographer import Chunk
    from scribe.llm.base import LLMBackend
    from scribe.store import NoteRecord

SYSTEM_PROMPT = """\
You are an analyst identifying recurring patterns in a personal note corpus.

You will be given a set of notes covering a defined time period. Surface recurring themes, \
persistent blockers, sentiment shifts, and emerging concerns. Each pattern should be named, \
described, and grounded in evidence from the notes.

Rules:
- Name each pattern clearly — one short descriptive phrase as a heading
- Describe each pattern in 2–4 sentences with specific evidence: dates, quotes, people
- Distinguish structural or recurring themes from one-off events
- Note directional shifts: something getting better or worse over the period
- Only surface patterns with at least two supporting data points
- Do not invent patterns not supported by the material
"""


def _build_user_message(
    notes: list[NoteRecord],
    chunks: list[Chunk],
    from_date: str,
    to_date: str,
    tag: str | None,
    ref: str | None,
) -> str:
    lines: list[str] = []

    lines.append(f"Period: {from_date} to {to_date}")
    lines.append(f"Notes: {len(notes)}")
    scope_parts: list[str] = []
    if tag:
        scope_parts.append(f"#{tag}")
    if ref:
        scope_parts.append(f"@{ref}")
    if scope_parts:
        lines.append("Scope: " + ", ".join(scope_parts))
    lines.append("")

    lines.append("## Notes")
    for note in notes:
        ts = note.time_stamp[:10] if note.time_stamp else "?"
        lines.append(f"[{ts}] {note.body.strip()}")
        meta: list[str] = []
        if note.tags:
            meta.append("tags: " + ", ".join(f"#{t}" for t in note.tags))
        if note.references:
            meta.append("refs: " + ", ".join(f"@{r}" for r in note.references))
        if meta:
            lines.append("  " + " | ".join(meta))
    lines.append("")

    if chunks:
        lines.append("## Context")
        for chunk in chunks:
            lines.append(f"(score {chunk.score:.3f}) {chunk.text.strip()}")
        lines.append("")

    return "\n".join(lines)


def run_patterns(
    notes: list[NoteRecord],
    chunks: list[Chunk],
    title: str,
    from_date: str,
    to_date: str,
    tag: str | None,
    ref: str | None,
    backend: LLMBackend,
) -> str:
    """Generate a patterns analysis markdown string via the LLM."""
    user_msg = _build_user_message(notes, chunks, from_date, to_date, tag, ref)
    llm_output = backend.generate(SYSTEM_PROMPT, user_msg)

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    scope_parts: list[str] = []
    if tag:
        scope_parts.append(f"#{tag}")
    if ref:
        scope_parts.append(f"@{ref}")

    meta_lines = [
        f"# {title}",
        "",
        f"*Generated: {generated}*  ",
        f"*Period: {from_date} to {to_date}*  ",
    ]
    if scope_parts:
        meta_lines.append("*Scope: " + ", ".join(scope_parts) + "*  ")
    meta_lines.append(f"*Notes: {len(notes)}*")
    meta_lines += ["", "---", ""]

    return "\n".join(meta_lines) + llm_output.strip() + "\n"
