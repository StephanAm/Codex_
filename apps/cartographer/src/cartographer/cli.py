# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from cartographer import __version__

if TYPE_CHECKING:
    from codex_core.models import Instance, InstanceKind
from cartographer.config import (
    get_drive_folder,
    get_local_folder_path,
    get_mnemo_db_path,
    get_remote_name,
    get_source_type,
    set_drive_folder,
    set_local_folder_path,
    set_mnemo_db_path,
    set_remote_name,
    set_source_type,
)
from cartographer.db import connect, get_db_path
from cartographer.merge import MergeResult
from cartographer.sync import SyncReport
from cartographer.sync import sync as do_sync
from cartographer.sync import sync_push as do_sync_push

# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(__version__, prog_name="carto")
def cli() -> None:
    """Cartographer — vector indexing service for the Codex workspace."""


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@cli.command()
def status() -> None:
    """Show mirror and indexing status."""
    conn = connect()
    meta = conn.execute("SELECT schema_version, created_at, updated_at FROM db_meta").fetchone()
    notes = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    kinds = conn.execute("SELECT COUNT(*) FROM instance_kinds").fetchone()[0]
    instances = conn.execute("SELECT COUNT(*) FROM instances").fetchone()[0]
    atlas_nodes = conn.execute("SELECT COUNT(*) FROM atlas_nodes").fetchone()[0]
    atlas_pages = conn.execute("SELECT COUNT(*) FROM atlas_pages").fetchone()[0]
    indexed = conn.execute("SELECT COUNT(*) FROM index_state").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

    source_type = get_source_type()

    click.echo(f"db:           {get_db_path()}")
    click.echo(f"version:      {meta['schema_version']}")
    click.echo(f"updated:      {meta['updated_at']}")
    click.echo(f"source:       {source_type}")
    if source_type == "google_drive":
        click.echo(f"drive folder: {get_drive_folder()}")
    elif source_type == "local_folder":
        click.echo(f"local path:   {get_local_folder_path() or '(not set)'}")
    elif source_type == "mnemo_local":
        click.echo(f"mnemo db:     {get_mnemo_db_path()}")
    click.echo(f"notes:        {notes}")
    click.echo(f"kinds:        {kinds}")
    click.echo(f"instances:    {instances}")
    click.echo(f"atlas nodes:  {atlas_nodes}")
    click.echo(f"atlas pages:  {atlas_pages}")
    click.echo(f"indexed:      {indexed} documents, {chunks} chunks")


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


@cli.group()
def sync() -> None:
    """Sync the local mirror from the configured source."""


@sync.command("pull")
def sync_pull() -> None:
    """Download and merge all available Mnemo DBs into the local mirror."""
    try:
        report = do_sync()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    _print_report(report)


@sync.command("push")
def sync_push() -> None:
    """Upload the local mirror to the configured source as this device's DB."""
    try:
        device_id, source_type = do_sync_push()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"pushed: {device_id} → {source_type}")


@sync.command("auth")
def sync_auth() -> None:
    """Run the Google Drive OAuth flow (google_drive source only)."""
    if get_source_type() != "google_drive":
        raise click.ClickException("auth is only needed for the google_drive source.")
    from cartographer.adapters.google_drive import run_auth_flow
    from cartographer.config import get_drive_credentials_path, get_drive_token_path

    try:
        run_auth_flow(get_drive_credentials_path(), get_drive_token_path())
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("Authorisation complete.")


@sync.group("config")
def sync_config() -> None:
    """View or update sync source configuration."""


@sync_config.command("show")
def sync_config_show() -> None:
    """Show current sync configuration."""
    source_type = get_source_type()
    click.echo(f"source:       {source_type}")
    click.echo(f"drive folder: {get_drive_folder()}")
    click.echo(f"local path:   {get_local_folder_path() or '(not set)'}")
    click.echo(f"mnemo db:     {get_mnemo_db_path()}")


@sync_config.command("source")
@click.argument("source_type", required=False, metavar="TYPE")
def sync_config_source(source_type: str | None) -> None:
    """View or set the sync source type.

    TYPE must be one of: google_drive, local_folder, mnemo_local.
    With no argument, shows the current value.
    """
    if source_type is None:
        click.echo(get_source_type())
        return
    try:
        set_source_type(source_type)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"source set to: {source_type}")


@sync_config.command("drive-folder")
@click.argument("name", required=False)
def sync_config_drive_folder(name: str | None) -> None:
    """View or set the Google Drive folder name used for sync.

    With no argument, shows the current folder name.
    """
    if name is None:
        click.echo(get_drive_folder())
        return
    set_drive_folder(name)
    click.echo(f"drive folder set to: {name}")


@sync_config.command("local-path")
@click.argument("path", required=False)
def sync_config_local_path(path: str | None) -> None:
    """View or set the local folder path used for sync.

    With no argument, shows the current path.
    """
    if path is None:
        current = get_local_folder_path()
        click.echo(current if current else "(not set)")
        return
    set_local_folder_path(path)
    click.echo(f"local path set to: {path}")


@sync_config.command("mnemo-db")
@click.argument("path", required=False)
def sync_config_mnemo_db(path: str | None) -> None:
    """View or set the path to the local Mnemo instance's DB.

    With no argument, shows the current path.
    Defaults to ~/.codex_/mnemo_/notes.db.
    """
    if path is None:
        click.echo(get_mnemo_db_path())
        return
    set_mnemo_db_path(path)
    click.echo(f"mnemo db set to: {path}")


# ---------------------------------------------------------------------------
# remote
# ---------------------------------------------------------------------------


@cli.group()
def remote() -> None:
    """Push or pull the Cartographer DB to/from the remote location."""


@remote.command("push")
@click.option("--force", is_flag=True, help="Overwrite even if the remote DB is newer.")
def remote_push(force: bool) -> None:
    """Upload the local DB to the remote location (master operation).

    Aborts if the remote DB has a newer updated_at timestamp, unless --force
    is passed.
    """
    from cartographer.remote import RemoteNewerError, push

    try:
        name = push(force=force)
    except RemoteNewerError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"pushed: {name}")


@remote.command("pull")
def remote_pull() -> None:
    """Download the remote DB and replace the local one entirely (slave operation).

    The local DB is overwritten; there is no merge.
    """
    from cartographer.remote import pull

    try:
        updated_at = pull()
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"pulled (remote updated_at: {updated_at})")


@remote.command("config")
@click.argument("name", required=False)
def remote_config(name: str | None) -> None:
    """View or set the remote DB filename (default: cartographer).

    This is the key used in the remote adapter — the actual file stored
    remotely will be NAME.db.
    """
    if name is None:
        click.echo(get_remote_name())
        return
    set_remote_name(name)
    click.echo(f"remote name set to: {name}")


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------


@cli.group(invoke_without_command=True)
@click.option("--force", is_flag=True, help="Re-index even items that are already up-to-date.")
@click.pass_context
def index(ctx: click.Context, force: bool) -> None:
    """Build vector embeddings for all mirrored content."""
    if ctx.invoked_subcommand is not None:
        return

    from cartographer.config import (
        get_embedding_backend,
        get_embedding_model,
        get_ollama_url,
    )
    from cartographer.embeddings import DEFAULT_MODELS, build_backend
    from cartographer.indexer import run_index

    backend_name = get_embedding_backend()
    model = get_embedding_model() or DEFAULT_MODELS.get(backend_name, "")
    ollama_url = get_ollama_url()

    click.echo(f"backend: {backend_name}")
    click.echo(f"model:   {model}")

    try:
        be = build_backend(backend_name, model or None, ollama_url)
        report = run_index(be, force=force)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"notes:       +{report.notes_indexed} (skipped {report.notes_skipped})")
    click.echo(f"atlas pages: +{report.atlas_pages_indexed} (skipped {report.atlas_pages_skipped})")
    click.echo(f"kinds:       +{report.kinds_indexed} (skipped {report.kinds_skipped})")
    click.echo(f"instances:   +{report.instances_indexed} (skipped {report.instances_skipped})")
    if report.errors:
        for err in report.errors:
            click.echo(f"  error: {err}", err=True)


@index.group("config")
def index_config() -> None:
    """View or update embedding configuration."""


@index_config.command("show")
def index_config_show() -> None:
    """Show current embedding configuration."""
    from cartographer.config import get_embedding_backend, get_embedding_model, get_ollama_url
    from cartographer.embeddings import DEFAULT_MODELS

    backend = get_embedding_backend()
    model = get_embedding_model() or DEFAULT_MODELS.get(backend, "")
    click.echo(f"backend:    {backend}")
    click.echo(f"model:      {model}")
    click.echo(f"ollama url: {get_ollama_url()}")


@index_config.command("backend")
@click.argument("name", required=False, metavar="BACKEND")
def index_config_backend(name: str | None) -> None:
    """View or set the embedding backend (fastembed, ollama).

    With no argument, shows the current value.
    """
    from cartographer.config import get_embedding_backend, set_embedding_backend

    if name is None:
        click.echo(get_embedding_backend())
        return
    try:
        set_embedding_backend(name)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"backend set to: {name}")


@index_config.command("model")
@click.argument("model", required=False)
def index_config_model(model: str | None) -> None:
    """View or set the embedding model name.

    Leave unset to use the default for the active backend.
    With no argument, shows the current value (or the backend default).
    """
    from cartographer.config import get_embedding_backend, get_embedding_model, set_embedding_model
    from cartographer.embeddings import DEFAULT_MODELS

    if model is None:
        current = get_embedding_model() or DEFAULT_MODELS.get(get_embedding_backend(), "")
        click.echo(current)
        return
    set_embedding_model(model)
    click.echo(f"model set to: {model}")


@index_config.command("ollama-url")
@click.argument("url", required=False)
def index_config_ollama_url(url: str | None) -> None:
    """View or set the Ollama server URL.

    Defaults to http://localhost:11434. With no argument, shows the current value.
    """
    from cartographer.config import get_ollama_url, set_ollama_url

    if url is None:
        click.echo(get_ollama_url())
        return
    set_ollama_url(url)
    click.echo(f"ollama url set to: {url}")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("query")
@click.option("--top-k", default=None, type=int, help="Maximum number of chunks to return.")
@click.option("--json", "as_json", is_flag=True, help="Emit results as JSON to stdout (for machine consumers).")
def search(query: str, top_k: int | None, as_json: bool) -> None:
    """Search the index for QUERY using the full retrieval pipeline.

    Parses @references, #tags, and date expressions from the query, then
    runs per-corpus vector search with temporal decay and boost scoring.
    """
    import json as _json

    from cartographer.config import (
        get_embedding_backend,
        get_embedding_model,
        get_ollama_url,
    )
    from cartographer.embeddings import DEFAULT_MODELS, build_backend
    from cartographer.search import search as do_search

    backend_name = get_embedding_backend()
    model = get_embedding_model() or DEFAULT_MODELS.get(backend_name, "")
    ollama_url = get_ollama_url()

    try:
        be = build_backend(backend_name, model or None, ollama_url)
        ctx = do_search(query, be)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    chunks = ctx.chunks[:top_k] if top_k is not None else ctx.chunks

    if as_json:
        click.echo(
            _json.dumps(
                {
                    "query": ctx.query,
                    "semantic_query": ctx.semantic_query,
                    "references": ctx.references,
                    "tags": ctx.tags,
                    "date_window": (
                        {"from_date": ctx.date_window.from_date, "to_date": ctx.date_window.to_date}
                        if ctx.date_window
                        else None
                    ),
                    "chunks": [
                        {
                            "corpus_type": c.corpus_type,
                            "content": c.content,
                            "score": c.score,
                            "title": c.title,
                            "tags": c.tags,
                            "references": c.references,
                            "time_stamp": c.time_stamp,
                        }
                        for c in chunks
                    ],
                }
            )
        )
        return

    if not chunks:
        click.echo("No results. Run `cartographer index` first, or try a different query.")
        return

    # Show parsed query signals when they differ from the raw query
    signals = []
    if ctx.references:
        signals.append(f"refs: {', '.join(ctx.references)}")
    if ctx.tags:
        signals.append(f"tags: {', '.join(ctx.tags)}")
    if ctx.date_window:
        signals.append(f"date: {ctx.date_window.from_date} – {ctx.date_window.to_date}")
    if signals:
        click.echo(f"signals: {' | '.join(signals)}")
    if ctx.semantic_query != query:
        click.echo(f"query:   {ctx.semantic_query}")

    for rank, chunk in enumerate(chunks, 1):
        type_label = chunk.corpus_type.replace("_", " ")
        click.echo(f"\n{rank:>2}. ({chunk.score:.3f}) [{type_label}] {chunk.title}")
        if chunk.content:
            # Show up to 200 chars of content, wrapped at 80 cols
            excerpt = chunk.content[:200].replace("\n", " ")
            words, line, lines = excerpt.split(), "", []
            for word in words:
                if len(line) + len(word) + 1 > 78:
                    lines.append(line)
                    line = word
                else:
                    line = f"{line} {word}".lstrip()
            if line:
                lines.append(line)
            for ln in lines:
                click.echo(f"     {ln}")


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--note-ids",
    "note_ids_str",
    required=True,
    metavar="IDS",
    help="Comma-separated integer note IDs.",
)
@click.option(
    "--top-k",
    default=10,
    show_default=True,
    help="Maximum number of chunks to return.",
)
def retrieve(note_ids_str: str, top_k: int) -> None:
    """Retrieve semantically related chunks for the given note IDs.

    Outputs a JSON object to stdout:

    \b
      {
        "chunks": [
          {"chunk_id": "<uuid>", "note_id": <int|null>, "text": "...", "score": 0.91},
          ...
        ]
      }

    Only JSON is written to stdout. Run `cartographer index` first to populate
    the embedding index.
    """
    import json

    from cartographer.retrieve import retrieve as do_retrieve

    try:
        note_ids = [int(x.strip()) for x in note_ids_str.split(",") if x.strip()]
    except ValueError as exc:
        raise click.ClickException(f"Invalid note IDs: {exc}") from exc

    if not note_ids:
        raise click.ClickException("--note-ids must contain at least one integer.")

    try:
        chunks = do_retrieve(note_ids, top_k)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        json.dumps(
            {
                "chunks": [
                    {
                        "chunk_id": c.chunk_id,
                        "note_id": c.note_id,
                        "text": c.text,
                        "score": c.score,
                    }
                    for c in chunks
                ]
            }
        )
    )


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


def _find_kind(name: str) -> InstanceKind:
    from codex_core import store

    matches = [k for k in store.list_types(db_path=get_db_path()) if k.name.lower() == name.lower()]
    if not matches:
        raise click.ClickException(f"Kind '{name}' not found.")
    return matches[0]


def _find_instance(name: str, kind_id: int | None = None) -> Instance:
    from codex_core import store

    matches = [
        i
        for i in store.list_instances(instance_kind_id=kind_id, db_path=get_db_path())
        if i.name.lower() == name.lower()
    ]
    if not matches:
        scope = f" in kind '{_kind_name_by_id(kind_id)}'" if kind_id is not None else ""
        raise click.ClickException(f"Instance '{name}' not found{scope}.")
    if len(matches) > 1:
        kinds_str = ", ".join(f"'{m.type.name}'" for m in matches)
        raise click.ClickException(f"Multiple instances named '{name}' ({kinds_str}). Use --kind to disambiguate.")
    return matches[0]


def _kind_name_by_id(kind_id: int | None) -> str:
    if kind_id is None:
        return ""
    from codex_core import store

    kind = store.get_type(kind_id, db_path=get_db_path())
    return kind.name if kind else str(kind_id)


@cli.group()
def registry() -> None:
    """Manage the Registry — kinds and instances."""


# ---- kinds ------------------------------------------------------------------


@registry.group()
def kinds() -> None:
    """Manage Registry kinds (common noun classifiers, e.g. Person, Company)."""


@kinds.command("list")
def kinds_list() -> None:
    """List all kinds."""
    from codex_core import store

    all_kinds = store.list_types(db_path=get_db_path())
    if not all_kinds:
        click.echo("No kinds found.")
        return
    for k in all_kinds:
        line = f"{k.name} ({k.plural})" if k.plural else k.name
        if k.description:
            line += f"  — {k.description}"
        click.echo(line)


@kinds.command("add")
@click.argument("name")
@click.option("--plural", "-p", default="", metavar="PLURAL", help="Plural form (e.g. People).")
@click.option("--description", "-d", default="", help="Optional description.")
def kinds_add(name: str, plural: str, description: str) -> None:
    """Create a new kind NAME."""
    from codex_core import store

    try:
        kind = store.create_type(name=name, plural=plural, description=description, db_path=get_db_path())
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Kind '{kind.name}' created.")


@kinds.command("show")
@click.argument("name")
def kinds_show(name: str) -> None:
    """Show details for kind NAME."""
    from codex_core import store

    kind = _find_kind(name)
    instances = store.list_instances(instance_kind_id=kind.id, db_path=get_db_path())
    click.echo(f"name:        {kind.name}")
    click.echo(f"plural:      {kind.plural or '(not set)'}")
    click.echo(f"description: {kind.description or '(none)'}")
    click.echo(f"instances:   {len(instances)}")
    click.echo(f"created:     {kind.created_at}")
    click.echo(f"updated:     {kind.updated_at}")


@kinds.command("edit")
@click.argument("name")
@click.option("--name", "new_name", default=None, metavar="NAME", help="New name.")
@click.option("--plural", "-p", default=None, metavar="PLURAL", help="New plural form.")
@click.option("--description", "-d", default=None, help="New description.")
def kinds_edit(name: str, new_name: str | None, plural: str | None, description: str | None) -> None:
    """Update kind NAME."""
    from codex_core import store

    kind = _find_kind(name)
    updated = store.update_type(
        instance_kind_id=kind.id,
        name=new_name if new_name is not None else kind.name,
        plural=plural if plural is not None else kind.plural,
        description=description if description is not None else kind.description,
        db_path=get_db_path(),
    )
    if updated is None:
        raise click.ClickException(f"Kind '{name}' not found.")
    click.echo(f"Kind '{updated.name}' updated.")


@kinds.command("delete")
@click.argument("name")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def kinds_delete(name: str, yes: bool) -> None:
    """Delete kind NAME.

    All instances belonging to this kind must be deleted first.
    """
    from codex_core import store

    kind = _find_kind(name)
    instances = store.list_instances(instance_kind_id=kind.id, db_path=get_db_path())
    if instances:
        raise click.ClickException(f"Kind '{kind.name}' has {len(instances)} instance(s). Delete them first.")
    if not yes:
        click.confirm(f"Delete kind '{kind.name}'?", abort=True)
    store.delete_type(instance_kind_id=kind.id, db_path=get_db_path())
    click.echo(f"Kind '{kind.name}' deleted.")


# ---- instances --------------------------------------------------------------


@registry.group()
def instances() -> None:
    """Manage Registry instances (specific named subjects, e.g. John Smith)."""


@instances.command("list")
@click.option("--kind", "kind_name", default=None, metavar="KIND", help="Filter by kind name.")
def instances_list(kind_name: str | None) -> None:
    """List all instances, optionally filtered by kind."""
    from codex_core import store

    kind_id = None
    if kind_name:
        kind_id = _find_kind(kind_name).id
    all_instances = store.list_instances(instance_kind_id=kind_id, db_path=get_db_path())
    if not all_instances:
        click.echo("No instances found.")
        return
    for inst in all_instances:
        click.echo(f"{inst.name}  [{inst.type.name}]")


@instances.command("add")
@click.argument("name")
@click.option("--kind", "kind_name", required=True, metavar="KIND", help="Kind this instance belongs to.")
@click.option("--description", "-d", default="", help="Optional description.")
@click.option("--ref", "refs", multiple=True, metavar="REF", help="Additional @reference token (repeatable).")
def instances_add(name: str, kind_name: str, description: str, refs: tuple[str, ...]) -> None:
    """Create a new instance NAME of the given kind."""
    from codex_core import store

    kind = _find_kind(kind_name)
    try:
        inst = store.create_instance(
            name=name,
            instance_kind_id=kind.id,
            description=description,
            references=list(refs) if refs else None,
            db_path=get_db_path(),
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Instance '{inst.name}' [{inst.type.name}] created.")


@instances.command("show")
@click.argument("name")
@click.option("--kind", "kind_name", default=None, metavar="KIND", help="Kind name to disambiguate.")
def instances_show(name: str, kind_name: str | None) -> None:
    """Show details for instance NAME."""
    kind_id = _find_kind(kind_name).id if kind_name else None
    inst = _find_instance(name, kind_id)
    click.echo(f"name:        {inst.name}")
    click.echo(f"kind:        {inst.type.name}")
    click.echo(f"description: {inst.description or '(none)'}")
    refs = ", ".join(inst.references) if inst.references else "(none)"
    click.echo(f"references:  {refs}")
    click.echo(f"created:     {inst.created_at}")
    click.echo(f"updated:     {inst.updated_at}")


@instances.command("edit")
@click.argument("name")
@click.option("--kind", "kind_name", default=None, metavar="KIND", help="Kind name to disambiguate.")
@click.option("--name", "new_name", default=None, metavar="NAME", help="New name.")
@click.option("--description", "-d", default=None, help="New description.")
@click.option("--ref", "refs", multiple=True, metavar="REF", help="Replace @references with these (repeatable).")
def instances_edit(
    name: str,
    kind_name: str | None,
    new_name: str | None,
    description: str | None,
    refs: tuple[str, ...],
) -> None:
    """Update instance NAME.

    Pass --ref one or more times to replace all explicit references.
    Omit --ref to leave references unchanged.
    """
    from codex_core import store

    kind_id = _find_kind(kind_name).id if kind_name else None
    inst = _find_instance(name, kind_id)
    updated = store.update_instance(
        instance_id=inst.id,
        name=new_name if new_name is not None else inst.name,
        description=description if description is not None else inst.description,
        instance_kind_id=inst.type.id,
        references=list(refs) if refs else None,
        db_path=get_db_path(),
    )
    if updated is None:
        raise click.ClickException(f"Instance '{name}' not found.")
    click.echo(f"Instance '{updated.name}' updated.")


@instances.command("delete")
@click.argument("name")
@click.option("--kind", "kind_name", default=None, metavar="KIND", help="Kind name to disambiguate.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def instances_delete(name: str, kind_name: str | None, yes: bool) -> None:
    """Delete instance NAME."""
    from codex_core import store

    kind_id = _find_kind(kind_name).id if kind_name else None
    inst = _find_instance(name, kind_id)
    if not yes:
        click.confirm(f"Delete instance '{inst.name}' [{inst.type.name}]?", abort=True)
    store.delete_instance(instance_id=inst.id, db_path=get_db_path())
    click.echo(f"Instance '{inst.name}' deleted.")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _print_report(report: SyncReport) -> None:
    click.echo(f"source: {report.source_type}")

    if not report.results:
        click.echo("no devices found in source")
        return

    for label, result in report.results:
        if isinstance(result, Exception):
            click.echo(f"  {label}: ERROR — {result}", err=True)
        else:
            _print_merge_result(label, result)

    if report.total_changes == 0:
        click.echo("up to date")


def _print_merge_result(label: str, result: MergeResult) -> None:
    if result.total_changes == 0:
        click.echo(f"  {label}: up to date")
        return
    click.echo(f"  {label}:")
    pairs = [
        ("notes", result.notes_added, result.notes_updated, result.notes_deleted),
        ("kinds", result.kinds_added, result.kinds_updated, result.kinds_deleted),
        ("instances", result.instances_added, result.instances_updated, result.instances_deleted),
        ("atlas nodes", result.atlas_nodes_added, result.atlas_nodes_updated, result.atlas_nodes_deleted),
        ("atlas pages", result.atlas_pages_added, result.atlas_pages_updated, result.atlas_pages_deleted),
    ]
    for name, added, updated, deleted in pairs:
        if added or updated or deleted:
            click.echo(f"    {name}: +{added} ~{updated} -{deleted}")
