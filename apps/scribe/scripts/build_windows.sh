#!/usr/bin/env bash
# Builds a standalone Scribe binary for Windows via PyInstaller.
# Output: apps/scribe/build/scribe.exe

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
WORKSPACE_ROOT="$(cd "$REPO_DIR/../.." && pwd)"
BUILD_DIR="$REPO_DIR/build"
TMP_DIR="$BUILD_DIR/.tmp"

log() { echo "▶ $*"; }
die() { echo "✗ $*" >&2; exit 1; }

command -v uv >/dev/null || die "uv not found"

mkdir -p "$BUILD_DIR" "$TMP_DIR"

log "Installing Python dependencies..."
cd "$WORKSPACE_ROOT"
uv sync --all-packages

log "Freezing with PyInstaller..."

ENTRY_PY="$TMP_DIR/entry.py"
cat > "$ENTRY_PY" << 'PYEOF'
from scribe.cli import main
main()
PYEOF

uv run pyinstaller \
  --onefile \
  --name scribe \
  --distpath "$TMP_DIR/dist" \
  --workpath "$TMP_DIR/work" \
  --specpath "$TMP_DIR" \
  --collect-all scribe \
  --noconfirm \
  "$ENTRY_PY"

cp "$TMP_DIR/dist/scribe.exe" "$BUILD_DIR/scribe.exe"

rm -rf "$TMP_DIR"

log "Done → build/scribe.exe"
