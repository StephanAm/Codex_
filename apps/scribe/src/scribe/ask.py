# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Ask pipeline: prompt assembly and LLM call for question answering."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scribe.cartographer import SearchChunk
    from scribe.llm.base import LLMBackend

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a knowledgeable assistant answering questions from a personal knowledge base.

You will be given a question and a set of context chunks retrieved from the user's notes, \
atlas pages, and definitions. Use only the provided context to answer. If the context does \
not contain enough information to answer confidently, say so clearly rather than guessing.

Rules:
- Answer directly and concisely
- Cite the source type (note, atlas page, definition) when it adds clarity
- Do not invent details not present in the context
- If the context is silent on the question, say "I could not find relevant information in your notes."
"""


def _build_user_message(question: str, chunks: list[SearchChunk]) -> str:
    lines: list[str] = []

    lines.append(f"Question: {question}")
    lines.append("")

    if chunks:
        lines.append("## Context")
        for chunk in chunks:
            type_label = chunk.corpus_type.replace("_", " ")
            header = f"[{type_label}]"
            if chunk.title:
                header += f" {chunk.title}"
            if chunk.time_stamp:
                header += f"  ({chunk.time_stamp[:10]})"
            lines.append(f"(score {chunk.score:.3f}) {header}")
            if chunk.content:
                lines.append(chunk.content.strip())
            lines.append("")
    else:
        lines.append("## Context")
        lines.append("(no relevant context found)")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_ask(question: str, chunks: list[SearchChunk], backend: LLMBackend) -> str:
    """Answer a question using the retrieved context chunks."""
    user_msg = _build_user_message(question, chunks)
    return backend.generate(SYSTEM_PROMPT, user_msg).strip()
