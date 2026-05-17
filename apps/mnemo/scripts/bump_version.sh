#!/usr/bin/env bash
# Manages semver tagging. Called by build scripts before building.
# VERSION (project root) is the single source of truth.
#
# Usage: bump_version.sh [patch|minor|major|X.Y.Z]
#
# With an argument, bumps to the specified type or version then tags.
# Without an argument, auto mode applies these rules:
#   1. Uncommitted changes → error.
#   2. Commits since last tag → bump PATCH in VERSION, sync all files, commit, tag.
#   3. No commits, tag ≠ VERSION → sync files, tag VERSION.
#   4. No commits, tag == VERSION → nothing to do.
#   5. No previous tag → sync files, tag VERSION.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUMP_ARG="${1:-}"

log() { echo "▶ [version] $*"; }
die() { echo "✗ [version] $*" >&2; exit 1; }

VERSION_FILE="$REPO_DIR/VERSION"

read_version()  { tr -d '[:space:]' < "$VERSION_FILE"; }
write_version() { printf '%s\n' "$1" > "$VERSION_FILE"; }

bump_patch() {
    local major minor patch
    IFS='.' read -r major minor patch <<< "$1"
    echo "$major.$minor.$((patch + 1))"
}

bump_minor() {
    local major minor patch
    IFS='.' read -r major minor patch <<< "$1"
    echo "$major.$((minor + 1)).0"
}

bump_major() {
    local major minor patch
    IFS='.' read -r major minor patch <<< "$1"
    echo "$((major + 1)).0.0"
}

sync_files() {
    local ver="$1"
    sed -i "s/^version = \"[^\"]*\"/version = \"$ver\"/"            "$REPO_DIR/pyproject.toml"
    sed -i "s/__version__ = \"[^\"]*\"/__version__ = \"$ver\"/"     "$REPO_DIR/src/note_taker/__init__.py"
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$ver\"/"       "$REPO_DIR/gui/src-tauri/tauri.conf.json"
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$ver\"/"       "$REPO_DIR/gui/package.json"
    uv sync --extra google-drive --quiet
    (cd "$REPO_DIR/gui" && npm install --silent)
}

commit_and_tag() {
    local ver="$1"
    local changed
    changed="$(git -C "$REPO_DIR" diff --name-only)"
    changed+="$(git -C "$REPO_DIR" diff --cached --name-only)"
    if [[ -n "$changed" ]]; then
        git -C "$REPO_DIR" add \
            "$VERSION_FILE" \
            "$REPO_DIR/pyproject.toml" \
            "$REPO_DIR/uv.lock" \
            "$REPO_DIR/src/note_taker/__init__.py" \
            "$REPO_DIR/gui/src-tauri/tauri.conf.json" \
            "$REPO_DIR/gui/package.json" \
            "$REPO_DIR/gui/package-lock.json"
        git -C "$REPO_DIR" commit -m "Bump version to $ver"
    fi
    git -C "$REPO_DIR" tag "v$ver"
    log "Tagged v$ver"
}

# ── Uncommitted changes check ─────────────────────────────────────────────────
if ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; then
    die "Uncommitted changes detected. Commit or stash before bumping."
fi

# ── Read current version ───────────────────────────────────────────────────────
CODE_VER="$(read_version)"
log "VERSION file: $CODE_VER"

# ── Explicit bump argument ─────────────────────────────────────────────────────
if [[ -n "$BUMP_ARG" ]]; then
    case "$BUMP_ARG" in
        patch)              NEW_VER="$(bump_patch "$CODE_VER")" ;;
        minor)              NEW_VER="$(bump_minor "$CODE_VER")" ;;
        major)              NEW_VER="$(bump_major "$CODE_VER")" ;;
        [0-9]*.[0-9]*.[0-9]*)  NEW_VER="$BUMP_ARG" ;;
        *)  die "Unknown argument '$BUMP_ARG'. Use patch, minor, major, or X.Y.Z." ;;
    esac
    log "$CODE_VER → $NEW_VER"
    write_version "$NEW_VER"
    sync_files "$NEW_VER"
    commit_and_tag "$NEW_VER"
    exit 0
fi

# ── Auto mode: find latest semver tag ────────────────────────────────────────
LATEST_TAG="$(git -C "$REPO_DIR" tag --sort=-version:refname \
    | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)"

# ── No previous tag ───────────────────────────────────────────────────────────
if [[ -z "$LATEST_TAG" ]]; then
    log "No previous tag — syncing files and tagging v$CODE_VER"
    sync_files "$CODE_VER"
    commit_and_tag "$CODE_VER"
    exit 0
fi

TAG_VER="${LATEST_TAG#v}"
log "Latest tag: $LATEST_TAG"

# ── Commits since last tag? ───────────────────────────────────────────────────
COMMITS_SINCE="$(git -C "$REPO_DIR" log "$LATEST_TAG..HEAD" --oneline)"

if [[ -n "$COMMITS_SINCE" ]]; then
    # Bump PATCH of whatever is in VERSION
    NEW_VER="$(bump_patch "$CODE_VER")"
    log "Commits found since $LATEST_TAG — bumping to $NEW_VER"
    write_version "$NEW_VER"
    sync_files "$NEW_VER"
    commit_and_tag "$NEW_VER"
elif [[ "$CODE_VER" != "$TAG_VER" ]]; then
    log "No new commits; VERSION ($CODE_VER) ≠ tag ($TAG_VER) — syncing and tagging v$CODE_VER"
    sync_files "$CODE_VER"
    commit_and_tag "$CODE_VER"
else
    log "Already at $LATEST_TAG with no new commits — nothing to do"
fi
