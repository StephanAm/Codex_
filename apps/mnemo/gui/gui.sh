#!/usr/bin/env bash
# Helper script for GUI development commands.
# Usage: ./gui/gui.sh <command>
#   api     — start the FastAPI backend on port 8765
#   kill    — stop whatever is listening on port 8765
#   dev     — start Tauri dev window (also starts Vite)
#   build   — TypeScript check + Vite production build

set -euo pipefail

export NVM_DIR="$HOME/.nvm"
# shellcheck source=/dev/null
[[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh"
nvm use 24 --silent

export PATH="$HOME/.cargo/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
PORT=8765

# Kill whatever process (uvicorn, frozen backend, anything) holds PORT.
kill_port() {
  local pid
  pid=$(lsof -ti :"$PORT" 2>/dev/null || true)
  if [[ -n "$pid" ]]; then
    kill "$pid" && echo "Stopped process $pid (was on port $PORT)." || echo "Failed to stop process $pid." >&2
  else
    echo "Nothing is listening on port $PORT."
  fi
}

case "${1:-}" in
  kill)
    kill_port
    ;;
  build)
    cd "$SCRIPT_DIR"
    npm run build
    ;;
  dev)
    cd "$SCRIPT_DIR"
    npm run tauri dev
    ;;
  api)
    # If the port is already occupied, kill the existing process first.
    existing=$(lsof -ti :"$PORT" 2>/dev/null || true)
    if [[ -n "$existing" ]]; then
      proc_name=$(ps -p "$existing" -o comm= 2>/dev/null || echo "unknown")
      echo "Port $PORT is held by '$proc_name' (pid $existing) — stopping it."
      kill "$existing" || true
      # Give the OS a moment to release the port.
      sleep 0.5
    fi
    cd "$REPO_DIR"
    .venv/bin/uvicorn note_taker.api:app --host 127.0.0.1 --port "$PORT" --reload
    ;;
  *)
    echo "Usage: $0 {api|kill|dev|build}" >&2
    exit 1
    ;;
esac
