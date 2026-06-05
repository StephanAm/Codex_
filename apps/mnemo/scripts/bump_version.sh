#!/usr/bin/env bash
# Manually set the working version (e.g. to start a new minor or major cycle).
# Writes VERSION (semver) and VERSION.PEP440 (derived); commits the change.
# Usage: bump_version.sh X.Y.Z-rc.1   or   bump_version.sh X.Y.Z
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="$(cd "$REPO_DIR/../.." && pwd)"
NEW_VER="${1:?Usage: bump_version.sh X.Y.Z[-rc.N]}"

log() { echo "▶ [version] $*"; }
die() { echo "✗ [version] $*" >&2; exit 1; }

to_pep440() { echo "$1" | sed 's/-rc\.\([0-9]*\)/rc\1/'; }

if ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; then
    die "Uncommitted changes detected. Commit or stash before bumping."
fi

OLD_VER="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"
PEP440="$(to_pep440 "$NEW_VER")"

printf '%s\n' "$NEW_VER" > "$REPO_DIR/VERSION"
printf '%s\n' "$PEP440"  > "$REPO_DIR/VERSION.PEP440"
sed -i "s/^version = \"[^\"]*\"/version = \"$PEP440\"/"           "$REPO_DIR/pyproject.toml"
sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$NEW_VER\"/"     "$REPO_DIR/gui/src-tauri/tauri.conf.json"
sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$NEW_VER\"/"     "$REPO_DIR/gui/package.json"
(cd "$WORKSPACE_ROOT" && uv sync --all-packages --extra google-drive --quiet)
(cd "$WORKSPACE_ROOT" && pnpm install --silent)

git -C "$REPO_DIR" add \
    "$REPO_DIR/VERSION" \
    "$REPO_DIR/VERSION.PEP440" \
    "$REPO_DIR/pyproject.toml" \
    "$REPO_DIR/gui/src-tauri/tauri.conf.json" \
    "$REPO_DIR/gui/package.json" \
    "$WORKSPACE_ROOT/uv.lock" \
    "$WORKSPACE_ROOT/pnpm-lock.yaml"
git -C "$REPO_DIR" commit -m "Bump version to $NEW_VER"

log "$OLD_VER → $NEW_VER  (PEP 440: $PEP440)"
