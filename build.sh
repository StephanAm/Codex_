#!/usr/bin/env bash
# Build a Codex app for the target platform.
# Usage: ./build.sh <app> [linux|windows]
#   <app>      — mnemo, scribe, or cartographer
#   [platform] — linux (default) or windows

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "▶ [build] $*"; }
die() { echo "✗ $*" >&2; exit 1; }

APP="${1:-}"
PLATFORM="${2:-linux}"

[[ -n "$APP" ]] || die "App name required. Usage: ./build.sh <app> [linux|windows]"

AVAILABLE="$(ls "$SCRIPT_DIR/apps/" | tr '\n' ' ')"
[[ -d "$SCRIPT_DIR/apps/$APP" ]] || die "Unknown app: '$APP'. Available: $AVAILABLE"

BUILD_SCRIPT="$SCRIPT_DIR/apps/$APP/scripts/build_${PLATFORM}.sh"
[[ -f "$BUILD_SCRIPT" ]] || die "No build script for platform '$PLATFORM' in app '$APP'."

log "Building $APP for $PLATFORM..."
bash "$BUILD_SCRIPT"
