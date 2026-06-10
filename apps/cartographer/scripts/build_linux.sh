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
uv sync --all-packages

# uv omits the INSTALLER file from dist-info (it's optional per PEP 376), but
# PyInstaller's --collect-all requires it. Create missing ones before freezing.
find "$WORKSPACE_ROOT/.venv/lib" -name "*.dist-info" -type d | while read -r d; do
    [[ -f "$d/INSTALLER" ]] || printf 'uv\n' > "$d/INSTALLER"
done

# ── 2. Freeze with PyInstaller ────────────────────────────────────────────────
log "Freezing with PyInstaller..."

ENTRY_PY="$TMP_DIR/entry.py"
cat > "$ENTRY_PY" << 'PYEOF'
from cartographer.cli import cli
cli()
PYEOF

uv run pyinstaller \
  --onefile \
  --name carto \
  --distpath "$TMP_DIR/dist" \
  --workpath "$TMP_DIR/work" \
  --specpath "$TMP_DIR" \
  --collect-all cartographer \
  --collect-all fastembed \
  --collect-all google.auth \
  --collect-all google.oauth2 \
  --collect-all google_auth_oauthlib \
  --collect-all googleapiclient \
  --noconfirm \
  "$ENTRY_PY"

cp "$TMP_DIR/dist/carto" "$BUILD_DIR/carto"
chmod +x "$BUILD_DIR/carto"

# ── cleanup ───────────────────────────────────────────────────────────────────
rm -rf "$TMP_DIR"

# Verify the binary reports the expected version.
EXPECTED_VER="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"
BINARY_VER="$("$BUILD_DIR/carto" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+([.-]rc\.[0-9]+)?' | head -1)"
if [ "$BINARY_VER" != "$EXPECTED_VER" ]; then
    die "Version mismatch: binary reports '$BINARY_VER' but VERSION file says '$EXPECTED_VER'"
fi

log "Done → build/carto  ($BINARY_VER)"
