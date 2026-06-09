# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import click

from scribe import __version__

_PERIOD_CHOICES = click.Choice(
    ["today", "yesterday", "this-week", "this-month", "last-week", "last-month"],
    case_sensitive=False,
)


@click.group()
@click.version_option(__version__, prog_name="scribe")
def main() -> None:
    """Scribe — context-aware LLM integration for the Codex workspace."""


# ---------------------------------------------------------------------------
# bulletin
# ---------------------------------------------------------------------------


@main.command()
@click.option("--date", "date_str", default=None, metavar="YYYY-MM-DD", help="Single day (default: today).")
@click.option("--from", "from_str", default=None, metavar="YYYY-MM-DD", help="Start of date range (inclusive).")
@click.option("--to", "to_str", default=None, metavar="YYYY-MM-DD", help="End of date range (inclusive).")
@click.option(
    "--period",
    default=None,
    type=_PERIOD_CHOICES,
    help="Named period: today, yesterday, this-week, this-month, last-week, last-month.",
)
@click.option("--title", default=None, help="Report title. Default: 'Bulletin — {date}'.")
@click.option("--output", "output_str", default=None, metavar="PATH", help="Output file. Default: ./bulletin-{date}.md")
@click.option("--top-k", "top_k", default=None, type=int, help="Chunks to retrieve (overrides SCRIBE_TOP_K).")
@click.option("--backend", "backend_name", default=None, help="LLM backend: ollama, dummy. Overrides SCRIBE_BACKEND.")
@click.option("--dry-run", is_flag=True, help="Print fetched notes, skip Cartographer and LLM.")
@click.option("--frontmatter/--no-frontmatter", default=True, help="Prepend YAML frontmatter (default: on).")
def bulletin(
    date_str: str | None,
    from_str: str | None,
    to_str: str | None,
    period: str | None,
    title: str | None,
    output_str: str | None,
    top_k: int | None,
    backend_name: str,
    dry_run: bool,
    frontmatter: bool,
) -> None:
    """Generate a bulletin from notes in the given date range.

    Reads notes from the Cartographer DB, retrieves semantic context,
    and asks the LLM to produce an ordered, deduplicated bullet list.
    """
    from scribe.config import (
        get_archive_dir,
        get_cartographer_bin,
        get_cartographer_db,
        get_claude_bin,
        get_ollama_url,
        get_scribe_backend,
        get_scribe_model,
        get_scribe_top_k,
    )

    # ── 1. Resolve date range ────────────────────────────────────────────────
    if date_str and (from_str or to_str):
        raise click.UsageError("--date is mutually exclusive with --from/--to.")
    if period and (date_str or from_str or to_str):
        raise click.UsageError("--period is mutually exclusive with --date/--from/--to.")

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    if period:
        from_date, to_date = _resolve_period(period)
    elif date_str:
        from_date = to_date = date_str
    elif from_str or to_str:
        from_date = from_str or today
        to_date = to_str or today
    else:
        from_date = to_date = today

    _validate_date(from_date, "--date/--from")
    _validate_date(to_date, "--to")

    label = from_date if from_date == to_date else f"{from_date}_{to_date}"
    resolved_title = title or f"Bulletin — {label}"
    if output_str:
        output_path = Path(output_str)
    elif archive_dir := get_archive_dir():
        output_path = archive_dir / "Daily Bulletins" / f"{to_date} Bulletin.md"
    else:
        output_path = Path(f"bulletin-{label}.md")

    # ── 2. Fetch notes from Cartographer DB ──────────────────────────────────
    from scribe.store import fetch_notes_in_range

    db_path = get_cartographer_db()
    try:
        notes = fetch_notes_in_range(from_date, to_date, db_path)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 3. No notes → clean exit ─────────────────────────────────────────────
    if not notes:
        period = from_date if from_date == to_date else f"{from_date} to {to_date}"
        click.echo(f"No notes found for {period}.", err=True)
        sys.exit(0)

    # ── 4. Dry-run ───────────────────────────────────────────────────────────
    if dry_run:
        period = from_date if from_date == to_date else f"{from_date} – {to_date}"
        click.echo(f"Period: {period}  Notes: {len(notes)}\n")
        for note in notes:
            ts = note.time_stamp[:10] if note.time_stamp else "?"
            click.echo(f"[{ts}] {note.body.strip()}")
        sys.exit(0)

    # ── 5. Check output path ─────────────────────────────────────────────────
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
    except OSError as exc:
        click.echo(f"Error: cannot write to {output_path}: {exc}", err=True)
        sys.exit(1)

    # ── 6. Retrieve context chunks ───────────────────────────────────────────
    from scribe.cartographer import retrieve_chunks

    effective_top_k = top_k if top_k is not None else get_scribe_top_k()
    note_ids = [n.id for n in notes]

    try:
        chunks = retrieve_chunks(note_ids, effective_top_k, get_cartographer_bin())
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 7. Build LLM backend ─────────────────────────────────────────────────
    from scribe.llm import build_backend

    resolved_backend = backend_name or get_scribe_backend()
    try:
        backend = build_backend(
            resolved_backend,
            get_scribe_model() or None,
            get_ollama_url(),
            get_claude_bin(),
        )
    except ValueError as exc:
        raise click.UsageError(str(exc))

    # ── 8. Generate bulletin ─────────────────────────────────────────────────
    from scribe.bulletin import run_bulletin

    try:
        markdown = run_bulletin(notes, chunks, resolved_title, from_date, to_date, backend, frontmatter=frontmatter)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 9. Write output ──────────────────────────────────────────────────────
    output_path.write_text(markdown, encoding="utf-8")
    click.echo(f"Written: {output_path}", err=True)


# ---------------------------------------------------------------------------
# todo
# ---------------------------------------------------------------------------


@main.command()
@click.option("--date", "date_str", default=None, metavar="YYYY-MM-DD", help="Single day (default: today).")
@click.option("--from", "from_str", default=None, metavar="YYYY-MM-DD", help="Start of date range (inclusive).")
@click.option("--to", "to_str", default=None, metavar="YYYY-MM-DD", help="End of date range (inclusive).")
@click.option(
    "--period",
    default=None,
    type=_PERIOD_CHOICES,
    help="Named period: today, yesterday, this-week, this-month, last-week, last-month.",
)
@click.option("--title", default=None, help="Report title. Default: 'To-Do — {date}'.")
@click.option("--output", "output_str", default=None, metavar="PATH", help="Output file. Default: ./todo-{date}.md")
@click.option("--top-k", "top_k", default=None, type=int, help="Chunks to retrieve (overrides SCRIBE_TOP_K).")
@click.option("--backend", "backend_name", default=None, help="LLM backend: ollama, dummy. Overrides SCRIBE_BACKEND.")
@click.option("--dry-run", is_flag=True, help="Print fetched notes, skip Cartographer and LLM.")
def todo(
    date_str: str | None,
    from_str: str | None,
    to_str: str | None,
    period: str | None,
    title: str | None,
    output_str: str | None,
    top_k: int | None,
    backend_name: str,
    dry_run: bool,
) -> None:
    """Generate a to-do list from #todo-tagged notes in the given date range.

    Reads notes tagged with #todo from the Cartographer DB, retrieves semantic
    context, and asks the LLM to produce a numbered list of action items.
    """
    from scribe.config import (
        get_cartographer_bin,
        get_cartographer_db,
        get_claude_bin,
        get_ollama_url,
        get_scribe_backend,
        get_scribe_model,
        get_scribe_top_k,
    )

    # ── 1. Resolve date range ────────────────────────────────────────────────
    if date_str and (from_str or to_str):
        raise click.UsageError("--date is mutually exclusive with --from/--to.")
    if period and (date_str or from_str or to_str):
        raise click.UsageError("--period is mutually exclusive with --date/--from/--to.")

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    if period:
        from_date, to_date = _resolve_period(period)
    elif date_str:
        from_date = to_date = date_str
    elif from_str or to_str:
        from_date = from_str or today
        to_date = to_str or today
    else:
        from_date = to_date = today

    _validate_date(from_date, "--date/--from")
    _validate_date(to_date, "--to")

    label = from_date if from_date == to_date else f"{from_date}_{to_date}"
    resolved_title = title or f"To-Do — {label}"
    output_path = Path(output_str) if output_str else Path(f"todo-{label}.md")

    # ── 2. Fetch #todo notes from Cartographer DB ────────────────────────────
    from scribe.store import fetch_notes_by_tag

    db_path = get_cartographer_db()
    try:
        notes = fetch_notes_by_tag("todo", from_date, to_date, db_path)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 3. No notes → clean exit ─────────────────────────────────────────────
    if not notes:
        period = from_date if from_date == to_date else f"{from_date} to {to_date}"
        click.echo(f"No #todo notes found for {period}.", err=True)
        sys.exit(0)

    # ── 4. Dry-run ───────────────────────────────────────────────────────────
    if dry_run:
        period = from_date if from_date == to_date else f"{from_date} – {to_date}"
        click.echo(f"Period: {period}  Notes: {len(notes)}\n")
        for note in notes:
            ts = note.time_stamp[:10] if note.time_stamp else "?"
            click.echo(f"[{ts}] {note.body.strip()}")
        sys.exit(0)

    # ── 5. Check output path ─────────────────────────────────────────────────
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
    except OSError as exc:
        click.echo(f"Error: cannot write to {output_path}: {exc}", err=True)
        sys.exit(1)

    # ── 6. Retrieve context chunks ───────────────────────────────────────────
    from scribe.cartographer import retrieve_chunks

    effective_top_k = top_k if top_k is not None else get_scribe_top_k()
    note_ids = [n.id for n in notes]

    try:
        chunks = retrieve_chunks(note_ids, effective_top_k, get_cartographer_bin())
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 7. Build LLM backend ─────────────────────────────────────────────────
    from scribe.llm import build_backend

    resolved_backend = backend_name or get_scribe_backend()
    try:
        backend = build_backend(
            resolved_backend,
            get_scribe_model() or None,
            get_ollama_url(),
            get_claude_bin(),
        )
    except ValueError as exc:
        raise click.UsageError(str(exc))

    # ── 8. Generate to-do list ───────────────────────────────────────────────
    from scribe.todo import run_todo

    try:
        markdown = run_todo(notes, chunks, resolved_title, from_date, to_date, backend)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 9. Write output ──────────────────────────────────────────────────────
    output_path.write_text(markdown, encoding="utf-8")
    click.echo(f"Written: {output_path}", err=True)


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------


@main.command()
@click.argument("question")
@click.option("--top-k", "top_k", default=None, type=int, help="Chunks to retrieve (overrides SCRIBE_TOP_K).")
@click.option("--backend", "backend_name", default=None, help="LLM backend: ollama, dummy. Overrides SCRIBE_BACKEND.")
@click.option("--output", "output_str", default=None, metavar="PATH", help="Output file. Default: stdout.")
@click.option("--dry-run", is_flag=True, help="Print retrieved context; skip LLM.")
def ask(
    question: str,
    top_k: int | None,
    backend_name: str | None,
    output_str: str | None,
    dry_run: bool,
) -> None:
    """Answer a question using semantically retrieved context from your notes.

    Calls `carto search` to find relevant context, then passes the question
    and context to the LLM to produce an answer.
    """
    # ── 1. Retrieve context chunks via carto search ──────────────────────────
    from scribe.cartographer import search_query
    from scribe.config import (
        get_cartographer_bin,
        get_claude_bin,
        get_ollama_url,
        get_scribe_backend,
        get_scribe_model,
        get_scribe_top_k,
    )

    effective_top_k = top_k if top_k is not None else get_scribe_top_k()

    try:
        chunks = search_query(question, effective_top_k, get_cartographer_bin())
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 2. Dry-run ───────────────────────────────────────────────────────────
    if dry_run:
        click.echo(f"Question: {question}\n")
        if chunks:
            click.echo(f"Context chunks: {len(chunks)}\n")
            for i, c in enumerate(chunks, 1):
                type_label = c.corpus_type.replace("_", " ")
                click.echo(f"{i:>2}. ({c.score:.3f}) [{type_label}] {c.title}")
                if c.content:
                    click.echo(f"     {c.content[:200].replace(chr(10), ' ')}")
        else:
            click.echo("No context chunks found.")
        sys.exit(0)

    # ── 3. Build LLM backend ─────────────────────────────────────────────────
    from scribe.llm import build_backend

    resolved_backend = backend_name or get_scribe_backend()
    try:
        backend = build_backend(
            resolved_backend,
            get_scribe_model() or None,
            get_ollama_url(),
            get_claude_bin(),
        )
    except ValueError as exc:
        raise click.UsageError(str(exc))

    # ── 4. Generate answer ───────────────────────────────────────────────────
    from scribe.ask import run_ask

    try:
        answer = run_ask(question, chunks, backend)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 5. Output ────────────────────────────────────────────────────────────
    if output_str:
        output_path = Path(output_str)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(answer + "\n", encoding="utf-8")
        except OSError as exc:
            click.echo(f"Error: cannot write to {output_path}: {exc}", err=True)
            sys.exit(1)
        click.echo(f"Written: {output_path}", err=True)
    else:
        click.echo(answer)


# ---------------------------------------------------------------------------
# brief
# ---------------------------------------------------------------------------


@main.command()
@click.argument("reference")
@click.option("--from", "from_str", default=None, metavar="YYYY-MM-DD", help="Start of date window (optional).")
@click.option("--to", "to_str", default=None, metavar="YYYY-MM-DD", help="End of date window (optional).")
@click.option(
    "--period",
    default=None,
    type=_PERIOD_CHOICES,
    help="Named period: today, yesterday, this-week, this-month, last-week, last-month.",
)
@click.option("--title", default=None, help="Report title. Default: 'Brief — @{reference}'.")
@click.option("--output", "output_str", default=None, metavar="PATH", help="Output file.")
@click.option("--top-k", "top_k", default=None, type=int, help="Chunks to retrieve (overrides SCRIBE_TOP_K).")
@click.option("--backend", "backend_name", default=None, help="LLM backend: ollama, dummy. Overrides SCRIBE_BACKEND.")
@click.option("--dry-run", is_flag=True, help="Print fetched notes, skip Cartographer and LLM.")
def brief(
    reference: str,
    from_str: str | None,
    to_str: str | None,
    period: str | None,
    title: str | None,
    output_str: str | None,
    top_k: int | None,
    backend_name: str | None,
    dry_run: bool,
) -> None:
    """Generate a briefing on a person, team, or project.

    Fetches all notes mentioning @REFERENCE, retrieves semantic context,
    and asks the LLM to produce a coherent narrative briefing.
    """
    from scribe.config import (
        get_cartographer_bin,
        get_cartographer_db,
        get_claude_bin,
        get_ollama_url,
        get_scribe_backend,
        get_scribe_model,
        get_scribe_top_k,
    )

    if period and (from_str or to_str):
        raise click.UsageError("--period is mutually exclusive with --from/--to.")

    if period:
        from_str, to_str = _resolve_period(period)
    else:
        if from_str:
            _validate_date(from_str, "--from")
        if to_str:
            _validate_date(to_str, "--to")

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    resolved_title = title or f"Brief — @{reference}"
    output_path = Path(output_str) if output_str else Path(f"brief-{reference}-{today}.md")

    # ── 1. Fetch notes by reference ──────────────────────────────────────────
    from scribe.store import fetch_notes_by_ref

    db_path = get_cartographer_db()
    try:
        notes = fetch_notes_by_ref(reference, db_path, from_str, to_str)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not notes:
        window = f" for {from_str} to {to_str}" if (from_str or to_str) else ""
        click.echo(f"No notes found mentioning @{reference}{window}.", err=True)
        sys.exit(0)

    # ── 2. Dry-run ───────────────────────────────────────────────────────────
    if dry_run:
        click.echo(f"Subject: @{reference}  Notes: {len(notes)}\n")
        for note in notes:
            ts = note.time_stamp[:10] if note.time_stamp else "?"
            click.echo(f"[{ts}] {note.body.strip()}")
        sys.exit(0)

    # ── 3. Check output path ─────────────────────────────────────────────────
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
    except OSError as exc:
        click.echo(f"Error: cannot write to {output_path}: {exc}", err=True)
        sys.exit(1)

    # ── 4. Retrieve context chunks ───────────────────────────────────────────
    from scribe.cartographer import retrieve_chunks

    effective_top_k = top_k if top_k is not None else get_scribe_top_k()
    note_ids = [n.id for n in notes]
    try:
        chunks = retrieve_chunks(note_ids, effective_top_k, get_cartographer_bin())
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 5. Build LLM backend ─────────────────────────────────────────────────
    from scribe.llm import build_backend

    resolved_backend = backend_name or get_scribe_backend()
    try:
        backend = build_backend(
            resolved_backend,
            get_scribe_model() or None,
            get_ollama_url(),
            get_claude_bin(),
        )
    except ValueError as exc:
        raise click.UsageError(str(exc))

    # ── 6. Generate briefing ─────────────────────────────────────────────────
    from scribe.brief import run_brief

    try:
        markdown = run_brief(reference, notes, chunks, resolved_title, from_str, to_str, backend)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 7. Write output ──────────────────────────────────────────────────────
    output_path.write_text(markdown, encoding="utf-8")
    click.echo(f"Written: {output_path}", err=True)


# ---------------------------------------------------------------------------
# open-items
# ---------------------------------------------------------------------------


@main.command("open-items")
@click.option("--date", "date_str", default=None, metavar="YYYY-MM-DD", help="Single day (default: today).")
@click.option("--from", "from_str", default=None, metavar="YYYY-MM-DD", help="Start of date range (inclusive).")
@click.option("--to", "to_str", default=None, metavar="YYYY-MM-DD", help="End of date range (inclusive).")
@click.option(
    "--period",
    default=None,
    type=_PERIOD_CHOICES,
    help="Named period: today, yesterday, this-week, this-month, last-week, last-month.",
)
@click.option("--title", default=None, help="Report title. Default: 'Open Items — {date}'.")
@click.option("--output", "output_str", default=None, metavar="PATH", help="Output file.")
@click.option("--top-k", "top_k", default=None, type=int, help="Chunks to retrieve (overrides SCRIBE_TOP_K).")
@click.option("--backend", "backend_name", default=None, help="LLM backend: ollama, dummy. Overrides SCRIBE_BACKEND.")
@click.option("--dry-run", is_flag=True, help="Print fetched notes, skip Cartographer and LLM.")
def open_items(
    date_str: str | None,
    from_str: str | None,
    to_str: str | None,
    period: str | None,
    title: str | None,
    output_str: str | None,
    top_k: int | None,
    backend_name: str | None,
    dry_run: bool,
) -> None:
    """Extract open commitments and follow-ups from notes in a date range.

    Reads notes from the Cartographer DB, retrieves semantic context,
    and asks the LLM to produce a numbered list of pending action items.
    """
    from scribe.config import (
        get_cartographer_bin,
        get_cartographer_db,
        get_claude_bin,
        get_ollama_url,
        get_scribe_backend,
        get_scribe_model,
        get_scribe_top_k,
    )

    if date_str and (from_str or to_str):
        raise click.UsageError("--date is mutually exclusive with --from/--to.")
    if period and (date_str or from_str or to_str):
        raise click.UsageError("--period is mutually exclusive with --date/--from/--to.")

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    if period:
        from_date, to_date = _resolve_period(period)
    elif date_str:
        from_date = to_date = date_str
    elif from_str or to_str:
        from_date = from_str or today
        to_date = to_str or today
    else:
        from_date = to_date = today

    _validate_date(from_date, "--date/--from")
    _validate_date(to_date, "--to")

    label = from_date if from_date == to_date else f"{from_date}_{to_date}"
    resolved_title = title or f"Open Items — {label}"
    output_path = Path(output_str) if output_str else Path(f"open-items-{label}.md")

    # ── 1. Fetch notes ───────────────────────────────────────────────────────
    from scribe.store import fetch_notes_in_range

    db_path = get_cartographer_db()
    try:
        notes = fetch_notes_in_range(from_date, to_date, db_path)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not notes:
        period = from_date if from_date == to_date else f"{from_date} to {to_date}"
        click.echo(f"No notes found for {period}.", err=True)
        sys.exit(0)

    # ── 2. Dry-run ───────────────────────────────────────────────────────────
    if dry_run:
        period = from_date if from_date == to_date else f"{from_date} – {to_date}"
        click.echo(f"Period: {period}  Notes: {len(notes)}\n")
        for note in notes:
            ts = note.time_stamp[:10] if note.time_stamp else "?"
            click.echo(f"[{ts}] {note.body.strip()}")
        sys.exit(0)

    # ── 3. Check output path ─────────────────────────────────────────────────
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
    except OSError as exc:
        click.echo(f"Error: cannot write to {output_path}: {exc}", err=True)
        sys.exit(1)

    # ── 4. Retrieve context chunks ───────────────────────────────────────────
    from scribe.cartographer import retrieve_chunks

    effective_top_k = top_k if top_k is not None else get_scribe_top_k()
    note_ids = [n.id for n in notes]
    try:
        chunks = retrieve_chunks(note_ids, effective_top_k, get_cartographer_bin())
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 5. Build LLM backend ─────────────────────────────────────────────────
    from scribe.llm import build_backend

    resolved_backend = backend_name or get_scribe_backend()
    try:
        backend = build_backend(
            resolved_backend,
            get_scribe_model() or None,
            get_ollama_url(),
            get_claude_bin(),
        )
    except ValueError as exc:
        raise click.UsageError(str(exc))

    # ── 6. Generate open-items list ──────────────────────────────────────────
    from scribe.open_items import run_open_items

    try:
        markdown = run_open_items(notes, chunks, resolved_title, from_date, to_date, backend)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 7. Write output ──────────────────────────────────────────────────────
    output_path.write_text(markdown, encoding="utf-8")
    click.echo(f"Written: {output_path}", err=True)


# ---------------------------------------------------------------------------
# patterns
# ---------------------------------------------------------------------------


@main.command()
@click.option("--from", "from_str", default=None, metavar="YYYY-MM-DD", help="Start of date range (inclusive).")
@click.option("--to", "to_str", default=None, metavar="YYYY-MM-DD", help="End of date range (inclusive).")
@click.option(
    "--period",
    default=None,
    type=_PERIOD_CHOICES,
    help="Named period: today, yesterday, this-week, this-month, last-week, last-month.",
)
@click.option("--tag", default=None, help="Scope to notes tagged with this tag (no # prefix).")
@click.option("--ref", default=None, help="Scope to notes referencing this person or project (no @ prefix).")
@click.option("--title", default=None, help="Report title. Default: 'Patterns — {from} to {to}'.")
@click.option("--output", "output_str", default=None, metavar="PATH", help="Output file.")
@click.option("--top-k", "top_k", default=None, type=int, help="Chunks to retrieve (overrides SCRIBE_TOP_K).")
@click.option("--backend", "backend_name", default=None, help="LLM backend: ollama, dummy. Overrides SCRIBE_BACKEND.")
@click.option("--dry-run", is_flag=True, help="Print fetched notes, skip Cartographer and LLM.")
def patterns(
    from_str: str | None,
    to_str: str | None,
    period: str | None,
    tag: str | None,
    ref: str | None,
    title: str | None,
    output_str: str | None,
    top_k: int | None,
    backend_name: str | None,
    dry_run: bool,
) -> None:
    """Analyse a note corpus for recurring themes and patterns.

    Requires an explicit date range. Optionally scoped to a tag or reference.
    """
    from scribe.config import (
        get_cartographer_bin,
        get_cartographer_db,
        get_claude_bin,
        get_ollama_url,
        get_scribe_backend,
        get_scribe_model,
        get_scribe_top_k,
    )

    if tag and ref:
        raise click.UsageError("--tag and --ref are mutually exclusive.")
    if period and (from_str or to_str):
        raise click.UsageError("--period is mutually exclusive with --from/--to.")
    if not period and not (from_str and to_str):
        raise click.UsageError("Provide either --period or both --from and --to.")

    if period:
        from_str, to_str = _resolve_period(period)
    else:
        _validate_date(from_str, "--from")  # type: ignore[arg-type]
        _validate_date(to_str, "--to")  # type: ignore[arg-type]
    # Both guaranteed non-None: period resolution assigns them, and the UsageError
    # guard above rejects the case where period is absent but either is missing.
    assert from_str is not None and to_str is not None

    resolved_title = title or f"Patterns — {from_str} to {to_str}"
    output_path = Path(output_str) if output_str else Path(f"patterns-{from_str}-{to_str}.md")

    # ── 1. Fetch notes ───────────────────────────────────────────────────────
    from scribe.store import fetch_notes_by_ref, fetch_notes_by_tag, fetch_notes_in_range

    db_path = get_cartographer_db()
    try:
        if tag:
            notes = fetch_notes_by_tag(tag, from_str, to_str, db_path)
        elif ref:
            notes = fetch_notes_by_ref(ref, db_path, from_str, to_str)
        else:
            notes = fetch_notes_in_range(from_str, to_str, db_path)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not notes:
        scope = f" for #{tag}" if tag else (f" for @{ref}" if ref else "")
        click.echo(f"No notes found for {from_str} to {to_str}{scope}.", err=True)
        sys.exit(0)

    # ── 2. Dry-run ───────────────────────────────────────────────────────────
    if dry_run:
        click.echo(f"Period: {from_str} to {to_str}  Notes: {len(notes)}\n")
        for note in notes:
            ts = note.time_stamp[:10] if note.time_stamp else "?"
            click.echo(f"[{ts}] {note.body.strip()}")
        sys.exit(0)

    # ── 3. Check output path ─────────────────────────────────────────────────
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
    except OSError as exc:
        click.echo(f"Error: cannot write to {output_path}: {exc}", err=True)
        sys.exit(1)

    # ── 4. Retrieve context chunks ───────────────────────────────────────────
    from scribe.cartographer import retrieve_chunks

    effective_top_k = top_k if top_k is not None else get_scribe_top_k()
    note_ids = [n.id for n in notes]
    try:
        chunks = retrieve_chunks(note_ids, effective_top_k, get_cartographer_bin())
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 5. Build LLM backend ─────────────────────────────────────────────────
    from scribe.llm import build_backend

    resolved_backend = backend_name or get_scribe_backend()
    try:
        backend = build_backend(
            resolved_backend,
            get_scribe_model() or None,
            get_ollama_url(),
            get_claude_bin(),
        )
    except ValueError as exc:
        raise click.UsageError(str(exc))

    # ── 6. Generate patterns analysis ────────────────────────────────────────
    from scribe.patterns import run_patterns

    try:
        markdown = run_patterns(notes, chunks, resolved_title, from_str, to_str, tag, ref, backend)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 7. Write output ──────────────────────────────────────────────────────
    output_path.write_text(markdown, encoding="utf-8")
    click.echo(f"Written: {output_path}", err=True)


# ---------------------------------------------------------------------------
# digest
# ---------------------------------------------------------------------------


@main.command()
@click.option("--date", "date_str", default=None, metavar="YYYY-MM-DD", help="Single day (default: today).")
@click.option("--from", "from_str", default=None, metavar="YYYY-MM-DD", help="Start of date range (inclusive).")
@click.option("--to", "to_str", default=None, metavar="YYYY-MM-DD", help="End of date range (inclusive).")
@click.option(
    "--period",
    default=None,
    type=_PERIOD_CHOICES,
    help="Named period: today, yesterday, this-week, this-month, last-week, last-month.",
)
@click.option("--tag", default=None, help="Scope to notes tagged with this tag (no # prefix).")
@click.option("--ref", default=None, help="Scope to notes referencing this person or project (no @ prefix).")
@click.option("--title", default=None, help="Report title. Default: 'Digest — {date}'.")
@click.option("--output", "output_str", default=None, metavar="PATH", help="Output file.")
@click.option("--top-k", "top_k", default=None, type=int, help="Chunks to retrieve (overrides SCRIBE_TOP_K).")
@click.option("--backend", "backend_name", default=None, help="LLM backend: ollama, dummy. Overrides SCRIBE_BACKEND.")
@click.option("--dry-run", is_flag=True, help="Print fetched notes, skip Cartographer and LLM.")
@click.option("--frontmatter/--no-frontmatter", default=True, help="Prepend YAML frontmatter (default: on).")
def digest(
    date_str: str | None,
    from_str: str | None,
    to_str: str | None,
    period: str | None,
    tag: str | None,
    ref: str | None,
    title: str | None,
    output_str: str | None,
    top_k: int | None,
    backend_name: str | None,
    dry_run: bool,
    frontmatter: bool,
) -> None:
    """Generate a structured activity digest for reporting.

    Reads notes from the Cartographer DB, retrieves semantic context,
    and asks the LLM to produce a grouped summary suitable for reporting up.
    """
    from scribe.config import (
        get_archive_dir,
        get_cartographer_bin,
        get_cartographer_db,
        get_claude_bin,
        get_ollama_url,
        get_scribe_backend,
        get_scribe_model,
        get_scribe_top_k,
    )

    if date_str and (from_str or to_str):
        raise click.UsageError("--date is mutually exclusive with --from/--to.")
    if period and (date_str or from_str or to_str):
        raise click.UsageError("--period is mutually exclusive with --date/--from/--to.")
    if tag and ref:
        raise click.UsageError("--tag and --ref are mutually exclusive.")

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    if period:
        from_date, to_date = _resolve_period(period)
    elif date_str:
        from_date = to_date = date_str
    elif from_str or to_str:
        from_date = from_str or today
        to_date = to_str or today
    else:
        from_date = to_date = today

    _validate_date(from_date, "--date/--from")
    _validate_date(to_date, "--to")

    label = from_date if from_date == to_date else f"{from_date}_{to_date}"
    resolved_title = title or f"Digest — {label}"
    if output_str:
        output_path = Path(output_str)
    elif archive_dir := get_archive_dir():
        output_path = archive_dir / "Weekly Reports" / f"{from_date} Digest.md"
    else:
        output_path = Path(f"digest-{label}.md")

    # ── 1. Fetch notes ───────────────────────────────────────────────────────
    from scribe.store import fetch_notes_by_ref, fetch_notes_by_tag, fetch_notes_in_range

    db_path = get_cartographer_db()
    try:
        if tag:
            notes = fetch_notes_by_tag(tag, from_date, to_date, db_path)
        elif ref:
            notes = fetch_notes_by_ref(ref, db_path, from_date, to_date)
        else:
            notes = fetch_notes_in_range(from_date, to_date, db_path)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if not notes:
        period = from_date if from_date == to_date else f"{from_date} to {to_date}"
        click.echo(f"No notes found for {period}.", err=True)
        sys.exit(0)

    # ── 2. Dry-run ───────────────────────────────────────────────────────────
    if dry_run:
        period = from_date if from_date == to_date else f"{from_date} – {to_date}"
        click.echo(f"Period: {period}  Notes: {len(notes)}\n")
        for note in notes:
            ts = note.time_stamp[:10] if note.time_stamp else "?"
            click.echo(f"[{ts}] {note.body.strip()}")
        sys.exit(0)

    # ── 3. Check output path ─────────────────────────────────────────────────
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
    except OSError as exc:
        click.echo(f"Error: cannot write to {output_path}: {exc}", err=True)
        sys.exit(1)

    # ── 4. Retrieve context chunks ───────────────────────────────────────────
    from scribe.cartographer import retrieve_chunks

    effective_top_k = top_k if top_k is not None else get_scribe_top_k()
    note_ids = [n.id for n in notes]
    try:
        chunks = retrieve_chunks(note_ids, effective_top_k, get_cartographer_bin())
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 5. Build LLM backend ─────────────────────────────────────────────────
    from scribe.llm import build_backend

    resolved_backend = backend_name or get_scribe_backend()
    try:
        backend = build_backend(
            resolved_backend,
            get_scribe_model() or None,
            get_ollama_url(),
            get_claude_bin(),
        )
    except ValueError as exc:
        raise click.UsageError(str(exc))

    # ── 6. Generate digest ───────────────────────────────────────────────────
    from scribe.digest import run_digest

    try:
        markdown = run_digest(
            notes, chunks, resolved_title, from_date, to_date, tag, ref, backend, frontmatter=frontmatter
        )
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # ── 7. Write output ──────────────────────────────────────────────────────
    output_path.write_text(markdown, encoding="utf-8")
    click.echo(f"Written: {output_path}", err=True)


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


@main.command()
@click.option("--dry-run", is_flag=True, help="Print what would be created/updated without writing.")
def registry(dry_run: bool) -> None:
    """Sync Mnemo Registry (Kinds + Instances) into the Obsidian vault.

    Creates a folder per Kind and a file per Instance under archive_dir.
    Existing files are updated idempotently: only name, description, and refs
    are overwritten; body content and other frontmatter are preserved.
    """
    from scribe.config import get_archive_dir, get_cartographer_db

    archive_dir = get_archive_dir()
    if archive_dir is None:
        click.echo("Error: archive_dir is not configured. Set [output] archive_dir in config.toml.", err=True)
        sys.exit(1)

    db_path = get_cartographer_db()
    if not db_path.exists():
        click.echo(f"Error: Cartographer DB not found at {db_path}. Run `carto sync pull`.", err=True)
        sys.exit(1)

    if dry_run:
        from scribe.store import fetch_instances, fetch_kinds

        for kind in fetch_kinds(db_path):
            click.echo(f"[kind]     {archive_dir / kind.plural / 'MANIFEST.md'}")
            for instance in fetch_instances(kind.id, db_path):
                click.echo(f"[instance] {archive_dir / kind.plural / (instance.name + '.md')}")
        sys.exit(0)

    from scribe.registry import sync_registry

    created, updated, unchanged = sync_registry(archive_dir, db_path)
    click.echo(f"Registry sync: {created} created, {updated} updated, {unchanged} unchanged", err=True)


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@main.group()
def config() -> None:
    """View or initialise Scribe configuration."""


@config.command("show")
def config_show() -> None:
    """Print the resolved configuration (file + env overrides)."""
    from scribe.config import CONFIG_FILE, resolved_config

    source = str(CONFIG_FILE) if CONFIG_FILE.exists() else "(defaults — no config file)"
    click.echo(f"config: {source}\n")

    for section, values in resolved_config().items():
        click.echo(f"[{section}]")
        assert isinstance(values, dict)
        for key, val in values.items():
            click.echo(f"  {key} = {val!r}")
        click.echo()


@config.command("init")
def config_init() -> None:
    """Write a default config.toml to ~/.codex_/scribe/."""
    from scribe.config import CONFIG_FILE, write_default_config

    try:
        write_default_config()
        click.echo(f"Created: {CONFIG_FILE}")
    except FileExistsError:
        click.echo(f"Already exists: {CONFIG_FILE}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_period(period: str) -> tuple[str, str]:
    today = date.today()
    p = period.lower()
    if p == "today":
        d = today.strftime("%Y-%m-%d")
        return d, d
    if p == "yesterday":
        d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        return d, d
    if p == "this-week":
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    if p == "this-month":
        first = today.replace(day=1)
        return first.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
    if p == "last-week":
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        return last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d")
    if p == "last-month":
        first_this = today.replace(day=1)
        last_day = first_this - timedelta(days=1)
        return last_day.replace(day=1).strftime("%Y-%m-%d"), last_day.strftime("%Y-%m-%d")
    raise ValueError(f"Unknown period: {period!r}")


def _validate_date(value: str, flag: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise click.UsageError(f"{flag} must be YYYY-MM-DD, got: {value!r}")
