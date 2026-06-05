#!/usr/bin/env bash
# Manually set the working version (e.g. to start a new minor or major cycle).
# For rc versions, only Python files are synced (tauri requires clean semver).
# For clean versions, all files including tauri.conf.json and package.json are synced.
# Usage: bump_version.sh X.Y.Zrc1   or   bump_version.sh X.Y.Z
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="$(cd "$REPO_DIR/../.." && pwd)"
NEW_VER="${1:?Usage: bump_version.sh X.Y.Z[rc1]}"

log() { echo "▶ [version] $*"; }
die() { echo "✗ [version] $*" >&2; exit 1; }

if ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; then
    die "Uncommitted changes detected. Commit or stash before bumping."
fi

OLD_VER="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"

printf '%s\n' "$NEW_VER" > "$REPO_DIR/VERSION"
sed -i "s/^version = \"[^\"]*\"/version = \"$NEW_VER\"/" "$REPO_DIR/pyproject.toml"
(cd "$WORKSPACE_ROOT" && uv sync --all-packages --extra google-drive --quiet)

FILES=(
    "$REPO_DIR/VERSION"
    "$REPO_DIR/pyproject.toml"
    "$WORKSPACE_ROOT/uv.lock"
)

# Only sync tauri/npm files for clean semver versions.
if [[ ! "$NEW_VER" =~ rc ]]; then
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$NEW_VER\"/" "$REPO_DIR/gui/src-tauri/tauri.conf.json"
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$NEW_VER\"/" "$REPO_DIR/gui/package.json"
    (cd "$WORKSPACE_ROOT" && pnpm install --silent)
    FILES+=(
        "$REPO_DIR/gui/src-tauri/tauri.conf.json"
        "$REPO_DIR/gui/package.json"
        "$WORKSPACE_ROOT/pnpm-lock.yaml"
    )
fi

git -C "$REPO_DIR" add "${FILES[@]}"
git -C "$REPO_DIR" commit -m "Bump version to $NEW_VER"

log "$OLD_VER → $NEW_VER"
