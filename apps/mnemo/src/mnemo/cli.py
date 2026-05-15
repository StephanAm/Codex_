import sys

import click

from .models import Note
from .session import clear_session_context, get_session_context, set_session_context
from .store import (
    add_note,
    delete_note,
    get_default_tags,
    list_entities,
    list_notes,
    search_notes,
    set_default_tags,
    set_entity_type,
)


def _render_note(note: Note) -> str:
    ts = note.created_at.strftime("%Y-%m-%d %H:%M")
    lines = [f"[{note.id}] {ts}", note.body]
    if note.tags:
        lines.append("  tags:     " + "  ".join(f"#{t}" for t in note.tags))
    if note.entities:
        lines.append("  entities: " + "  ".join(f"@{e}" for e in note.entities))
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
    session_tags, session_entities = get_session_context()
    all_extra_tags = list(dict.fromkeys(defaults + session_tags))
    if all_extra_tags or session_entities:
        from .parser import parse as _parse
        parsed = _parse(text)
        missing_tags = [t for t in all_extra_tags if t not in parsed.tags]
        missing_entities = [e for e in session_entities if e not in parsed.entities]
        suffix = [f"#{t}" for t in missing_tags] + [f"@{e}" for e in missing_entities]
        if suffix:
            text = text + " " + " ".join(suffix)
    note = add_note(text)
    click.echo(f"Added note #{note.id}")


@cli.command("list")
@click.option("--tag", default=None, help="Filter by #tag (omit the #)")
@click.option("--entity", default=None, help="Filter by @entity (omit the @)")
@click.option("--limit", default=20, show_default=True, help="Max results")
def list_cmd(tag: str | None, entity: str | None, limit: int) -> None:
    """List recent notes, optionally filtered by tag or entity."""
    notes = list_notes(tag=tag, entity=entity, limit=limit)
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
@click.argument("note_id", type=int)
def delete(note_id: int) -> None:
    """Delete a note by its ID."""
    if delete_note(note_id):
        click.echo(f"Deleted note #{note_id}")
    else:
        raise click.ClickException(f"Note #{note_id} not found.")


@cli.group()
def entities() -> None:
    """Manage known @entities."""


@entities.command("list")
def entities_list() -> None:
    """List all entities extracted from notes."""
    all_entities = list_entities()
    if not all_entities:
        click.echo("No entities found.")
        return
    for e in all_entities:
        type_str = f"  ({e.entity_type})" if e.entity_type else ""
        click.echo(f"@{e.name}{type_str}")


@entities.command("set-type")
@click.argument("name")
@click.argument("entity_type")
def entities_set_type(name: str, entity_type: str) -> None:
    """Assign a type (person/project/team/org/…) to an @entity."""
    if set_entity_type(name, entity_type):
        click.echo(f"@{name} → {entity_type}")
    else:
        raise click.ClickException(
            f"Entity @{name} not found. Mention @{name} in a note first."
        )


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
@click.option("--mention", "mentions", multiple=True, help="Entity to apply to all new notes (omit @).")
def session_set(tags: tuple[str, ...], mentions: tuple[str, ...]) -> None:
    """Set session-wide #tags and @mentions applied to every new note.

    Replaces any previously active session context.
    """
    if not tags and not mentions:
        raise click.ClickException("Provide at least one --tag or --mention.")
    norm_tags = [t.lstrip("#").lower() for t in tags if t.strip()]
    norm_mentions = [m.lstrip("@").lower() for m in mentions if m.strip()]
    set_session_context(norm_tags, norm_mentions)
    parts = ["  ".join(f"#{t}" for t in norm_tags), "  ".join(f"@{e}" for e in norm_mentions)]
    click.echo("Session context: " + "  ".join(p for p in parts if p))


@session.command("show")
def session_show() -> None:
    """Show the active session context."""
    tags, entities = get_session_context()
    if not tags and not entities:
        click.echo("No session context active.")
        return
    if tags:
        click.echo("tags:    " + "  ".join(f"#{t}" for t in tags))
    if entities:
        click.echo("mentions: " + "  ".join(f"@{e}" for e in entities))


@session.command("clear")
def session_clear() -> None:
    """Clear the active session context."""
    clear_session_context()
    click.echo("Session context cleared.")
