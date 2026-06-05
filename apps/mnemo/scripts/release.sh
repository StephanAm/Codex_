#!/usr/bin/env bash
# RC-based release flow:
#   patch  — strip rc suffix from VERSION, release that version
#   minor  — bump minor from last tag, release that version
#   major  — bump major from last tag, release that version
#   X.Y.Z  — release that exact version
# After a successful build the tag is pushed, triggering the CI Windows build.
# Usage: release.sh [patch|minor|major|X.Y.Z]  (default: patch)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="$(cd "$REPO_DIR/../.." && pwd)"
BUMP_ARG="${1:-patch}"
TAG_PREFIX="v"

log() { echo "▶ [release] $*"; }
die() { echo "✗ [release] $*" >&2; exit 1; }

bump_patch() { IFS='.' read -r a b c <<< "$1"; echo "$a.$b.$((c + 1))"; }
bump_minor() { IFS='.' read -r a b c <<< "$1"; echo "$a.$((b + 1)).0"; }
bump_major() { IFS='.' read -r a b c <<< "$1"; echo "$((a + 1)).0.0"; }

# Sync all release files (clean version only — tauri/npm require valid semver).
sync_release_files() {
    local ver="$1"
    printf '%s\n' "$ver" > "$REPO_DIR/VERSION"
    sed -i "s/^version = \"[^\"]*\"/version = \"$ver\"/"              "$REPO_DIR/pyproject.toml"
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$ver\"/"         "$REPO_DIR/gui/src-tauri/tauri.conf.json"
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$ver\"/"         "$REPO_DIR/gui/package.json"
    (cd "$WORKSPACE_ROOT" && uv sync --all-packages --extra google-drive --quiet)
    (cd "$WORKSPACE_ROOT" && pnpm install --silent)
}

# Sync only Python files for rc versions (tauri.conf.json rejects non-semver).
sync_rc_files() {
    local ver="$1"
    printf '%s\n' "$ver" > "$REPO_DIR/VERSION"
    sed -i "s/^version = \"[^\"]*\"/version = \"$ver\"/" "$REPO_DIR/pyproject.toml"
    (cd "$WORKSPACE_ROOT" && uv sync --all-packages --extra google-drive --quiet)
}

stage_release_files() {
    git -C "$REPO_DIR" add \
        "$REPO_DIR/VERSION" \
        "$REPO_DIR/pyproject.toml" \
        "$REPO_DIR/gui/src-tauri/tauri.conf.json" \
        "$REPO_DIR/gui/package.json" \
        "$WORKSPACE_ROOT/uv.lock" \
        "$WORKSPACE_ROOT/pnpm-lock.yaml"
}

stage_rc_files() {
    git -C "$REPO_DIR" add \
        "$REPO_DIR/VERSION" \
        "$REPO_DIR/pyproject.toml" \
        "$WORKSPACE_ROOT/uv.lock"
}

# ── 1. Clean working tree ─────────────────────────────────────────────────────
if ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; then
    die "Uncommitted changes detected. Commit or stash before releasing."
fi

# ── 2. Compute release version ────────────────────────────────────────────────
CURRENT="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"
BASE="${CURRENT%%rc*}"

LATEST_TAG="$(git -C "$REPO_DIR" tag --sort=-version:refname \
    | grep -E "^v[0-9]+\.[0-9]+\.[0-9]+$" | head -1 || true)"
LAST_VER="${LATEST_TAG#"$TAG_PREFIX"}"

case "$BUMP_ARG" in
    patch)
        RELEASE_VER="$BASE" ;;
    minor)
        [[ -n "$LAST_VER" ]] || die "No previous tag found — cannot compute minor bump."
        RELEASE_VER="$(bump_minor "$LAST_VER")" ;;
    major)
        [[ -n "$LAST_VER" ]] || die "No previous tag found — cannot compute major bump."
        RELEASE_VER="$(bump_major "$LAST_VER")" ;;
    [0-9]*.[0-9]*.[0-9]*)
        RELEASE_VER="$BUMP_ARG" ;;
    *)
        die "Unknown argument '$BUMP_ARG'. Use patch, minor, major, or X.Y.Z." ;;
esac

log "Releasing $RELEASE_VER  (current: $CURRENT)"

# ── 3. Regenerate OpenAPI spec ────────────────────────────────────────────────
log "Generating OpenAPI spec..."
(cd "$WORKSPACE_ROOT" && uv run --package mnemo note-openapi) > "$WORKSPACE_ROOT/designdocs/openapi.json"

if ! git -C "$REPO_DIR" diff --quiet -- "$WORKSPACE_ROOT/designdocs/openapi.json"; then
    log "OpenAPI spec changed — committing..."
    git -C "$REPO_DIR" add "$WORKSPACE_ROOT/designdocs/openapi.json"
    git -C "$REPO_DIR" commit -m "Update OpenAPI spec"
fi

# ── 4. Sync files to release version ─────────────────────────────────────────
log "Syncing version files to $RELEASE_VER..."
sync_release_files "$RELEASE_VER"

# ── 5. Generate changelog (stages CHANGELOG.md) ───────────────────────────────
log "Updating changelog..."
"$REPO_DIR/scripts/update_changelog.sh" "$RELEASE_VER"

# ── 6. Commit + tag ───────────────────────────────────────────────────────────
stage_release_files
git -C "$REPO_DIR" commit -m "Release Mnemo_ $RELEASE_VER"
git -C "$REPO_DIR" tag "${TAG_PREFIX}${RELEASE_VER}"
log "Tagged ${TAG_PREFIX}${RELEASE_VER}"

# ── 7. Build gate ─────────────────────────────────────────────────────────────
log "Building GUI..."
if ! "$REPO_DIR/gui/gui.sh" build; then
    log "Build failed — rolling back..."
    git -C "$REPO_DIR" tag -d "${TAG_PREFIX}${RELEASE_VER}"
    git -C "$REPO_DIR" reset --hard HEAD~1
    die "Build failed. Rolled back to $CURRENT. Fix and retry."
fi

# ── 8. Bump to next rc ────────────────────────────────────────────────────────
NEXT_RC="$(bump_patch "$RELEASE_VER")rc1"
log "Bumping to $NEXT_RC..."
sync_rc_files "$NEXT_RC"
stage_rc_files
git -C "$REPO_DIR" commit -m "Bump version to $NEXT_RC"

# ── 9. Push branch + tag ──────────────────────────────────────────────────────
log "Pushing to origin..."
git -C "$REPO_DIR" push origin main
git -C "$REPO_DIR" push origin --tags

log "Released: $CURRENT → $RELEASE_VER → $NEXT_RC  (tag: ${TAG_PREFIX}${RELEASE_VER})"
