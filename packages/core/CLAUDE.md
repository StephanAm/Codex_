# CLAUDE.md — `codex_core`

The shared data layer for every app in the monorepo. Today consumed by Mnemo; tomorrow by Lexis_ and Pragma_.

## What belongs here

A module belongs in `codex_core` if **at least two apps would want it** (or clearly will), and it has **no UI imports**. Anything CLI-, TUI-, or GUI-specific stays in the consuming app.

Current modules:

| Module | Role |
|---|---|
| `models.py` | `Note`, `Reference`, `Type` (Kind), `Instance` dataclasses |
| `db.py` | SQLite connection factory + schema migrations |
| `parser.py` | `#tag` / `@reference` extraction from free-form text |
| `dates.py` | `~{...}` date expression normalisation (see [`../../designdocs/dateparsingrules.md`](../../designdocs/dateparsingrules.md)) |
| `logger.py` | Structured `get_logger`; use instead of `print` |
| `session.py` | Process-local session context (env-var + tmpfile), auto-applies tags/refs |
| `store.py` | Primary data-access API — 40+ functions over the SQLite store |
| `sync/` | Peer-to-peer sync: adapter protocol + Google Drive + local-folder + merge |

## The `store.py` contract

`store.py` is the public API every app depends on. **Do not** break its function signatures lightly — at minimum search the workspace for callers before changing one. Every function accepts an optional `db_path` parameter for test isolation; new functions should follow the same convention.

## Hard rules

- **No app imports.** `codex_core` must never `import mnemo` (or any app). It is a leaf in the dependency graph.
- **No UI dependencies.** No FastAPI, no Click, no curses, no React. (FastAPI handlers live in `apps/<app>/api.py`.)
- **Runtime paths are stable.** `~/.note_taker/` and `/tmp/note-taker-session-*` are user-data paths and the on-disk session prefix. Do not rename — doing so would orphan user databases and live sessions. The Python package was renamed `note_taker` → `codex_core`; the runtime identifiers stayed put deliberately.

## Sync architecture

The full spec lives in [`../../designdocs/sync.md`](../../designdocs/sync.md). **Read it before working on any sync, merge, or storage-adapter feature.** Key points:

- Each device owns its own SQLite DB; sync is peer-to-peer via a shared storage location.
- The `StorageAdapter` protocol has two implementations: `GoogleDriveAdapter` and `LocalFolderAdapter`.
- Merge is tombstone-first, last-write-wins on `updated_at`.
- Instance Kinds and Instances sync fully — UUID + timestamp merge with tombstone tables, same pattern as notes.

## Kind / Instance domain model

The full spec lives in [`../../designdocs/things-and-instances.md`](../../designdocs/things-and-instances.md). The code uses `Type` (Python model / DB table `types`) for Kind, and `Instance` (Python model / DB table `instances`) for Instance.

## Tests

All core tests live in `tests/`. Run from the workspace root:

```bash
uv run pytest packages/core/tests/                 # core tests only
uv run pytest packages/core/tests/test_store.py    # one file
```
