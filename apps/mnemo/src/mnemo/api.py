"""FastAPI REST layer — thin wrapper over store.py for the GUI."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .models import Note
from .session import clear_session_context, get_session_context, set_session_context
from .store import (
    add_note,
    delete_note,
    get_default_tags,
    get_sync_folder,
    list_entities,
    list_notes,
    list_tags,
    search_notes,
    set_default_tags,
    set_sync_folder,
    update_note,
)

app = FastAPI(title="note-taker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://localhost:5173", "tauri://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PORT = 8765


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
    }


class ConfigPayload(BaseModel):
    default_tags: list[str] | None = None
    sync_folder: str | None = None


@app.put("/config")
def set_config(payload: ConfigPayload) -> dict[str, Any]:
    if payload.default_tags is not None:
        set_default_tags(payload.default_tags)
    if payload.sync_folder is not None:
        set_sync_folder(payload.sync_folder)
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
def run_sync() -> dict[str, str]:
    return {"message": _do_sync()}


def _do_sync() -> str:
    from pathlib import Path

    from .db import connect, get_db_path
    from .sync.device import get_device_id
    from .sync.merge import merge_remote

    config_dir = Path.home() / ".note_taker"
    creds = config_dir / "credentials.json"
    if not creds.exists():
        return "Sync failed: credentials.json not found in ~/.note_taker/"
    try:
        from .sync.google_drive import GoogleDriveAdapter
        adapter = GoogleDriveAdapter(
            creds, config_dir / "token.json", folder_name=get_sync_folder()
        )
        device_id = get_device_id()
        db_path = get_db_path()
        adapter.upload(device_id, db_path)
        devices = [d for d in adapter.list_devices() if d != device_id]
        if not devices:
            return "Push complete — no other devices to pull from."
        local_conn = connect(db_path)
        added = updated = deleted = 0
        for d in devices:
            result = merge_remote(local_conn, adapter.download(d))
            added += result.added
            updated += result.updated
            deleted += result.deleted
        return f"Sync complete — {added} added, {updated} updated, {deleted} deleted."
    except Exception as exc:
        return f"Sync failed: {exc}"


# ── entry point ───────────────────────────────────────────────────────────────

def serve() -> None:
    uvicorn.run(app, host="127.0.0.1", port=PORT, reload=False)
