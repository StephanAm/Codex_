# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`codex` is a `uv` + `pnpm` monorepo. It ships **Mnemo_** today and will host two companion apps in the future — **Lexis_** (reporting) and **Pragma_** (to-dos) — that share Mnemo_'s data layer.

Mnemo_ is the application shell. Its current tools: **Stylus** (fast capture / notes), **Atlas** (structured knowledge), **Bulletin** (summaries). **Cartographer** is a background service for vector indexing.

```
codex/
├── apps/
│   └── mnemo/            # Mnemo_ app: CLI, TUI, Tauri+React GUI (Stylus tool)
├── packages/
│   ├── core/             # codex_core — shared Python (models, store, sync, parser)
│   └── ui/               # @codex/ui — shared React primitives + design-system CSS
├── designdocs/           # Cross-app design and reference docs
└── pyproject.toml        # uv workspace root (no [project], tooling config only)
```

Per-app docs live in [`apps/mnemo/CLAUDE.md`](apps/mnemo/CLAUDE.md). Per-package docs in [`packages/core/CLAUDE.md`](packages/core/CLAUDE.md).

## Workspace commands

All commands run from this directory (`/home/stephan/Code/codex/`).

```bash
# Python (uv workspace)
uv sync --all-packages                     # install everything into shared .venv
uv sync --all-packages --extra google-drive  # + Google Drive sync deps
uv run pytest                              # all tests, all packages
uv run ruff check                          # lint
uv run ruff format                         # format
uv run mypy                                # type check

# Node (pnpm workspace)
pnpm install                               # install all JS packages
pnpm --filter ./apps/mnemo/gui build       # build Mnemo's frontend
```

To run a workspace member's script, target the package:

```bash
uv run --package mnemo note --help
uv run --package mnemo note-tui
uv run --package mnemo note-api
```

## Architecture rule: no app → app, no core → app

- `packages/core` (`codex_core`) is the data layer. It must not import from any app.
- `packages/ui` (`@codex/ui`) is generic UI primitives. No Mnemo-specific layout or copy.
- Apps depend on packages, never on each other. If Lexis needs something from Mnemo, lift it into a package first.

## Design system

Mnemo_'s UI follows [`designdocs/mnemo-design-system.md`](designdocs/mnemo-design-system.md). The shared `@codex/ui` package implements the design-system primitives; app-level CSS (in `apps/<app>/gui/src/App.css`) layers Mnemo_-specific layout on top.

Key points (full rules in the design doc):
- Name: `Mnemo_` — trailing underscore is part of the name; wordmark is `MNEMO_` in Cyan Pulse
- One typeface only: **IBM Plex Mono** (weights 400 and 500)
- Seven permitted colours — no others
- No drop shadows, gradients, glows, or blur
- No border-radius beyond 4px except on the app icon

## Platform targets

This is a multi-platform project. All code must build and run correctly on both **Linux** and **Windows**. When writing scripts, paths, or system calls, account for both environments.

## Designdocs

Cross-app design references live in [`designdocs/`](designdocs/):

- [`mnemo-context.md`](designdocs/mnemo-context.md) — what Mnemo_ is and why
- [`mnemo-design-system.md`](designdocs/mnemo-design-system.md) — single source of truth for UI
- [`sync.md`](designdocs/sync.md) — peer-to-peer sync architecture
- [`things-and-instances.md`](designdocs/things-and-instances.md) — Kind / Instance domain model
- [`dateparsingrules.md`](designdocs/dateparsingrules.md) — `~{...}` date expression rules
- [`mnemo-mcp-design.md`](designdocs/mnemo-mcp-design.md) — MCP server design
- [`wishlist.md`](designdocs/wishlist.md) — deferred feature ideas
- [`buglist.md`](designdocs/buglist.md) — parked bugs

Feature requests and deferred ideas go in [`designdocs/wishlist.md`](designdocs/wishlist.md). Bugs that would derail current work go in [`designdocs/buglist.md`](designdocs/buglist.md).
