"""FastAPI REST layer — thin wrapper over store.py for the GUI."""

from __future__ import annotations

import json
import os
import signal
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:
    from importlib.metadata import version as _pkg_version
    _VERSION = _pkg_version("note-taker")
except Exception:
    _VERSION = "unknown"
from pydantic import BaseModel, Field

from .models import Note
import truststore
truststore.inject_into_ssl()

from .logger import get_logger
from .session import clear_session_context, get_session_context, set_session_context
from .store import (
    add_note,
    delete_note,
    get_autosync_debounce_ms,
    get_note,
    get_default_tags,
    get_pins,
    get_pins_updated_at,
    get_sync_adapter,
    get_sync_folder,
    get_sync_local_path,
    list_entities,
    list_notes,
    list_tags,
    search_notes,
    set_autosync_debounce_ms,
    set_default_tags,
    set_pins,
    set_sync_adapter,
    set_sync_folder,
    set_sync_local_path,
    update_note,
)

PORT = 8765
_log = get_logger("api")
PID_FILE = Path.home() / ".note_taker" / "api.pid"


def _write_pid_file() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(json.dumps({"pid": os.getpid(), "port": PORT, "version": _VERSION}))


def _remove_pid_file() -> None:
    PID_FILE.unlink(missing_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    _write_pid_file()
    try:
        yield
    finally:
        _remove_pid_file()


app = FastAPI(title="note-taker API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/health", summary="Health check")
def health() -> dict[str, Any]:
    """Return the API status, process ID, and running version."""
    return {"status": "ok", "pid": os.getpid(), "version": _VERSION}


@app.post("/shutdown", summary="Shut down the API server")
def shutdown() -> dict[str, str]:
    """Gracefully stop the API server process. Used by the GUI on quit."""
    threading.Timer(0.1, lambda: signal.raise_signal(signal.SIGINT)).start()
    return {"message": "Shutting down"}


# ── serialisation ─────────────────────────────────────────────────────────────

def _note_dict(note: Note) -> dict[str, Any]:
    d = asdict(note)
    d["created_at"] = note.created_at.isoformat()
    d["updated_at"] = note.updated_at.isoformat()
    d["time_stamp"] = note.time_stamp.isoformat()
    return d


# ── response models ───────────────────────────────────────────────────────────

class NoteResponse(BaseModel):
    id: int = Field(..., description="Auto-incrementing integer primary key")
    uuid: str = Field(..., description="Stable UUID used for sync and conflict resolution")
    body: str = Field(..., description="Full plain-text note body, including any inline tags and references")
    tags: list[str] = Field(..., description="Tags parsed from the body (`#Tag`) plus any injected at creation, stored lowercase")
    entities: list[str] = Field(..., description="References parsed from the body (`@Name`) plus any injected at creation, stored lowercase")
    created_at: str = Field(..., description="ISO 8601 UTC timestamp of when the note was created")
    updated_at: str = Field(..., description="ISO 8601 UTC timestamp of the most recent edit")
    time_stamp: str = Field(..., description="ISO 8601 timestamp of the `~{date}` expression in the body, or equal to `created_at` if none was specified")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 42,
                "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "body": "Discussed caching strategy with @Alice — going with Redis. #Backend #Architecture ~{2026-05-18}",
                "tags": ["backend", "architecture"],
                "entities": ["alice"],
                "created_at": "2026-05-18T09:30:00+00:00",
                "updated_at": "2026-05-18T09:30:00+00:00",
                "time_stamp": "2026-05-18T00:00:00+00:00",
            }
        }
    }


# ── notes ─────────────────────────────────────────────────────────────────────

@app.get("/notes", summary="List or search notes", response_model=list[NoteResponse])
def get_notes(
    q: str | None = None,
    tag: str | None = None,
    entity: str | None = None,
) -> list[dict[str, Any]]:
    """Return a list of notes, optionally filtered or searched.

    - **q** — full-text search query; when provided, `tag` and `entity` are ignored
    - **tag** — filter by tag (lowercase, e.g. `work`)
    - **entity** — filter by referenced entity (lowercase, e.g. `alice`)

    Returns up to 500 notes ordered by creation date descending.
    """
    if q:
        notes = search_notes(q)
    else:
        notes = list_notes(tag=tag, entity=entity, limit=500)
    return [_note_dict(n) for n in notes]


@app.get("/notes/{note_id}", summary="Get a note by ID", response_model=NoteResponse)
def get_note_by_id(note_id: int) -> dict[str, Any]:
    """Return a single note by its integer ID.

    Raises **404** if no note with that ID exists.
    """
    note = get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note #{note_id} not found")
    return _note_dict(note)


class NoteBody(BaseModel):
    body: str
    tags: list[str] = []
    entities: list[str] = []


@app.post("/notes", status_code=201, summary="Create a note", response_model=NoteResponse)
def create_note(payload: NoteBody) -> dict[str, Any]:
    """Create a new note from a plain-text body.

    Tags (`#Tag`) and references (`@Name`) are parsed automatically from the body.
    Additional tags and entities can be injected via the `tags` and `entities` fields
    without embedding them in the body text.

    Returns the created note with its assigned ID and timestamps.
    """
    note = add_note(payload.body, extra_tags=payload.tags, extra_entities=payload.entities)
    return _note_dict(note)


@app.put("/notes/{note_id}", summary="Update a note", response_model=NoteResponse)
def edit_note(note_id: int, payload: NoteBody) -> dict[str, Any]:
    """Replace the body of an existing note and re-parse its tags and references.

    The full body must be supplied — this is a replace, not a patch.
    Raises **404** if no note with that ID exists.
    """
    note = update_note(note_id, payload.body, extra_tags=payload.tags, extra_entities=payload.entities)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note #{note_id} not found")
    return _note_dict(note)


@app.delete("/notes/{note_id}", status_code=204, summary="Delete a note")
def remove_note(note_id: int) -> None:
    """Permanently delete a note by ID.

    The deletion is recorded so it can be propagated during sync.
    Raises **404** if no note with that ID exists.
    """
    if not delete_note(note_id):
        raise HTTPException(status_code=404, detail=f"Note #{note_id} not found")


# ── tags & entities ───────────────────────────────────────────────────────────

@app.get("/tags", summary="List all tags")
def get_tags() -> list[str]:
    """Return a sorted list of all tags that appear on at least one note."""
    return list_tags()


@app.get("/entities", summary="List all entities")
def get_entities() -> list[dict[str, Any]]:
    """Return all referenced entities (people, teams, named things) across all notes."""
    return [asdict(e) for e in list_entities()]


# ── config ────────────────────────────────────────────────────────────────────

@app.get("/config", summary="Get configuration")
def get_config() -> dict[str, Any]:
    """Return the current Mnemo configuration, including sync settings and default tags."""
    return {
        "default_tags": get_default_tags(),
        "sync_folder": get_sync_folder(),
        "sync_adapter": get_sync_adapter(),
        "sync_local_path": get_sync_local_path(),
        "autosync_debounce_ms": get_autosync_debounce_ms(),
    }


class ConfigPayload(BaseModel):
    default_tags: list[str] | None = None
    sync_folder: str | None = None
    sync_adapter: str | None = None
    sync_local_path: str | None = None
    autosync_debounce_ms: int | None = None


@app.put("/config", summary="Update configuration")
def set_config(payload: ConfigPayload) -> dict[str, Any]:
    """Update one or more configuration values. Omitted fields are left unchanged.

    - **default_tags** — tags automatically applied to every new note
    - **sync_adapter** — `google_drive` or `local_folder`
    - **sync_folder** — Google Drive folder name (only used when adapter is `google_drive`)
    - **sync_local_path** — absolute path to the local sync folder (only used when adapter is `local_folder`)
    - **autosync_debounce_ms** — milliseconds to wait before triggering an autosync after a note change

    Returns the full updated configuration.
    """
    if payload.default_tags is not None:
        set_default_tags(payload.default_tags)
    if payload.sync_folder is not None:
        set_sync_folder(payload.sync_folder)
    if payload.sync_adapter is not None:
        try:
            set_sync_adapter(payload.sync_adapter)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.sync_local_path is not None:
        set_sync_local_path(payload.sync_local_path)
    if payload.autosync_debounce_ms is not None:
        try:
            set_autosync_debounce_ms(payload.autosync_debounce_ms)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return get_config()


# ── pins ──────────────────────────────────────────────────────────────────────

class PinsPayload(BaseModel):
    uuids: list[str]


class PinsResponse(BaseModel):
    notes: list[NoteResponse]
    updated_at: str


def _build_pins_response() -> dict[str, Any]:
    uuids = get_pins()
    updated_at = get_pins_updated_at()
    notes_by_uuid = {n.uuid: _note_dict(n) for n in list_notes(limit=10_000)}
    ordered = [notes_by_uuid[u] for u in uuids if u in notes_by_uuid]
    return {"notes": ordered, "updated_at": updated_at}


@app.get("/pins", summary="Get pinned notes in order")
def get_pins_endpoint() -> dict[str, Any]:
    """Return the ordered list of pinned notes as full note objects."""
    return _build_pins_response()


@app.put("/pins", summary="Set pinned note order")
def put_pins_endpoint(payload: PinsPayload) -> dict[str, Any]:
    """Replace the ordered list of pinned note UUIDs and persist with a new timestamp."""
    set_pins(payload.uuids)
    return _build_pins_response()


# ── session ───────────────────────────────────────────────────────────────────

@app.get("/session", summary="Get session context")
def get_session() -> dict[str, Any]:
    """Return the active session tags and entities.

    Session context is applied automatically to all notes created during the session.
    It is process-local and not persisted to the database.
    """
    tags, entities = get_session_context()
    return {"tags": tags, "entities": entities}


class SessionPayload(BaseModel):
    tags: list[str]
    entities: list[str]


@app.put("/session", summary="Set session context")
def set_session(payload: SessionPayload) -> dict[str, Any]:
    """Set the active session tags and entities.

    Any tags and entities supplied here will be automatically attached to every note
    created while the session is active.
    """
    set_session_context(payload.tags, payload.entities)
    return {"tags": payload.tags, "entities": payload.entities}


@app.delete("/session", status_code=204, summary="Clear session context")
def delete_session() -> None:
    """Clear the active session, removing any automatically applied tags and entities."""
    clear_session_context()


# ── sync ──────────────────────────────────────────────────────────────────────

@app.post("/sync", summary="Push and pull (full sync)")
def run_sync() -> dict[str, Any]:
    """Upload the local database to the configured sync target, then pull and merge changes from all other devices.

    Returns a result message and a `needs_auth` flag. When `needs_auth` is `true`,
    the user must complete Google Drive authorisation via `POST /auth/google` before syncing.
    """
    message, needs_auth = _do_sync()
    return {"message": message, "needs_auth": needs_auth}


@app.post("/sync/push", summary="Push local changes")
def run_push() -> dict[str, Any]:
    """Upload the local database to the configured sync target without pulling remote changes.

    Returns a result message and a `needs_auth` flag.
    """
    message, needs_auth = _do_push()
    return {"message": message, "needs_auth": needs_auth}


@app.post("/sync/pull", summary="Pull remote changes")
def run_pull() -> dict[str, Any]:
    """Download and merge databases from all other known devices without pushing local changes.

    Returns a result message and a `needs_auth` flag.
    """
    message, needs_auth = _do_pull()
    return {"message": message, "needs_auth": needs_auth}


def _build_adapter() -> Any:
    from .sync.adapter import StorageAdapter  # noqa: F401
    sync_adapter = get_sync_adapter()
    if sync_adapter == "local_folder":
        from .sync.local_folder import LocalFolderAdapter
        raw = get_sync_local_path()
        if not raw:
            raise ValueError("Sync failed: local folder path is not configured.")
        return LocalFolderAdapter(Path(raw))
    from .sync.google_drive import GoogleDriveAdapter
    config_dir = Path.home() / ".note_taker"
    return GoogleDriveAdapter(
        config_dir / "credentials.json",
        config_dir / "token.json",
        folder_name=get_sync_folder(),
    )


def _do_push() -> tuple[str, bool]:
    from .sync.adapter import AuthRequired
    from .sync.device import get_device_id
    from .db import get_db_path
    try:
        adapter = _build_adapter()
        adapter.upload(get_device_id(), get_db_path())
        return "Push complete.", False
    except AuthRequired:
        return "Google Drive authorization required.", True
    except Exception as exc:
        return f"Push failed: {exc}", False


def _do_pull() -> tuple[str, bool]:
    from .db import connect, get_db_path
    from .sync.adapter import AuthRequired
    from .sync.device import get_device_id
    from .sync.merge import merge_remote
    try:
        adapter = _build_adapter()
        device_id = get_device_id()
        devices = [d for d in adapter.list_devices() if d != device_id]
        if not devices:
            return "No other devices to pull from.", False
        local_conn = connect(get_db_path())
        added = updated = deleted = 0
        for d in devices:
            result = merge_remote(local_conn, adapter.download(d))
            added += result.added
            updated += result.updated
            deleted += result.deleted
        return f"Pull complete — {added} added, {updated} updated, {deleted} deleted.", False
    except AuthRequired:
        return "Google Drive authorization required.", True
    except Exception as exc:
        return f"Pull failed: {exc}", False


def _do_sync() -> tuple[str, bool]:
    from .db import connect, get_db_path
    from .sync.adapter import AuthRequired
    from .sync.device import get_device_id
    from .sync.merge import merge_remote

    try:
        from .sync.adapter import StorageAdapter
        sync_adapter = get_sync_adapter()
        adapter: StorageAdapter
        if sync_adapter == "local_folder":
            from .sync.local_folder import LocalFolderAdapter
            raw = get_sync_local_path()
            if not raw:
                return "Sync failed: local folder path is not configured.", False
            adapter = LocalFolderAdapter(Path(raw))
        else:
            from .sync.google_drive import GoogleDriveAdapter
            config_dir = Path.home() / ".note_taker"
            adapter = GoogleDriveAdapter(
                config_dir / "credentials.json",
                config_dir / "token.json",
                folder_name=get_sync_folder(),
            )
        device_id = get_device_id()
        db_path = get_db_path()
        adapter.upload(device_id, db_path)
        devices = [d for d in adapter.list_devices() if d != device_id]
        if not devices:
            return "Push complete — no other devices to pull from.", False
        local_conn = connect(db_path)
        added = updated = deleted = 0
        for d in devices:
            result = merge_remote(local_conn, adapter.download(d))
            added += result.added
            updated += result.updated
            deleted += result.deleted
        return f"Sync complete — {added} added, {updated} updated, {deleted} deleted.", False
    except AuthRequired:
        return "Google Drive authorization required.", True
    except Exception as exc:
        return f"Sync failed: {exc}", False


# ── auth ───────────────────────────────────────────────────────────────────────

@app.post("/auth/google", summary="Authorise Google Drive")
async def auth_google() -> dict[str, str]:
    """Run the Google Drive OAuth flow to obtain and store an access token.

    Requires `credentials.json` to be present at `~/.note_taker/credentials.json`.
    Download it from the Google Cloud Console under APIs & Services → Credentials → OAuth 2.0 Client ID.

    This call opens a browser window for the user to complete the OAuth consent flow.
    Raises **400** if `credentials.json` is missing, **500** if the flow fails.
    """
    import asyncio
    config_dir = Path.home() / ".note_taker"
    creds_path = config_dir / "credentials.json"
    token_path = config_dir / "token.json"
    if not creds_path.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                f"credentials.json not found at {creds_path}. "
                "Download it from Google Cloud Console "
                "(APIs & Services → Credentials → OAuth 2.0 Client ID)."
            ),
        )
    try:
        from .sync.google_drive import run_auth_flow
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_auth_flow, creds_path, token_path)
    except Exception as exc:
        _log.exception("Google auth flow failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"message": "Authorized"}


# ── entry point ───────────────────────────────────────────────────────────────

def serve() -> None:
    uvicorn.run(app, host="127.0.0.1", port=PORT, reload=False)


def export_openapi() -> None:
    print(json.dumps(app.openapi(), indent=2))
