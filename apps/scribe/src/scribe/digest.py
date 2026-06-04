# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Digest pipeline: structured activity summary for reporting."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scribe.cartographer import Chunk
    from scribe.llm.base import LLMBackend
    from scribe.store import NoteRecord

SYSTEM_PROMPT = """\
You are a skilled writer producing an activity digest for reporting purposes.

You will be given a set of notes covering a time period. Produce a structured summary of what \
happened, what was decided, and what is outstanding. The output should be suitable for sharing \
with a manager or stakeholder.

Rules:
- Group activity by natural themes, projects, or topics that emerge from the notes
- For each group: a short heading, then a concise summary paragraph
- Highlight decisions made and their rationale where mentioned
- Call out outstanding items or blockers in a final section
- Write in clear, professional prose
- Do not invent content; only report what the notes contain
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

    period = from_date if from_date == to_date else f"{from_date} to {to_date}"
    lines.append(f"Period: {period}")
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


def run_digest(
    notes: list[NoteRecord],
    chunks: list[Chunk],
    title: str,
    from_date: str,
    to_date: str,
    tag: str | None,
    ref: str | None,
    backend: LLMBackend,
) -> str:
    """Generate a digest markdown string via the LLM."""
    user_msg = _build_user_message(notes, chunks, from_date, to_date, tag, ref)
    llm_output = backend.generate(SYSTEM_PROMPT, user_msg)

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    period = from_date if from_date == to_date else f"{from_date} – {to_date}"

    scope_parts: list[str] = []
    if tag:
        scope_parts.append(f"#{tag}")
    if ref:
        scope_parts.append(f"@{ref}")

    meta_lines = [
        f"# {title}",
        "",
        f"*Generated: {generated}*  ",
        f"*Period: {period}*  ",
    ]
    if scope_parts:
        meta_lines.append("*Scope: " + ", ".join(scope_parts) + "*  ")
    meta_lines.append(f"*Notes: {len(notes)}*")
    meta_lines += ["", "---", ""]

    return "\n".join(meta_lines) + llm_output.strip() + "\n"
