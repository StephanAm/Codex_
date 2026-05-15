#!/usr/bin/env bash
# Full production build: Python backend → PyInstaller sidecar → Tauri app.
# Run from anywhere; paths are derived from this script's location.
#
# Prerequisites:
#   uv sync --dev          (installs pyinstaller into .venv)
#   Rust/Cargo in PATH     (see CLAUDE.md for one-time setup)

set -euo pipefail

export NVM_DIR="$HOME/.nvm"
# shellcheck source=/dev/null
[[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh"
nvm use 24 --silent

export PATH="$HOME/.cargo/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
BINARIES_DIR="$SCRIPT_DIR/src-tauri/binaries"

TARGET=$(rustc -Vv | grep '^host' | cut -d' ' -f2)
echo "Target triple: $TARGET"

mkdir -p "$BINARIES_DIR"

# ── Step 1: Build Python backend with PyInstaller ─────────────────────────────
echo "Building Python backend..."
cd "$REPO_DIR"
.venv/bin/python -m PyInstaller \
  --onefile \
  --noconsole \
  --distpath "$BINARIES_DIR" \
  --workpath "$REPO_DIR/build/pyinstaller" \
  --specpath "$REPO_DIR/build/pyinstaller" \
  --name "backend-$TARGET" \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on \
  --collect-submodules note_taker \
  "$SCRIPT_DIR/backend_main.py"

echo "Backend binary: $BINARIES_DIR/backend-$TARGET"

# ── Step 2: Build Tauri app ───────────────────────────────────────────────────
echo "Building Tauri app..."
cd "$SCRIPT_DIR"
npm run tauri build

echo "Done."
