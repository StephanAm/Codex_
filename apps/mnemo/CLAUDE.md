# CLAUDE.md — Mnemo

This file provides guidance to Claude Code (claude.ai/code) when working with the Mnemo app.

For workspace-wide rules see [`../../CLAUDE.md`](../../CLAUDE.md). For the shared data layer see [`../../packages/core/CLAUDE.md`](../../packages/core/CLAUDE.md). For user-facing docs see [`README.md`](README.md) and [`gui/README.md`](gui/README.md).

Feature requests and deferred ideas live in [`../../designdocs/wishlist.md`](../../designdocs/wishlist.md). Known bugs in [`../../designdocs/buglist.md`](../../designdocs/buglist.md).

## Application name

This application is called **Mnemo_**. The trailing underscore is part of the name, not punctuation — always written as `Mnemo_` in prose, `MNEMO_` as the wordmark. Short for mnemonic — the art of remembering.

Mnemo_ is the application shell. The note-taking tool inside it is called **Stylus**. Other tools: Atlas (structured knowledge), Bulletin (summaries). Cartographer is a background service for vector indexing.

Tagline: *"Remember everything."*

## What lives here vs. in `codex_core`

Mnemo-specific Python in `src/mnemo/`:

| Module | Role |
|---|---|
| `cli.py` | Click entry point (`note`) |
| `tui.py` | Curses TUI (`note-tui`); all UI state lives here |
| `api.py` | FastAPI server (`note-api`) — REST consumed by the GUI, port 8765 |
| `gui_cli.py` | GUI dev wrapper (`gui` script) |

Mnemo-specific React in `gui/src/`: `App.tsx`, `api.ts`, `App.css`, and all the domain components (`NoteDetail`, `NoteList`, `NoteEditor`, `ConfigPanel`, `SplashScreen`, `RecallSidebar`, `InstanceSidebar`, `InstanceDetail`, `KindDetail`).

Everything data-shaped — models, store, parser, dates, logger, session, sync — lives in [`codex_core`](../../packages/core/src/codex_core/). When you reach for a function that another app would plausibly want, lift it into `codex_core` first.

Generic UI primitives — `TagBadge`, `TagReferencePicker`, `SyncButton` — live in [`@codex/ui`](../../packages/ui/). When you build a primitive that isn't Mnemo-specific (no domain copy, no app-specific layout), put it there.

## Sync architecture

The full spec lives in [`../../designdocs/sync.md`](../../designdocs/sync.md). **Read it before working on any sync, merge, or storage-adapter feature.** Key points:

- Each device owns its own SQLite DB; sync is peer-to-peer via a shared storage location.
- The `StorageAdapter` protocol has two implementations: `GoogleDriveAdapter` and `LocalFolderAdapter`.
- Merge is tombstone-first, last-write-wins on `updated_at`.
- Instance Kinds and Instances sync fully — UUID + timestamp merge with tombstone tables, same pattern as notes.

## Kind and Instance domain model

The full spec lives in [`../../designdocs/things-and-instances.md`](../../designdocs/things-and-instances.md). **Read it before working on any Kind/Instance feature.** Key points:

- **Kind** — a user-defined common noun that classifies a named real-world subject (e.g. `Person`, `Team`, `Company`). This is what the code calls `Type`.
- **Instance** — a specific named subject that belongs to a Kind (e.g. `John Smith` of kind `Person`). An Instance cannot exist without a Kind.
- Instances connect to notes indirectly via `@reference` tokens — there is no direct note↔instance relationship.
- The word **"entity" must never appear in the UI**. It is an internal engineering term only.

### UI copy rules for Kind/Instance

| Context | Copy |
|---|---|
| Sidebar section heading | `KINDS` |
| Group heading in sidebar | Kind name, pluralised (e.g. `People`, `Teams`) — user supplies the plural |
| Create kind affordance | `+ new kind` |
| Create instance affordance | `+ new [kind name]` (e.g. `+ new person`) |
| Detail view metadata label | Kind name (e.g. `Person`) |

### Internal naming

The code uses `Type` (Python model / DB table `types`) for Kind, and `Instance` (Python model / DB table `instances`) for Instance. The design doc's internal naming table (`entity_type`/`entity`) predates the code rename and can be ignored.

## Design system

The full design system lives in [`../../designdocs/mnemo-design-system.md`](../../designdocs/mnemo-design-system.md). **When building any Mnemo UI, prompt that file and follow every rule exactly.** It is the single source of truth for colours, typography, layout, components, motion, and copy tone.

The shared `@codex/ui` package owns the design-system primitives (badges, buttons, picker, plus their CSS); Mnemo-specific layout sits on top in `gui/src/App.css`.

Key points:
- Wordmark: `MNEMO_` — trailing underscore is part of the mark, rendered in Cyan Pulse
- One typeface only: **IBM Plex Mono** (weights 400 and 500)
- Seven permitted colours — no others
- No drop shadows, gradients, glows, or blur
- No border-radius beyond 4px except on the app icon

## Platform targets

Mnemo must build and run correctly on both **Linux** and **Windows**. When writing scripts, paths, or system calls, account for both environments.

## Commands

Run from the workspace root (`/home/stephan/Code/codex/`):

```bash
uv sync --all-packages --extra google-drive  # install everything (incl. Google Drive)
uv run pytest                                # all tests
uv run pytest packages/core/tests/test_store.py::test_foo  # single test
uv run ruff check                            # lint
uv run ruff format                           # format
uv run mypy                                  # type check

uv run --package mnemo note --help           # CLI
uv run --package mnemo note-tui              # TUI
uv run --package mnemo note-api              # API server
```

### Running the GUI (two terminals)

```bash
# Terminal 1 — Python API server
./apps/mnemo/gui/gui.sh api               # FastAPI on http://localhost:8765

# Terminal 2 — Tauri desktop window
./apps/mnemo/gui/gui.sh dev               # requires Rust/Cargo

# Build check (TypeScript + Vite)
./apps/mnemo/gui/gui.sh build
```

Rust installation (one-time, if not already installed):
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# Also needed on Linux: libwebkit2gtk-4.1-dev librsvg2-dev
```

## Project purpose

Mnemo_ is a multi-tool desktop app. This repo currently implements Stylus (the note-taking tool) across three layers:

1. **CLI** (`note`) — done. Click-based commands: add, list, search, delete, references, config, session, sync.
2. **TUI** (`note-tui`) — done. Interactive curses UI with browse/add/edit/delete/search/config/session/sync.
3. **GUI** (inside Mnemo_) — in progress. Tauri + React desktop app in `gui/`. See [`gui/README.md`](gui/README.md) for structure and dev commands.

## Tag and reference syntax

Notes use two inline annotation types, parsed from the body text by [`codex_core.parser`](../../packages/core/src/codex_core/parser.py):

- **Tags** — `#ThisIsATag` — categorise a note (topic, project, type of entry, etc.)
- **References** — `@ThisIsAReference` — refer to a person, team, or named entity

Both use CamelCase with no spaces. They are stored lowercase in the DB regardless of how they are written.

## Key conventions

- Python layers that need data access (CLI, TUI, `api.py`) import from [`codex_core.store`](../../packages/core/src/codex_core/store.py) directly — never from `cli.py` or `tui.py`. The GUI is fully decoupled: it talks to `api.py` over HTTP; `api.py` is the only Python module the GUI touches.
- `store.py` functions accept an optional `db_path` parameter for test isolation.
- Tags and references are always stored lowercase; the parser normalises them.
- The session context (`codex_core.session`) is process-local (env-var backed) and is not persisted to the DB.
- The codebase uses "references" throughout — both internally and in the user-facing UI.

### Build artefacts

The `build/` directory under `apps/mnemo/` is the output location for both final and intermediary build artefacts. It is gitignored.
