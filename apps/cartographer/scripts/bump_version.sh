#!/usr/bin/env bash
# Manually set the working version (e.g. to start a new minor or major cycle).
# Syncs VERSION, pyproject.toml, and __init__.py; commits the change.
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
sed -i "s/^version = \"[^\"]*\"/version = \"$NEW_VER\"/"        "$REPO_DIR/pyproject.toml"
sed -i "s/__version__ = \"[^\"]*\"/__version__ = \"$NEW_VER\"/" "$REPO_DIR/src/cartographer/__init__.py"
(cd "$WORKSPACE_ROOT" && uv sync --all-packages --quiet)

git -C "$REPO_DIR" add \
    "$REPO_DIR/VERSION" \
    "$REPO_DIR/pyproject.toml" \
    "$REPO_DIR/src/cartographer/__init__.py" \
    "$WORKSPACE_ROOT/uv.lock"
git -C "$REPO_DIR" commit -m "Bump cartographer version to $NEW_VER"

log "$OLD_VER → $NEW_VER"
