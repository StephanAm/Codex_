set shell := ["bash", "-euo", "pipefail", "-c"]

# List all recipes
default:
    @just --list

# Install all Python and Node dependencies
install:
    uv sync --all-packages --extra google-drive --extra embeddings
    pnpm install

# ── Checks ────────────────────────────────────────────────────────────────────

# Lint with ruff
lint:
    uv run ruff check

# Format with ruff
fmt:
    uv run ruff format

# Type-check with mypy
typecheck:
    uv run mypy

# Run tests (extra args forwarded, e.g. `just test packages/core/tests/`)
test *args:
    uv run pytest {{args}}

# Run all checks: lint + typecheck + tests
check: lint typecheck test

# ── Mnemo_ ────────────────────────────────────────────────────────────────────

# Mnemo_ CLI (args forwarded, e.g. `just mnemo add "hello"`)
mnemo *args:
    uv run --package mnemo note {{args}}

# Mnemo_ TUI
mnemo-tui:
    uv run --package mnemo note-tui

# Mnemo_ API server (port 8765, with hot-reload)
mnemo-api:
    ./apps/mnemo/gui/gui.sh api

# Stop whatever is holding port 8765
mnemo-api-kill:
    ./apps/mnemo/gui/gui.sh kill

# Mnemo_ Tauri dev window (also starts Vite)
mnemo-dev:
    ./apps/mnemo/gui/gui.sh dev

# TypeScript + Vite production build (no AppImage)
mnemo-gui-build:
    ./apps/mnemo/gui/gui.sh build

# Build Mnemo_ AppImage (full: PyInstaller backend + Tauri)
mnemo-build:
    ./apps/mnemo/scripts/build_linux.sh

# Release Mnemo_ — bump can be patch / minor / major / X.Y.Z (default: patch)
mnemo-release bump="patch":
    ./apps/mnemo/scripts/release.sh {{bump}}

# ── Cartographer_ ─────────────────────────────────────────────────────────────

# Cartographer_ CLI (args forwarded, e.g. `just carto index`)
carto *args:
    uv run carto {{args}}

# Build Cartographer_ standalone binary
carto-build:
    ./apps/cartographer/scripts/build_linux.sh

# Release Cartographer_ — bump can be patch / minor / major / X.Y.Z (default: patch)
carto-release bump="patch":
    ./apps/cartographer/scripts/release.sh {{bump}}

# ── Scribe_ ───────────────────────────────────────────────────────────────────

# Scribe_ CLI (args forwarded, e.g. `just scribe ask "what is…"`)
scribe *args:
    uv run --package scribe scribe {{args}}

# Build Scribe_ standalone binary
scribe-build:
    ./apps/scribe/scripts/build_linux.sh

# Release Scribe_ — bump can be patch / minor / major / X.Y.Z (default: patch)
scribe-release bump="patch":
    ./apps/scribe/scripts/release.sh {{bump}}


# ── Bulk ───────────────────────────────────────────────────────────────────
release-all bump="patch":
    just mnemo-release {{bump}}
    just scribe-release {{bump}}
    just carto-release {{bump}}

build-all:
    just mnemo-build
    just scribe-build
    just carto-build