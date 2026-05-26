# Mnemo

A tool for capturing, tagging, and searching plain-text notes, with Google Drive sync across devices. Interfaces: CLI, TUI, and a Tauri desktop GUI (in progress).

**Design system:** [`../../designdocs/mnemo-design-system.md`](../../designdocs/mnemo-design-system.md) — colours, typography, components, and copy rules for the GUI.

## Setup

Run from the `codex` workspace root (`/home/stephan/Code/codex/`):

```bash
uv sync --all-packages                     # install all workspace members
uv sync --all-packages --extra google-drive  # + Google Drive sync support
```

## Usage

### TUI (interactive)

```bash
note-tui
```

Key bindings: `a` add · `e`/Enter edit · `d` delete · `/` search · `s` session · `S` sync · `c` config · `q` quit

### CLI

```bash
# Add a note (inline, prompted, or piped)
note add "Discussed roadmap with @alice #planning"
echo "Quick thought" | note add

# List and search
note list
note list --tag planning --limit 50
note search "roadmap"

# Delete
note delete 42
```

### Tags and references

Notes are parsed for `#tags` and `@references` automatically. Use them inline in any note body.

```bash
note add "Reviewed PR with @bob #code-review"
note list --tag code-review
note list --reference bob
```

### Session context

Apply tags/references to all new notes in a shell session without typing them each time.

```bash
note session set --tag standup --mention alice
note session show
note session clear
```

### Sync

Two storage adapters are supported: **Google Drive** (default) and **local folder**.

```bash
note sync push          # upload this device's DB
note sync pull          # merge all other devices' DBs locally
note sync status        # show device ID and current adapter config

# Google Drive — place credentials.json from the Google Cloud Console in ~/.note_taker/
note sync config adapter google_drive
note sync config folder my-notes-folder

# Local folder
note sync config adapter local_folder
note sync config local-path /path/to/shared/folder
```

## Project structure

Mnemo lives inside the `codex` monorepo. The Mnemo-specific code is here under `apps/mnemo/`; shared data-layer code lives in [`packages/core/`](../../packages/core/) (the `codex_core` package), and shared React primitives in [`packages/ui/`](../../packages/ui/) (the `@codex/ui` package).

```
apps/mnemo/
├── src/mnemo/
│   ├── cli.py          # Click entry point (`note` command)
│   ├── tui.py          # Curses TUI (`note-tui` command)
│   ├── api.py          # FastAPI server (`note-api` command, port 8765)
│   └── gui_cli.py      # GUI dev wrapper (`gui` script)
├── gui/                # Tauri + React desktop app — see gui/README.md
├── tests/
├── scripts/            # Release & build helpers
├── pyproject.toml
├── VERSION
└── CHANGELOG.md
```

Shared modules used by Mnemo live in `codex_core` (under `packages/core/src/codex_core/`): `store.py`, `models.py`, `parser.py`, `dates.py`, `session.py`, `db.py`, `logger.py`, and the entire `sync/` subpackage.

## Dev commands

Run from the workspace root (`/home/stephan/Code/codex/`):

```bash
uv run pytest                                            # all tests, all packages
uv run pytest packages/core/tests/test_store.py::test_foo  # run a single test
uv run ruff check                                        # lint
uv run ruff format                                       # format
uv run mypy                                              # type check
```

## Logging

Use `get_logger` from `codex_core.logger` instead of `print`. Direct `print` calls are not allowed.

```python
from codex_core.logger import get_logger

log = get_logger(__name__)
log.info("started")
```

Console output shows a level icon, a colour-coded logger name, and the message. All logs are also written in ISO 8601 format to `app.log`.
