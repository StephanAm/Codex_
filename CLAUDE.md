# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`codex` is a `uv` + `pnpm` monorepo. It ships three branded apps: **Mnemo_**, **Cartographer_**, and **Scribe_**.

**Mnemo_** is the application shell with four tools: **Stylus** (fast capture / notes), **Atlas** (structured knowledge), **Bulletin** (summaries), **Registry** (Kinds & Instances). **Cartographer_** is a background service for vector indexing. **Scribe_** is a CLI tool that generates AI-written reports from Mnemo_ notes.

```
codex/
├── apps/
│   ├── mnemo/            # Mnemo_ app: CLI, TUI, Tauri+React GUI (Stylus tool)
│   ├── cartographer/     # Cartographer_ — vector indexing service
│   └── scribe/           # Scribe_ — AI report generation CLI (see designdocs/scribe-design.md)
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
- Apps depend on packages, never on each other. If one app needs something from another, lift it into a package first.

## Design system

Mnemo_'s UI follows [`designdocs/mnemo-design-system.md`](designdocs/mnemo-design-system.md). The shared `@codex/ui` package implements the design-system primitives; app-level CSS (in `apps/<app>/gui/src/App.css`) layers Mnemo_-specific layout on top.

Key points (full rules in the design doc):
- Trailing underscore is part of each app name; wordmarks: `MNEMO_` (Cyan Pulse), `CARTO_` (Cartographer_), `SCRIBE_` (Scribe_)
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
- [`registry-design.md`](designdocs/registry-design.md) — Registry tool: Kind / Instance domain model
- [`dateparsingrules.md`](designdocs/dateparsingrules.md) — `~{...}` date expression rules
- [`mnemo-mcp-design.md`](designdocs/mnemo-mcp-design.md) — MCP server design
- [`scribe-design.md`](designdocs/scribe-design.md) — Scribe design: pipeline, CLI, Cartographer subprocess contract, prompt design
- [`corpus-design.md`](designdocs/corpus-design.md) — Cartographer_ corpus: three content types, retrieval budgets, scoring, result assembly
- [`wishlist.md`](designdocs/wishlist.md) — deferred feature ideas
- [`buglist.md`](designdocs/buglist.md) — parked bugs

Feature requests and deferred ideas go in [`designdocs/wishlist.md`](designdocs/wishlist.md). Bugs that would derail current work go in [`designdocs/buglist.md`](designdocs/buglist.md).
