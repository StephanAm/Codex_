from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import click

from scribe import __version__


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
@click.option("--title", default=None, help="Report title. Default: 'Bulletin — {date}'.")
@click.option("--output", "output_str", default=None, metavar="PATH", help="Output file. Default: ./bulletin-{date}.md")
@click.option("--top-k", "top_k", default=None, type=int, help="Chunks to retrieve (overrides SCRIBE_TOP_K).")
@click.option("--backend", "backend_name", default=None, help="LLM backend: ollama, dummy. Overrides SCRIBE_BACKEND.")
@click.option("--dry-run", is_flag=True, help="Print fetched notes, skip Cartographer and LLM.")
def bulletin(
    date_str: str | None,
    from_str: str | None,
    to_str: str | None,
    title: str | None,
    output_str: str | None,
    top_k: int | None,
    backend_name: str,
    dry_run: bool,
) -> None:
    """Generate a bulletin from notes in the given date range.

    Reads notes from the Cartographer DB, retrieves semantic context,
    and asks the LLM to produce an ordered, deduplicated bullet list.
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

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    if date_str:
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
    output_path = Path(output_str) if output_str else Path(f"bulletin-{label}.md")

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
        markdown = run_bulletin(notes, chunks, resolved_title, from_date, to_date, backend)
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
@click.option("--title", default=None, help="Report title. Default: 'To-Do — {date}'.")
@click.option("--output", "output_str", default=None, metavar="PATH", help="Output file. Default: ./todo-{date}.md")
@click.option("--top-k", "top_k", default=None, type=int, help="Chunks to retrieve (overrides SCRIBE_TOP_K).")
@click.option("--backend", "backend_name", default=None, help="LLM backend: ollama, dummy. Overrides SCRIBE_BACKEND.")
@click.option("--dry-run", is_flag=True, help="Print fetched notes, skip Cartographer and LLM.")
def todo(
    date_str: str | None,
    from_str: str | None,
    to_str: str | None,
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

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    if date_str:
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


def _validate_date(value: str, flag: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise click.UsageError(f"{flag} must be YYYY-MM-DD, got: {value!r}")
