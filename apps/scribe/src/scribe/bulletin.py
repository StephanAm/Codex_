# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Bulletin pipeline: prompt assembly, LLM call, markdown rendering."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import frontmatter as fm_lib

if TYPE_CHECKING:
    from scribe.cartographer import Chunk
    from scribe.llm.base import LLMBackend
    from scribe.store import NoteRecord

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a technical writer producing a concise daily bulletin from a set of notes.

Your output must be an ordered, deduplicated bullet list. Each bullet captures one distinct \
idea, event, or decision from the notes. Draw on the provided context chunks for additional \
depth where relevant.

Rules:
- Output bullets only — no headings, no sections, no preamble, no closing remarks
- Each bullet is one idea; do not repeat the same information across bullets
- Order bullets so the most significant or actionable items come first
- Use clear, direct language; avoid padding
- If context chunks add meaningful detail not in the notes, weave it in concisely
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


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_bulletin(
    notes: list[NoteRecord],
    chunks: list[Chunk],
    title: str,
    from_date: str,
    to_date: str,
    backend: LLMBackend,
    *,
    frontmatter: bool = True,
) -> str:
    """Generate a bulletin markdown string via the LLM."""
    user_msg = _build_user_message(notes, chunks, from_date, to_date)
    llm_output = backend.generate(SYSTEM_PROMPT, user_msg)

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    period = from_date if from_date == to_date else f"{from_date} – {to_date}"

    fm = ""
    if frontmatter:
        all_tags = ["#daily-bulletin"] + sorted({f"#{t}" for note in notes for t in note.tags})
        all_refs = sorted({f"@{r}" for note in notes for r in note.references})
        meta: dict[str, object] = {"date": to_date, "tags": all_tags}
        if all_refs:
            meta["refs"] = all_refs
        post = fm_lib.Post("")
        post.metadata.update(meta)
        fm = fm_lib.dumps(post) + "\n\n"

    header = f"# {title}\n\n*Generated: {generated}*  \n*Period: {period}*  \n*Notes: {len(notes)}*\n\n---\n\n"

    return fm + header + llm_output.strip() + "\n"
