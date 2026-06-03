# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

import sys
from datetime import date, timedelta
from pathlib import Path

import click

from codex_core.models import Note
from codex_core.session import clear_session_context, get_session_context, set_session_context
from codex_core.store import (
    add_note,
    create_instance,
    create_type,
    daily_report,
    delete_note,
    export_kb_all,
    export_kb_instance,
    export_kb_kind,
    get_default_tags,
    get_sync_adapter,
    get_sync_folder,
    get_sync_local_path,
    list_instances,
    list_notes,
    list_references,
    list_types,
    search_notes,
    set_default_tags,
    set_sync_adapter,
    set_sync_folder,
    set_sync_local_path,
)


def _render_note(note: Note) -> str:
    ts = note.created_at.strftime("%Y-%m-%d %H:%M")
    lines = [f"[{note.id}] {ts}", note.body]
    if note.tags:
        lines.append("  tags:       " + "  ".join(f"#{t}" for t in note.tags))
    if note.references:
        lines.append("  references: " + "  ".join(f"@{r}" for r in note.references))
    return "\n".join(lines)


@click.group()
def cli() -> None:
    """note-taker — capture and search plain-text notes."""


@cli.command()
@click.argument("text", required=False)
def add(text: str | None) -> None:
    """Add a new note. Pass TEXT as an argument or pipe via stdin."""
    if text is None:
        if not sys.stdin.isatty():
            text = sys.stdin.read().strip()
        else:
            text = click.prompt("Note")
    if not text:
        raise click.ClickException("Note text cannot be empty.")
    defaults = get_default_tags()
    session_tags, session_references = get_session_context()
    all_extra_tags = list(dict.fromkeys(defaults + session_tags))
    if all_extra_tags or session_references:
        from codex_core.parser import parse as _parse

        parsed = _parse(text)
        missing_tags = [t for t in all_extra_tags if t not in parsed.tags]
        missing_references = [r for r in session_references if r not in parsed.references]
        suffix = [f"#{t}" for t in missing_tags] + [f"@{r}" for r in missing_references]
        if suffix:
            text = text + " " + " ".join(suffix)
    note = add_note(text)
    click.echo(f"Added note #{note.id}")


@cli.command("list")
@click.option("--tag", default=None, help="Filter by #tag (omit the #)")
@click.option("--reference", default=None, help="Filter by @reference (omit the @)")
@click.option("--limit", default=20, show_default=True, help="Max results")
def list_cmd(tag: str | None, reference: str | None, limit: int) -> None:
    """List recent notes, optionally filtered by tag or reference."""
    notes = list_notes(tag=tag, reference=reference, limit=limit)
    if not notes:
        click.echo("No notes found.")
        return
    for note in notes:
        click.echo(_render_note(note))
        click.echo()


@cli.command()
@click.argument("query")
def search(query: str) -> None:
    """Full-text search across note bodies."""
    notes = search_notes(query)
    if not notes:
        click.echo("No notes found.")
        return
    for note in notes:
        click.echo(_render_note(note))
        click.echo()


@cli.command()
@click.option(
    "--from", "from_date", default=None, metavar="YYYY-MM-DD", help="Start date (inclusive). Defaults to today."
)
@click.option("--to", "to_date", default=None, metavar="YYYY-MM-DD", help="End date (inclusive). Defaults to --from.")
@click.option("--days", default=None, type=int, help="Number of days ending today (alternative to --from/--to).")
@click.option("--output", "-o", default=None, metavar="FILE", help="Write report to a file instead of stdout.")
def report(from_date: str | None, to_date: str | None, days: int | None, output: str | None) -> None:
    """Generate a daily markdown report for a date range."""
    today = date.today()
    if days is not None:
        start = today - timedelta(days=days - 1)
        end = today
    else:
        start = date.fromisoformat(from_date) if from_date else today
        end = date.fromisoformat(to_date) if to_date else start

    md = daily_report(start, end)
    if not md:
        click.echo("No notes found for that period.")
        return

    if output:
        Path(output).write_text(md + "\n", encoding="utf-8")
        click.echo(f"Report written to {output}")
    else:
        click.echo(md)


@cli.command("export-kb")
@click.option("--kind", default=None, metavar="NAME", help="Export all instances of a Kind.")
@click.option("--instance", default=None, metavar="NAME", help="Export a single Instance.")
@click.option("--output", "-o", default=None, metavar="FILE", help="Write to a file instead of stdout.")
def export_kb(kind: str | None, instance: str | None, output: str | None) -> None:
    """Export a Kind or Instance knowledge base as markdown."""
    if kind and instance:
        raise click.UsageError("Provide --kind or --instance, not both.")

    if kind:
        md = export_kb_kind(kind)
    elif instance:
        md = export_kb_instance(instance)
    else:
        md = export_kb_all()
    if not md:
        raise click.ClickException("Not found.")

    if output:
        Path(output).write_text(md + "\n", encoding="utf-8")
        click.echo(f"Exported to {output}")
    else:
        click.echo(md)


@cli.command()
@click.argument("note_id", type=int)
def delete(note_id: int) -> None:
    """Delete a note by its ID."""
    if delete_note(note_id):
        click.echo(f"Deleted note #{note_id}")
    else:
        raise click.ClickException(f"Note #{note_id} not found.")


@cli.group()
def references() -> None:
    """Manage known @references."""


@references.command("list")
def references_list() -> None:
    """List all references extracted from notes."""
    all_references = list_references()
    if not all_references:
        click.echo("No references found.")
        return
    for r in all_references:
        click.echo(f"@{r.name}")


@cli.group()
def config() -> None:
    """Manage note-taker configuration."""


@config.command("default-tags")
@click.argument("tags", nargs=-1)
@click.option("--clear", is_flag=True, help="Remove all default tags.")
def config_default_tags(tags: tuple[str, ...], clear: bool) -> None:
    """View or set default tags added to every new note.

    With no arguments, shows the current default tags.
    Pass TAG names (without #) to replace the current list.
    Use --clear to remove all default tags.
    """
    if clear:
        set_default_tags([])
        click.echo("Default tags cleared.")
    elif tags:
        set_default_tags(list(tags))
        formatted = "  ".join(f"#{t}" for t in get_default_tags())
        click.echo(f"Default tags set: {formatted}")
    else:
        current = get_default_tags()
        if current:
            click.echo("Default tags: " + "  ".join(f"#{t}" for t in current))
        else:
            click.echo("No default tags configured.")


@cli.group()
def session() -> None:
    """Manage the current session context (not persisted to the database)."""


@session.command("set")
@click.option("--tag", "tags", multiple=True, help="Tag to apply to all new notes (omit #).")
@click.option("--mention", "mentions", multiple=True, help="Reference to apply to all new notes (omit @).")
def session_set(tags: tuple[str, ...], mentions: tuple[str, ...]) -> None:
    """Set session-wide #tags and @mentions applied to every new note.

    Replaces any previously active session context.
    """
    if not tags and not mentions:
        raise click.ClickException("Provide at least one --tag or --mention.")
    norm_tags = [t.lstrip("#").lower() for t in tags if t.strip()]
    norm_mentions = [m.lstrip("@").lower() for m in mentions if m.strip()]
    set_session_context(norm_tags, norm_mentions)
    parts = ["  ".join(f"#{t}" for t in norm_tags), "  ".join(f"@{r}" for r in norm_mentions)]
    click.echo("Session context: " + "  ".join(p for p in parts if p))


@session.command("show")
def session_show() -> None:
    """Show the active session context."""
    tags, references = get_session_context()
    if not tags and not references:
        click.echo("No session context active.")
        return
    if tags:
        click.echo("tags:     " + "  ".join(f"#{t}" for t in tags))
    if references:
        click.echo("mentions: " + "  ".join(f"@{r}" for r in references))


@session.command("clear")
def session_clear() -> None:
    """Clear the active session context."""
    clear_session_context()
    click.echo("Session context cleared.")


# ── kinds ─────────────────────────────────────────────────────────────────────


@cli.group()
def kinds() -> None:
    """Manage Kinds and their Instances."""


@kinds.command("list")
def kinds_list() -> None:
    """List all Kinds."""
    all_kinds = list_types()
    if not all_kinds:
        click.echo("No kinds found.")
        return
    for k in all_kinds:
        click.echo(k.name)


@kinds.command("instances")
@click.argument("kind_name")
def kinds_instances(kind_name: str) -> None:
    """List all Instances of a Kind."""
    all_kinds = {k.name.lower(): k for k in list_types()}
    kind = all_kinds.get(kind_name.lower())
    if kind is None:
        raise click.ClickException(f"Kind '{kind_name}' not found.")
    instances = list_instances(kind.id)
    if not instances:
        click.echo(f"No instances found for '{kind.name}'.")
        return
    for i in instances:
        click.echo(i.name)


@kinds.command("import")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def kinds_import(file: Path) -> None:
    """Bulk-import Kinds and Instances from a YAML file.

    \b
    Expected format:
      kinds:
        - name: Person
          plural: People
          description: Optional description
          instances:
            - name: John Smith
              description: Optional
              references:
                - AcmeCorp
    """
    import yaml  # noqa: PLC0415

    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise click.ClickException(f"Invalid YAML: {exc}") from exc

    if not isinstance(data, dict) or "kinds" not in data:
        raise click.ClickException("File must have a top-level 'kinds' list.")

    raw_kinds = data.get("kinds") or []
    if not isinstance(raw_kinds, list):
        raise click.ClickException("'kinds' must be a list.")

    existing_kinds = {k.name.lower(): k for k in list_types()}
    kinds_created = kinds_skipped = instances_created = instances_skipped = 0

    for entry in raw_kinds:
        if not isinstance(entry, dict) or not entry.get("name"):
            raise click.ClickException(f"Each kind must have a 'name' field: {entry!r}")

        kind_name = str(entry["name"]).strip()
        kind_key = kind_name.lower()

        if kind_key in existing_kinds:
            kind = existing_kinds[kind_key]
            kinds_skipped += 1
        else:
            kind = create_type(
                name=kind_name,
                plural=str(entry.get("plural") or ""),
                description=str(entry.get("description") or ""),
            )
            existing_kinds[kind_key] = kind
            kinds_created += 1

        existing_instance_names = {i.name.lower() for i in list_instances(kind.id)}

        for inst in entry.get("instances") or []:
            if not isinstance(inst, dict) or not inst.get("name"):
                raise click.ClickException(f"Each instance must have a 'name' field: {inst!r}")
            inst_name = str(inst["name"]).strip()
            if inst_name.lower() in existing_instance_names:
                instances_skipped += 1
            else:
                raw_refs = inst.get("references") or []
                refs = [str(r).lstrip("@").lower() for r in raw_refs]
                create_instance(
                    name=inst_name,
                    instance_kind_id=kind.id,
                    description=str(inst.get("description") or ""),
                    references=refs,
                )
                existing_instance_names.add(inst_name.lower())
                instances_created += 1

    click.echo(
        f"Import complete — "
        f"{kinds_created} kind(s) created, {kinds_skipped} skipped; "
        f"{instances_created} instance(s) created, {instances_skipped} skipped."
    )


# ── sync ──────────────────────────────────────────────────────────────────────


def _get_adapter() -> object:
    adapter = get_sync_adapter()
    if adapter == "local_folder":
        from codex_core.sync.local_folder import LocalFolderAdapter

        raw = get_sync_local_path()
        if not raw:
            raise click.ClickException("Local folder path is not configured. Run: note sync config local-path <PATH>")
        return LocalFolderAdapter(Path(raw))
    # default: google_drive
    from codex_core.sync.google_drive import GoogleDriveAdapter

    auth_dir = Path.home() / ".codex_"
    return GoogleDriveAdapter(
        auth_dir / "credentials.json",
        auth_dir / "token.json",
        folder_name=get_sync_folder(),
    )


@cli.group()
def sync() -> None:
    """Sync notes across devices via remote storage."""


@sync.command("push")
def sync_push() -> None:
    """Upload this device's DB to remote storage."""
    from codex_core.db import get_db_path
    from codex_core.sync.device import get_device_id

    adapter = _get_adapter()
    device_id = get_device_id()
    db_path = get_db_path()
    click.echo(f"Pushing as device {device_id!r} …")
    adapter.upload(device_id, db_path)  # type: ignore[attr-defined]
    click.echo("Push complete.")


@sync.command("pull")
def sync_pull() -> None:
    """Download and merge all other devices' DBs into the local DB."""
    from codex_core.db import connect, get_db_path
    from codex_core.sync.device import get_device_id
    from codex_core.sync.merge import merge_remote

    adapter = _get_adapter()
    device_id = get_device_id()
    devices = [d for d in adapter.list_devices() if d != device_id]  # type: ignore[attr-defined]
    if not devices:
        click.echo("No other devices found in remote storage.")
        return
    local_conn = connect(get_db_path())
    total_added = total_updated = total_deleted = 0
    for d in devices:
        click.echo(f"Merging from {d!r} …")
        data: bytes = adapter.download(d)  # type: ignore[attr-defined]
        result = merge_remote(local_conn, data)
        total_added += result.added
        total_updated += result.updated
        total_deleted += result.deleted
    click.echo(f"Sync complete — {total_added} added, {total_updated} updated, {total_deleted} deleted.")


@sync.command("status")
def sync_status() -> None:
    """Show this device's ID and sync configuration."""
    from codex_core.sync.device import get_device_id

    adapter = get_sync_adapter()
    click.echo(f"Device ID:     {get_device_id()}")
    click.echo(f"Adapter:       {adapter}")
    if adapter == "local_folder":
        click.echo(f"Local path:    {get_sync_local_path() or '(not set)'}")
    else:
        click.echo(f"Drive folder:  {get_sync_folder()}")


@sync.group("config")
def sync_config() -> None:
    """View or update sync configuration."""


@sync_config.command("folder")
@click.argument("name", required=False)
@click.option("--clear", is_flag=True, help="Reset to the default folder name.")
def sync_config_folder(name: str | None, clear: bool) -> None:
    """View or set the Google Drive folder used for sync.

    With no arguments, shows the current folder name.
    Pass NAME to change it. Use --clear to reset to 'note-taker-sync'.
    """
    if clear:
        set_sync_folder("note-taker-sync")
        click.echo("Drive folder reset to: note-taker-sync")
    elif name:
        set_sync_folder(name)
        click.echo(f"Drive folder set to: {name}")
    else:
        click.echo(f"Drive folder: {get_sync_folder()}")


@sync_config.command("adapter")
@click.argument("name", required=False, metavar="ADAPTER")
def sync_config_adapter(name: str | None) -> None:
    """View or set the sync storage adapter.

    ADAPTER must be 'google_drive' or 'local_folder'.
    With no arguments, shows the current adapter.
    """
    if name:
        try:
            set_sync_adapter(name)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Sync adapter set to: {name}")
    else:
        click.echo(f"Sync adapter: {get_sync_adapter()}")


@sync_config.command("local-path")
@click.argument("path", required=False)
@click.option("--clear", is_flag=True, help="Clear the configured local path.")
def sync_config_local_path(path: str | None, clear: bool) -> None:
    """View or set the local folder path used by the local_folder adapter.

    With no arguments, shows the current path.
    """
    if clear:
        set_sync_local_path("")
        click.echo("Local sync path cleared.")
    elif path:
        set_sync_local_path(path)
        click.echo(f"Local sync path set to: {path}")
    else:
        current = get_sync_local_path()
        click.echo(f"Local sync path: {current or '(not set)'}")
