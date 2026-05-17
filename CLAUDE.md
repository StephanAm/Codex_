# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

For user-facing documentation see [`README.md`](README.md) (setup, usage, CLI reference, project structure) and [`gui/README.md`](gui/README.md) (GUI architecture, dev commands, component reference).

## Application name

This application is called **Mnemo**. Always capitalised, never with a full stop. Short for mnemonic — the art of remembering.

Tagline: *"Remember everything."*

## Design system

The full design system lives in [`mnemo-design-system.md`](mnemo-design-system.md). **When building any Mnemo UI, prompt that file and follow every rule exactly.** It is the single source of truth for colours, typography, layout, components, motion, and copy tone.

Key points:
- Wordmark: `MNEMO_` — trailing underscore is part of the mark, rendered in Cyan Pulse
- One typeface only: **IBM Plex Mono** (weights 400 and 500)
- Seven permitted colours — no others
- No drop shadows, gradients, glows, or blur
- No border-radius beyond 4px except on the app icon

## Platform targets

This is a multi-platform project. All code must build and run correctly on both **Linux** and **Windows**. When writing scripts, paths, or system calls, account for both environments.

## Project purpose

A note-taking tool built in layers:

1. **CLI** (`note`) — done. Click-based commands: add, list, search, delete, entities, config, session, sync.
2. **TUI** (`note-tui`) — done. Interactive curses UI with browse/add/edit/delete/search/config/session/sync.
3. **GUI** — in progress. Tauri + React desktop app in `gui/`. See [`gui/README.md`](gui/README.md) for structure, important files, and dev commands.

## Commands

```bash
uv sync --extra google-drive   # install all dependencies (incl. Google Drive)
uv run pytest                  # run all tests with coverage
uv run pytest tests/test_foo.py::test_bar  # run a single test
uv run ruff check              # lint
uv run ruff format             # format
uv run mypy                    # type check
```

### Running the GUI (two terminals)

```bash
# Terminal 1 — Python API server
./gui/gui.sh api               # starts FastAPI on http://localhost:8765

# Terminal 2 — Tauri desktop window
./gui/gui.sh dev               # requires Rust/Cargo installed

# Build check (TypeScript + Vite)
./gui/gui.sh build
```

Rust installation (one-time, if not already installed):
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# Also needed on Linux: libwebkit2gtk-4.1-dev librsvg2-dev
```

## Architecture

This is a `src/` layout package. Source lives under `src/note_taker/`; tests live under `tests/`. The package is installed in editable mode by `uv sync`, so imports resolve to the `src/` tree.

All tool configuration (pytest, ruff, mypy, coverage) is in `pyproject.toml`. Mypy runs in strict mode against `src/` only.

### Module overview

| Module | Role |
|---|---|
| `cli.py` | Click entry point for the `note` command |
| `tui.py` | Curses TUI entry point for `note-tui`; all UI state lives here |
| `store.py` | All DB reads/writes — the primary API layer used by both CLI and TUI |
| `models.py` | `Note` and `Entity` dataclasses |
| `parser.py` | Extracts `#tags` and `@entities` from free-form note text |
| `session.py` | In-process session context backed by env vars; auto-applies tags/entities to new notes |
| `db.py` | SQLite connection factory and schema migrations |
| `logger.py` | Structured logger (`get_logger`); use instead of `print` everywhere |
| `api.py` | FastAPI server — REST API consumed by the GUI, runs on port 8765 |
| `sync/adapter.py` | Abstract sync adapter interface |
| `sync/google_drive.py` | Google Drive implementation of the adapter |
| `sync/local_folder.py` | Local folder implementation of the adapter |
| `sync/device.py` | Generates and persists a stable per-device ID |
| `sync/merge.py` | 3-way merge logic for reconciling remote DBs into the local DB |

### Tag and reference syntax

Notes use two inline annotation types, parsed from the body text by `parser.py`:

- **Tags** — `#ThisIsATag` — categorise a note (topic, project, type of entry, etc.)
- **References** — `@ThisIsAReference` — refer to a person, team, or named entity

Both use CamelCase with no spaces. They are stored lowercase in the DB regardless of how they are written.

### Build artefacts

The `build/` directory is the output location for both final and intermediary build artefacts. It is gitignored.

### Key conventions

- Python layers that need data access (CLI, TUI, `api.py`) import from `store.py` directly — never from `cli.py` or `tui.py`. The GUI is fully decoupled: it talks to `api.py` over HTTP; `api.py` is the only Python module it touches.
- `store.py` functions accept an optional `db_path` parameter for test isolation.
- Tags and references are always stored lowercase; `parser.py` normalises them.
- The `session.py` context is process-local (env-var backed) and is not persisted to the DB.
- The codebase uses "entities" internally for what the user calls "references" — treat the terms as synonymous.

## Renaming the package

1. Rename `src/note_taker/` to `src/<newname>/`
2. Update `[project] name` and `[tool.hatch.build.targets.wheel] packages` in `pyproject.toml`
3. Update `--cov=note_taker` in `[tool.pytest.ini_options] addopts`
4. Update imports in `tests/`
