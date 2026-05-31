from pathlib import Path

import click

from cartographer.config import (
    get_drive_folder,
    get_local_folder_path,
    get_mnemo_db_path,
    get_source_type,
    set_drive_folder,
    set_local_folder_path,
    set_mnemo_db_path,
    set_source_type,
)
from cartographer.db import connect, get_db_path
from cartographer.merge import MergeResult
from cartographer.sync import SyncReport, sync as do_sync


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """Cartographer — vector indexing service for the Codex workspace."""


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@cli.command()
def status() -> None:
    """Show mirror and indexing status."""
    conn = connect()
    meta = conn.execute("SELECT schema_version, created_at FROM db_meta").fetchone()
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
    Defaults to ~/.note_taker/notes.db.
    """
    if path is None:
        click.echo(get_mnemo_db_path())
        return
    set_mnemo_db_path(path)
    click.echo(f"mnemo db set to: {path}")


# ---------------------------------------------------------------------------
# index (stub)
# ---------------------------------------------------------------------------

@cli.command()
def index() -> None:
    """Build vector embeddings for all mirrored content."""
    click.echo("index: not yet implemented")


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
        ("notes",       result.notes_added,       result.notes_updated,       result.notes_deleted),
        ("kinds",       result.kinds_added,        result.kinds_updated,       result.kinds_deleted),
        ("instances",   result.instances_added,    result.instances_updated,   result.instances_deleted),
        ("atlas nodes", result.atlas_nodes_added,  result.atlas_nodes_updated, result.atlas_nodes_deleted),
        ("atlas pages", result.atlas_pages_added,  result.atlas_pages_updated, result.atlas_pages_deleted),
    ]
    for name, added, updated, deleted in pairs:
        if added or updated or deleted:
            click.echo(f"    {name}: +{added} ~{updated} -{deleted}")
