# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Brief pipeline: prompt assembly and LLM call for reference briefings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scribe.cartographer import Chunk
    from scribe.llm.base import LLMBackend
    from scribe.store import NoteRecord

SYSTEM_PROMPT = """\
You are a research assistant preparing a briefing document on a specific person, team, or project.

You will be given all notes that mention the subject, plus retrieved context for additional depth. \
Synthesise these into a coherent narrative that gives the reader a complete picture before a \
meeting or conversation.

Rules:
- Write in flowing prose, not bullet lists
- Structure the narrative naturally: who or what this is, recent activity, key themes, anything outstanding
- Draw on context chunks for definition and background where available
- Be specific — cite dates and concrete details from the notes
- Do not invent details not present in the source material
- If there is little material, be honest about the limited history
"""


def _build_user_message(
    reference: str,
    notes: list[NoteRecord],
    chunks: list[Chunk],
    from_date: str | None,
    to_date: str | None,
) -> str:
    lines: list[str] = []

    lines.append(f"Subject: @{reference}")
    if from_date or to_date:
        lines.append(f"Date window: {from_date or '?'} to {to_date or '?'}")
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


def run_brief(
    reference: str,
    notes: list[NoteRecord],
    chunks: list[Chunk],
    title: str,
    from_date: str | None,
    to_date: str | None,
    backend: LLMBackend,
) -> str:
    """Generate a briefing markdown string via the LLM."""
    user_msg = _build_user_message(reference, notes, chunks, from_date, to_date)
    llm_output = backend.generate(SYSTEM_PROMPT, user_msg)

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    meta_lines = [
        f"# {title}",
        "",
        f"*Generated: {generated}*  ",
        f"*Subject: @{reference}*  ",
    ]
    if from_date or to_date:
        meta_lines.append(f"*Period: {from_date or '?'} to {to_date or '?'}*  ")
    meta_lines.append(f"*Notes: {len(notes)}*")
    meta_lines += ["", "---", ""]

    return "\n".join(meta_lines) + llm_output.strip() + "\n"
