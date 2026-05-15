#!/usr/bin/env bash
# Helper script for GUI development commands.
# Usage: ./gui/gui.sh <command>
#   build   — TypeScript check + Vite production build
#   dev     — start Tauri dev window (also starts Vite)
#   api     — start the FastAPI backend on port 8765

set -euo pipefail

export NVM_DIR="$HOME/.nvm"
# shellcheck source=/dev/null
[[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh"
nvm use 24 --silent

export PATH="$HOME/.cargo/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

case "${1:-}" in
  build)
    cd "$SCRIPT_DIR"
    npm run build
    ;;
  dev)
    cd "$SCRIPT_DIR"
    npm run tauri dev
    ;;
  api)
    cd "$REPO_DIR"
    .venv/bin/uvicorn note_taker.api:app --host 127.0.0.1 --port 8765 --reload
    ;;
  *)
    echo "Usage: $0 {build|dev|api}" >&2
    exit 1
    ;;
esac
