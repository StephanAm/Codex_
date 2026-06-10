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
TAG_PREFIX="cartographer-v"

log() { echo "▶ [release] $*"; }
die() { echo "✗ [release] $*" >&2; exit 1; }

bump_patch() { IFS='.' read -r a b c <<< "$1"; echo "$a.$b.$((c + 1))"; }
bump_minor() { IFS='.' read -r a b c <<< "$1"; echo "$a.$((b + 1)).0"; }
bump_major() { IFS='.' read -r a b c <<< "$1"; echo "$((a + 1)).0.0"; }

# 1.2.3-rc.1 → 1.2.3rc1  |  1.2.3 → 1.2.3
to_pep440() { echo "$1" | sed 's/-rc\.\([0-9]*\)/rc\1/'; }

# Strip pre-release suffix: 1.2.3-rc.1 → 1.2.3
base_ver() { echo "${1%%-*}"; }

sync_files() {
    local ver="$1"
    local pep440; pep440="$(to_pep440 "$ver")"
    printf '%s\n' "$ver"    > "$REPO_DIR/VERSION"
    printf '%s\n' "$pep440" > "$REPO_DIR/VERSION.PEP440"
    sed -i "s/^version = \"[^\"]*\"/version = \"$pep440\"/"       "$REPO_DIR/pyproject.toml"
    sed -i "s/__version__ = \"[^\"]*\"/__version__ = \"$ver\"/"   "$REPO_DIR/src/cartographer/__init__.py"
    (cd "$WORKSPACE_ROOT" && uv lock --quiet)
}

stage_version_files() {
    git -C "$REPO_DIR" add \
        "$REPO_DIR/VERSION" \
        "$REPO_DIR/VERSION.PEP440" \
        "$REPO_DIR/pyproject.toml" \
        "$REPO_DIR/src/cartographer/__init__.py" \
        "$WORKSPACE_ROOT/uv.lock"
}

# ── 1. Clean working tree ─────────────────────────────────────────────────────
if ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; then
    die "Uncommitted changes detected. Commit or stash before releasing."
fi

# ── 2. Compute release version ────────────────────────────────────────────────
CURRENT="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"
BASE="$(base_ver "$CURRENT")"

LATEST_TAG="$(git -C "$REPO_DIR" tag --sort=-version:refname \
    | grep -E "^${TAG_PREFIX}[0-9]+\.[0-9]+\.[0-9]+$" | head -1 || true)"
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

# ── 3. Sync files to release version ─────────────────────────────────────────
log "Syncing version files to $RELEASE_VER..."
sync_files "$RELEASE_VER"

# ── 4. Generate changelog (stages CHANGELOG.md) ───────────────────────────────
log "Updating changelog..."
"$REPO_DIR/scripts/update_changelog.sh" "$RELEASE_VER"

# ── 5. Commit + tag ───────────────────────────────────────────────────────────
stage_version_files
git -C "$REPO_DIR" commit -m "Release cartographer $RELEASE_VER"
git -C "$REPO_DIR" tag "${TAG_PREFIX}${RELEASE_VER}"
log "Tagged ${TAG_PREFIX}${RELEASE_VER}"

# ── 6. Build gate ─────────────────────────────────────────────────────────────
log "Building Linux binary..."
if ! "$REPO_DIR/scripts/build_linux.sh"; then
    log "Build failed — rolling back..."
    git -C "$REPO_DIR" tag -d "${TAG_PREFIX}${RELEASE_VER}"
    git -C "$REPO_DIR" reset --hard HEAD~1
    die "Build failed. Rolled back to $CURRENT. Fix and retry."
fi

# ── 7. Bump to next rc ────────────────────────────────────────────────────────
NEXT_RC="$(bump_patch "$RELEASE_VER")-rc.1"
log "Bumping to $NEXT_RC..."
sync_files "$NEXT_RC"
stage_version_files
git -C "$REPO_DIR" commit -m "Bump cartographer version to $NEXT_RC"

# ── 8. Push branch + tag ──────────────────────────────────────────────────────
log "Pushing to origin..."
git -C "$REPO_DIR" push origin main
git -C "$REPO_DIR" push origin --tags

log "Released: $CURRENT → $RELEASE_VER → $NEXT_RC  (tag: ${TAG_PREFIX}${RELEASE_VER})"
