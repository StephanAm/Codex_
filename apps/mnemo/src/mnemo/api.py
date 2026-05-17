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
from pydantic import BaseModel

from .models import Note
import truststore
truststore.inject_into_ssl()

from .logger import get_logger
from .session import clear_session_context, get_session_context, set_session_context
from .store import (
    add_note,
    delete_note,
    get_autosync_debounce_ms,
    get_default_tags,
    get_sync_adapter,
    get_sync_folder,
    get_sync_local_path,
    list_entities,
    list_notes,
    list_tags,
    search_notes,
    set_autosync_debounce_ms,
    set_default_tags,
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
    PID_FILE.write_text(json.dumps({"pid": os.getpid(), "port": PORT}))


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

@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "pid": os.getpid()}


@app.post("/shutdown")
def shutdown() -> dict[str, str]:
    threading.Timer(0.1, lambda: signal.raise_signal(signal.SIGINT)).start()
    return {"message": "Shutting down"}


# ── serialisation ─────────────────────────────────────────────────────────────

def _note_dict(note: Note) -> dict[str, Any]:
    d = asdict(note)
    d["created_at"] = note.created_at.isoformat()
    d["updated_at"] = note.updated_at.isoformat()
    d["time_stamp"] = note.time_stamp.isoformat()
    return d


# ── notes ─────────────────────────────────────────────────────────────────────

@app.get("/notes")
def get_notes(
    q: str | None = None,
    tag: str | None = None,
    entity: str | None = None,
) -> list[dict[str, Any]]:
    if q:
        notes = search_notes(q)
    else:
        notes = list_notes(tag=tag, entity=entity, limit=500)
    return [_note_dict(n) for n in notes]


class NoteBody(BaseModel):
    body: str
    tags: list[str] = []
    entities: list[str] = []


@app.post("/notes", status_code=201)
def create_note(payload: NoteBody) -> dict[str, Any]:
    note = add_note(payload.body, extra_tags=payload.tags, extra_entities=payload.entities)
    return _note_dict(note)


@app.put("/notes/{note_id}")
def edit_note(note_id: int, payload: NoteBody) -> dict[str, Any]:
    note = update_note(note_id, payload.body, extra_tags=payload.tags, extra_entities=payload.entities)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note #{note_id} not found")
    return _note_dict(note)


@app.delete("/notes/{note_id}", status_code=204)
def remove_note(note_id: int) -> None:
    if not delete_note(note_id):
        raise HTTPException(status_code=404, detail=f"Note #{note_id} not found")


# ── tags & entities ───────────────────────────────────────────────────────────

@app.get("/tags")
def get_tags() -> list[str]:
    return list_tags()


@app.get("/entities")
def get_entities() -> list[dict[str, Any]]:
    return [asdict(e) for e in list_entities()]


# ── config ────────────────────────────────────────────────────────────────────

@app.get("/config")
def get_config() -> dict[str, Any]:
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


@app.put("/config")
def set_config(payload: ConfigPayload) -> dict[str, Any]:
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


# ── session ───────────────────────────────────────────────────────────────────

@app.get("/session")
def get_session() -> dict[str, Any]:
    tags, entities = get_session_context()
    return {"tags": tags, "entities": entities}


class SessionPayload(BaseModel):
    tags: list[str]
    entities: list[str]


@app.put("/session")
def set_session(payload: SessionPayload) -> dict[str, Any]:
    set_session_context(payload.tags, payload.entities)
    return {"tags": payload.tags, "entities": payload.entities}


@app.delete("/session", status_code=204)
def delete_session() -> None:
    clear_session_context()


# ── sync ──────────────────────────────────────────────────────────────────────

@app.post("/sync")
def run_sync() -> dict[str, Any]:
    message, needs_auth = _do_sync()
    return {"message": message, "needs_auth": needs_auth}


@app.post("/sync/push")
def run_push() -> dict[str, Any]:
    message, needs_auth = _do_push()
    return {"message": message, "needs_auth": needs_auth}


@app.post("/sync/pull")
def run_pull() -> dict[str, Any]:
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

@app.post("/auth/google")
async def auth_google() -> dict[str, str]:
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
