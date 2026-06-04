# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Open-items pipeline: extract commitments and follow-ups from notes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scribe.cartographer import Chunk
    from scribe.llm.base import LLMBackend
    from scribe.store import NoteRecord

SYSTEM_PROMPT = """\
You are a meticulous assistant extracting open commitments and unresolved items from a set of notes.

Your output must be a numbered list of distinct action items, follow-ups, and open questions. \
Focus on items that are still pending — not things already resolved or completed.

Rules:
- Number each item
- Each item is one commitment, follow-up, or open question
- Include who owns it or who raised it if the notes make that clear
- Include relevant dates or deadlines where mentioned
- Order by urgency or recency where possible
- If context chunks clarify the status of an item, use that information
- Output numbered items only — no headings, no preamble, no closing remarks
"""


def _build_user_message(
    notes: list[NoteRecord],
    chunks: list[Chunk],
    from_date: str,
    to_date: str,
) -> str:
    lines: list[str] = []

    period = from_date if from_date == to_date else f"{from_date} to {to_date}"
    lines.append(f"Period: {period}")
    lines.append(f"Notes: {len(notes)}")
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


def run_open_items(
    notes: list[NoteRecord],
    chunks: list[Chunk],
    title: str,
    from_date: str,
    to_date: str,
    backend: LLMBackend,
) -> str:
    """Generate an open-items markdown string via the LLM."""
    user_msg = _build_user_message(notes, chunks, from_date, to_date)
    llm_output = backend.generate(SYSTEM_PROMPT, user_msg)

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    period = from_date if from_date == to_date else f"{from_date} – {to_date}"

    header = f"# {title}\n\n*Generated: {generated}*  \n*Period: {period}*  \n*Notes: {len(notes)}*\n\n---\n\n"
    return header + llm_output.strip() + "\n"
