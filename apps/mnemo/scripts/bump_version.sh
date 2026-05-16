#!/usr/bin/env bash
# Manages semver tagging. Called by build scripts before building.
# VERSION (project root) is the single source of truth.
#
# Rules:
#   1. Uncommitted changes → error.
#   2. Commits since last tag → bump PATCH in VERSION, sync all files, commit, tag.
#   3. No commits, tag ≠ VERSION → sync files, tag VERSION.
#   4. No commits, tag == VERSION → nothing to do.
#   5. No previous tag → sync files, tag VERSION.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { echo "▶ [version] $*"; }
die() { echo "✗ [version] $*" >&2; exit 1; }

VERSION_FILE="$REPO_DIR/VERSION"

read_version() {
    tr -d '[:space:]' < "$VERSION_FILE"
}

write_version() {
    local ver="$1"
    printf '%s\n' "$ver" > "$VERSION_FILE"
}

bump_patch() {
    local ver="$1"
    local major minor patch
    IFS='.' read -r major minor patch <<< "$ver"
    echo "$major.$minor.$((patch + 1))"
}

sync_files() {
    local ver="$1"
    sed -i "s/^version = \"[^\"]*\"/version = \"$ver\"/"            "$REPO_DIR/pyproject.toml"
    sed -i "s/__version__ = \"[^\"]*\"/__version__ = \"$ver\"/"     "$REPO_DIR/src/note_taker/__init__.py"
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$ver\"/"       "$REPO_DIR/gui/src-tauri/tauri.conf.json"
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$ver\"/"       "$REPO_DIR/gui/package.json"
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
            "$REPO_DIR/src/note_taker/__init__.py" \
            "$REPO_DIR/gui/src-tauri/tauri.conf.json" \
            "$REPO_DIR/gui/package.json"
        git -C "$REPO_DIR" commit -m "Bump version to $ver"
    fi
    git -C "$REPO_DIR" tag "v$ver"
    log "Tagged v$ver"
}

# ── 1. Uncommitted changes check ──────────────────────────────────────────────
if ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; then
    die "Uncommitted changes detected. Commit or stash before building."
fi

# ── 2. Read version from VERSION file ─────────────────────────────────────────
CODE_VER="$(read_version)"
log "VERSION file: $CODE_VER"

# ── 3. Latest semver tag ──────────────────────────────────────────────────────
LATEST_TAG="$(git -C "$REPO_DIR" tag --sort=-version:refname \
    | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)"

# ── 4. No previous tag ────────────────────────────────────────────────────────
if [[ -z "$LATEST_TAG" ]]; then
    log "No previous tag — syncing files and tagging v$CODE_VER"
    sync_files "$CODE_VER"
    commit_and_tag "$CODE_VER"
    exit 0
fi

TAG_VER="${LATEST_TAG#v}"
log "Latest tag: $LATEST_TAG"

# ── 5. Commits since last tag? ────────────────────────────────────────────────
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
