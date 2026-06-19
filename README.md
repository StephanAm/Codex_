# Codex

A `uv` + `pnpm` monorepo. Three branded apps: **Mnemo_**, **Cartographer_**, and **Scribe_**.

---

## Apps

### Mnemo_
*Remember everything.*

A desktop application for personal knowledge work — notes, structured pages, and named subjects. Four tools in one shell:

| Tool | Purpose |
|---|---|
| **Stylus** | Fast-capture notes with inline `#tags`, `@references`, and `~{dates}` |
| **Atlas** | Hierarchical knowledge pages — the wiki to Stylus's journal |
| **Registry** | Kinds & Instances — named real-world subjects (people, projects, teams) |
| **Bulletin** | Digest views over Stylus notes |

Three interfaces: CLI (`note`), TUI (`note-tui`), and a Tauri + React desktop GUI. All share a single SQLite database. Syncs across devices via Google Drive or a local folder.

### Cartographer_
A background service that keeps a vector index of Mnemo_ notes and Atlas pages. Provides semantic search via embedding-based retrieval.

### Scribe_
A CLI that generates AI-written markdown documents from notes. Reads the Cartographer_ index, retrieves semantic context, and calls an LLM (Claude by default, Ollama supported) to produce a bulletin or to-do list.

---

## Build tools

| Tool | Purpose | Install |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python package and workspace manager (replaces pip/venv) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [pnpm](https://pnpm.io/) | Node package manager for the JS/TS workspace | `npm install -g pnpm` |
| **Python ≥ 3.11** | Required by all workspace members; uv manages the interpreter | via uv: `uv python install 3.11` |
| **Node.js** | Required for the Mnemo_ frontend (React + Vite) | [nodejs.org](https://nodejs.org/) |
| **Rust** (+ Cargo) | Required to build the Tauri desktop shell | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |

The following system libraries are also required **on Linux** to build the Tauri GUI:

```bash
sudo apt install libwebkit2gtk-4.1-dev librsvg2-dev
```

Python, Rust, and the system libraries are only needed if you are building the desktop GUI. The CLI, TUI, Cartographer_, and Scribe_ require only `uv`.

On Debian / Ubuntu / Mint, `setup-dev.sh` installs everything and is safe to re-run:

```bash
./setup-dev.sh
```

---

## Setup

Requires [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/).

```bash
uv sync --all-packages                       # Python — install all workspace members
uv sync --all-packages --extra google-drive  # + Google Drive sync support
pnpm install                                 # Node — install JS packages
```

One-time for the desktop GUI:
```bash
# Linux
sudo apt install libwebkit2gtk-4.1-dev librsvg2-dev
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

---

## Running

### Mnemo_ CLI / TUI

```bash
uv run --package mnemo note --help    # CLI
uv run --package mnemo note-tui       # interactive TUI
```

### Mnemo_ desktop GUI

```bash
./apps/mnemo/gui/gui.sh api           # terminal 1 — FastAPI on :8765
./apps/mnemo/gui/gui.sh dev           # terminal 2 — Tauri window
```

### Scribe_

```bash
scribe bulletin                       # today's notes → markdown bulletin
scribe bulletin --from 2025-07-01 --to 2025-07-15
scribe todo                           # #todo-tagged notes → action list
scribe config init                    # write default config to ~/.codex_/scribe/
```

---

## Dev

All commands from the workspace root:

```bash
uv run ruff check          # lint
uv run ruff format         # format
uv run mypy                # type-check
uv run pytest              # all tests

pnpm --filter ./apps/mnemo/gui build   # frontend build check
```

---

## Repo layout

```
codex/
├── apps/
│   ├── mnemo/             # Mnemo_ — CLI, TUI, Tauri GUI, FastAPI server
│   ├── cartographer/      # Cartographer_ — vector indexing service
│   └── scribe/            # Scribe_ — AI document generation CLI
├── packages/
│   ├── core/              # codex_core — shared Python (models, store, parser, sync)
│   └── ui/                # @codex/ui — shared React primitives + design-system CSS
├── designdocs/            # Architecture and design references
└── pyproject.toml         # uv workspace root
```

Key design references:

- [`designdocs/mnemo-context.md`](designdocs/mnemo-context.md) — what Mnemo_ is and why
- [`designdocs/mnemo-design-system.md`](designdocs/mnemo-design-system.md) — UI rules (colours, type, components)
- [`designdocs/atlas-design.md`](designdocs/atlas-design.md) — Atlas data model and Cartographer_ integration
- [`designdocs/registry-design.md`](designdocs/registry-design.md) — Kind / Instance domain model
- [`designdocs/scribe-design.md`](designdocs/scribe-design.md) — Scribe_ pipeline and CLI
- [`designdocs/sync.md`](designdocs/sync.md) — peer-to-peer sync architecture
