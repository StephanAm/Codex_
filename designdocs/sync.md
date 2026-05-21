# Mnemo Sync Design

This document describes how Mnemo synchronises data across multiple devices.

## Core model

Each device maintains its own SQLite database (`~/.note_taker/notes.db`). Sync works by uploading the entire local DB to a shared storage location and merging the DBs of all other known devices into the local copy. There is no authoritative server — every device is a peer.

A full sync (`POST /sync`) is always: **push first, then pull**. Push-only and pull-only variants also exist.

## Device identity

Every device gets a stable ID the first time it touches the config table:

```
{hostname[:16]}-{uuid[:8]}
```

e.g. `macbook-pro-a1b2c3d4`

The ID is stored in `config.device_id` and never changes. It is the filename used in the remote storage location: `{device_id}.db`.

Source: `sync/device.py` → `get_device_id()`

## Storage adapters

The `StorageAdapter` protocol (`sync/adapter.py`) defines three operations:

| Method | What it does |
|---|---|
| `upload(device_id, local_db)` | Write the local DB file to remote storage as `{device_id}.db` |
| `list_devices()` | Return all device IDs that have a DB in the shared location |
| `download(device_id)` | Fetch a remote DB as raw bytes |

Two implementations:

### `LocalFolderAdapter`

Reads/writes `.db` files to a local directory path. Useful for syncing across devices via a shared network drive or for testing without cloud credentials. Configured via `sync_local_folder_path` in config.

### `GoogleDriveAdapter`

Reads/writes to a named folder in Google Drive (default: `note-taker-sync`). Uses OAuth 2.0 — see the **Authentication** section below. Configured via `sync_google_drive_folder` in config.

The active adapter is controlled by the `sync_adapter` config key (`google_drive` or `local_folder`).

## Merge algorithm

`sync/merge.py` → `merge_remote(local_conn, remote_bytes)`

The merge is a **tombstone-first, last-write-wins** strategy operating at the note level.

### Step 1 — Apply tombstones

Remote `deleted_notes` rows are processed first. For each:

1. Delete the matching note from local `notes` if it exists.
2. Insert the tombstone into local `deleted_notes` (idempotent via `INSERT OR IGNORE`).

This ensures a deletion from any device propagates to all others and can never be reversed by a later pull.

### Step 2 — Merge notes

For each note in the remote DB (skipping any whose UUID is tombstoned locally):

- **Not present locally** → insert the note, copy its tags and references.
- **Present locally, remote `updated_at` is newer** → overwrite body, replace tags and references.
- **Present locally, local `updated_at` is newer or equal** → skip (local wins).

Conflict resolution is always last-write-wins based on ISO-8601 `updated_at` timestamps. There is no three-way merge of note content.

### Step 3 — Sync pins

Pins are stored as a JSON blob in `config.pins`. They are merged last-write-wins on `config.pins_updated_at`. If the remote timestamp is newer (or local has none), the remote `pins` and `pins_updated_at` values overwrite local.

## What is and is not synced

| Data | Synced | Notes |
|---|---|---|
| Notes (body, tags, references) | Yes | Full merge with tombstones |
| Note deletions | Yes | Via `deleted_notes` tombstone table |
| Pinned notes | Yes | Last-write-wins on `pins_updated_at` |
| Instance Kinds | Yes | UUID + last-write-wins merge with `deleted_instance_kinds` tombstones; name collisions get a UUID suffix |
| Instances | Yes | UUID + last-write-wins merge with `deleted_instances` tombstones; kind FK remapped via UUID lookup |
| Config / settings | No | Each device keeps its own settings |

## Tombstone tables

Three tombstone tables exist in the schema (`db.py`):

- `deleted_notes` — notes
- `deleted_instance_kinds` — kinds
- `deleted_instances` — instances

A tombstone is permanent: once a UUID appears in a tombstone table, that record is never re-imported by any future merge.

## Authentication (Google Drive)

`GoogleDriveAdapter` requires an OAuth 2.0 access token.

- `credentials.json` — downloaded from Google Cloud Console, placed at `~/.note_taker/credentials.json`. This is the OAuth client secret file, not a personal token.
- `token.json` — obtained and refreshed automatically, stored at `~/.note_taker/token.json`.

If no valid token exists, any adapter operation raises `AuthRequired`. The GUI surfaces this as a prompt to complete the OAuth flow via `POST /auth/google`. The CLI requires the user to run `note sync auth` (or equivalent) before syncing.

Token refresh is handled silently when the token is expired but has a valid refresh token.

## API endpoints

All sync operations are exposed through the FastAPI server (`api.py`):

| Endpoint | Description |
|---|---|
| `POST /sync` | Full sync: push then pull |
| `POST /sync/push` | Upload local DB only |
| `POST /sync/pull` | Download and merge all other devices only |
| `POST /auth/google` | Run Google Drive OAuth flow |

All sync endpoints return `{ "message": "...", "needs_auth": bool }`. When `needs_auth` is `true` the caller must direct the user through `POST /auth/google` before retrying.

## Configuration keys

All stored in the `config` table:

| Key | Default | Description |
|---|---|---|
| `device_id` | generated | Stable per-device identifier |
| `sync_adapter` | `google_drive` | Active adapter (`google_drive` \| `local_folder`) |
| `sync_google_drive_folder` | `note-taker-sync` | Google Drive folder name |
| `sync_local_folder_path` | *(none)* | Absolute path for the local folder adapter |
| `autosync_debounce_ms` | `5000` | Milliseconds after a note change before autosync fires |

## Sequence diagram — full sync

```
Device A                     Storage                    Device B
   │                            │                          │
   │── upload(A.db) ──────────► │                          │
   │                            │                          │
   │── list_devices() ─────────►│                          │
   │◄─ [A, B] ─────────────────│                          │
   │                            │                          │
   │── download(B.db) ─────────►│                          │
   │◄─ B.db bytes ─────────────│                          │
   │                            │                          │
   │  merge_remote(B.db)        │                          │
   │  (tombstones → notes → pins)                         │
```

If there are N other devices, Device A downloads and merges each one in sequence.

## Extending sync to new entity types

To add sync support for a new table (e.g. Instances):

1. Add a `uuid`, `created_at`, and `updated_at` column to the table in `db.py`.
2. Add a tombstone table (e.g. `deleted_instances`) in `db.py`.
3. Record deletions into the tombstone table in `store.py` (alongside the actual `DELETE`).
4. Add a merge block in `merge.py` following the same tombstone-first, last-write-wins pattern as notes.
