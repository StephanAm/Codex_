#!/usr/bin/env bash
# Builds a production AppImage for Linux.
# Run from the project root: ./build_linux.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUI_DIR="$REPO_DIR/gui"
TAURI_DIR="$GUI_DIR/src-tauri"
BUILD_DIR="$REPO_DIR/build"
TMP_DIR="$BUILD_DIR/.tmp"

log() { echo "▶ $*"; }
die() { echo "✗ $*" >&2; exit 1; }

# ── version ───────────────────────────────────────────────────────────────────
bash "$REPO_DIR/scripts/bump_version.sh"

# ── prerequisites ─────────────────────────────────────────────────────────────
command -v uv         >/dev/null || die "uv not found"
command -v mksquashfs >/dev/null || die "squashfs-tools not installed — run: sudo apt install squashfs-tools"

export PATH="$HOME/.cargo/bin:$PATH"
command -v cargo >/dev/null || die "cargo not found — install Rust: https://rustup.rs"

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
# shellcheck source=/dev/null
[[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh"
nvm use 24 --silent 2>/dev/null || true
command -v node >/dev/null || die "node not found"
command -v npm  >/dev/null || die "npm not found"

# ── setup ─────────────────────────────────────────────────────────────────────
TARGET_TRIPLE="$(rustc -vV | grep '^host:' | awk '{print $2}')"
mkdir -p "$BUILD_DIR" "$TMP_DIR"

log "Target: $TARGET_TRIPLE"

# ── 1. Python dependencies ────────────────────────────────────────────────────
log "Installing Python dependencies..."
cd "$REPO_DIR"
uv sync --extra google-drive

# ── 2. Freeze Python backend ──────────────────────────────────────────────────
log "Freezing Python backend with PyInstaller..."

ENTRY_PY="$TMP_DIR/backend_entry.py"
cat > "$ENTRY_PY" << 'PYEOF'
from note_taker.api import serve
serve()
PYEOF

uv run pyinstaller \
  --onefile \
  --name backend \
  --distpath "$TMP_DIR/dist" \
  --workpath "$TMP_DIR/work" \
  --specpath "$TMP_DIR" \
  --collect-all note_taker \
  --collect-all uvicorn \
  --collect-all fastapi \
  --noconfirm \
  "$ENTRY_PY"

# Stage where Tauri expects it
mkdir -p "$TAURI_DIR/binaries"
cp "$TMP_DIR/dist/backend" "$TAURI_DIR/binaries/backend-$TARGET_TRIPLE"
chmod +x "$TAURI_DIR/binaries/backend-$TARGET_TRIPLE"
log "Backend binary staged → src-tauri/binaries/backend-$TARGET_TRIPLE"

# ── 3. Node dependencies ──────────────────────────────────────────────────────
log "Installing Node dependencies..."
cd "$GUI_DIR"
npm install

# ── 4. Tauri build ────────────────────────────────────────────────────────────
log "Building Tauri AppImage..."
npm run tauri build -- --bundles appimage

# ── 5. Collect artefact ───────────────────────────────────────────────────────
APPIMAGE_SRC="$(find "$TAURI_DIR/target/release/bundle/appimage" -name "*.AppImage" | head -1)"
[[ -n "$APPIMAGE_SRC" ]] || die "AppImage not found in Tauri bundle output"
cp "$APPIMAGE_SRC" "$BUILD_DIR/"

# ── cleanup ───────────────────────────────────────────────────────────────────
rm -rf "$TMP_DIR"

log "Done → build/$(basename "$APPIMAGE_SRC")"
