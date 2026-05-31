#!/usr/bin/env bash
# Builds a standalone Cartographer binary for Linux via PyInstaller.
# Output: apps/cartographer/build/cartographer

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

# ── 1. Python dependencies ────────────────────────────────────────────────────
log "Installing Python dependencies..."
cd "$WORKSPACE_ROOT"
uv sync --all-packages --extra google-drive

# ── 2. Freeze with PyInstaller ────────────────────────────────────────────────
log "Freezing with PyInstaller..."

ENTRY_PY="$TMP_DIR/entry.py"
cat > "$ENTRY_PY" << 'PYEOF'
from cartographer.cli import cli
cli()
PYEOF

uv run pyinstaller \
  --onefile \
  --name cartographer \
  --distpath "$TMP_DIR/dist" \
  --workpath "$TMP_DIR/work" \
  --specpath "$TMP_DIR" \
  --collect-all cartographer \
  --noconfirm \
  "$ENTRY_PY"

cp "$TMP_DIR/dist/cartographer" "$BUILD_DIR/cartographer"
chmod +x "$BUILD_DIR/cartographer"

# ── cleanup ───────────────────────────────────────────────────────────────────
rm -rf "$TMP_DIR"

log "Done → build/cartographer"
