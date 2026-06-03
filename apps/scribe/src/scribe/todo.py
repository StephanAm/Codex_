"""Todo pipeline: prompt assembly, LLM call, markdown rendering."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scribe.cartographer import Chunk
    from scribe.llm.base import LLMBackend
    from scribe.store import NoteRecord

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an assistant that extracts to-do items from a set of tagged notes.

Your output must be a plain numbered list of action items. Each item is one specific, \
actionable task extracted from the notes. Draw on the provided context chunks for \
additional clarity where relevant.

Rules:
- Output numbered items only — no headings, no sections, no preamble, no closing remarks
- Each item is one distinct, actionable task
- Deduplicate: if the same task appears in multiple notes, list it once
- Use imperative language (e.g. "Set up X", "Review Y", "Fix Z")
- Order by apparent priority or urgency if discernible; otherwise maintain note order
- If context chunks clarify a task, use that detail; do not add unrelated items
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


def run_todo(
    notes: list[NoteRecord],
    chunks: list[Chunk],
    title: str,
    from_date: str,
    to_date: str,
    backend: LLMBackend,
) -> str:
    """Generate a to-do list markdown string via the LLM."""
    user_msg = _build_user_message(notes, chunks, from_date, to_date)
    llm_output = backend.generate(SYSTEM_PROMPT, user_msg)

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    period = from_date if from_date == to_date else f"{from_date} – {to_date}"

    header = f"# {title}\n\n*Generated: {generated}*  \n*Period: {period}*  \n*Notes: {len(notes)}*\n\n---\n\n"

    return header + llm_output.strip() + "\n"
