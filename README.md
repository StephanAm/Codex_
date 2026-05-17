# Mnemo

A tool for capturing, tagging, and searching plain-text notes, with Google Drive sync across devices. Interfaces: CLI, TUI, and a Tauri desktop GUI (in progress).

**Design system:** [`mnemo-design-system.md`](mnemo-design-system.md) — colours, typography, components, and copy rules for the GUI.

## Setup

```bash
uv sync                                    # core dependencies
uv sync --extra google-drive              # + Google Drive sync support
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

### Tags and entities

Notes are parsed for `#tags` and `@entities` automatically. Use them inline in any note body.

```bash
note add "Reviewed PR with @bob #code-review"
note list --tag code-review
note list --entity bob
```

### Session context

Apply tags/entities to all new notes in a shell session without typing them each time.

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

```
├── src/note_taker/
│   ├── cli.py          # Click entry point (`note` command)
│   ├── tui.py          # Curses TUI (`note-tui` command)
│   ├── api.py          # FastAPI server (`note-api` command, port 8765)
│   ├── store.py        # All DB reads/writes — primary API layer
│   ├── models.py       # Note and Entity dataclasses
│   ├── parser.py       # Extracts #tags and @entities from text
│   ├── session.py      # In-process session context (env-var backed)
│   ├── db.py           # SQLite connection and schema setup
│   ├── logger.py       # Structured logger (get_logger); use instead of print
│   └── sync/
│       ├── adapter.py        # Abstract sync adapter interface
│       ├── google_drive.py   # Google Drive implementation
│       ├── local_folder.py   # Local folder implementation
│       ├── device.py         # Stable per-device ID
│       └── merge.py          # 3-way merge logic
├── gui/                # Tauri + React desktop app — see gui/README.md
├── tests/
├── pyproject.toml
└── .github/workflows/  # CI
```

## Dev commands

```bash
uv run pytest                              # run all tests with coverage
uv run pytest tests/test_foo.py::test_bar  # run a single test
uv run ruff check                          # lint
uv run ruff format                         # format
uv run mypy                                # type check
```

## Logging

Use `get_logger` from `note_taker.logger` instead of `print`. Direct `print` calls are not allowed.

```python
from note_taker.logger import get_logger

log = get_logger(__name__)
log.info("started")
```

Console output shows a level icon, a colour-coded logger name, and the message. All logs are also written in ISO 8601 format to `app.log`.
