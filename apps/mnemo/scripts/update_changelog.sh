#!/usr/bin/env bash
# Prepends a new release entry to CHANGELOG.md.
# Reads VERSION to compute the new version (same bump logic as bump_version.sh).
# Usage: update_changelog.sh [patch|minor|major|X.Y.Z]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHANGELOG="$REPO_DIR/CHANGELOG.md"
BUMP_ARG="${1:-patch}"

log() { echo "▶ [changelog] $*"; }

CUR_VER="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"

bump_patch() { IFS='.' read -r a b c <<< "$1"; echo "$a.$b.$((c + 1))"; }
bump_minor() { IFS='.' read -r a b c <<< "$1"; echo "$a.$((b + 1)).0"; }
bump_major() { IFS='.' read -r a b c <<< "$1"; echo "$((a + 1)).0.0"; }

case "$BUMP_ARG" in
    patch)                 NEW_VER="$(bump_patch "$CUR_VER")" ;;
    minor)                 NEW_VER="$(bump_minor "$CUR_VER")" ;;
    major)                 NEW_VER="$(bump_major "$CUR_VER")" ;;
    [0-9]*.[0-9]*.[0-9]*) NEW_VER="$BUMP_ARG" ;;
    *) echo "✗ [changelog] Unknown bump arg: $BUMP_ARG" >&2; exit 1 ;;
esac

DATE="$(date +%Y-%m-%d)"

PREV_TAG="$(git -C "$REPO_DIR" tag --sort=-version:refname \
    | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)"

RANGE="${PREV_TAG:+$PREV_TAG..}HEAD"

COMMITS="$(git -C "$REPO_DIR" log "$RANGE" \
    --pretty=format:"- %s" \
    --no-merges \
    | grep -v '^- Bump version' \
    | grep -v '^- Update OpenAPI spec' \
    | grep -v '^- Update changelog' \
    || true)"

if [[ -z "$COMMITS" ]]; then
    log "No commits to log — skipping"
    exit 0
fi

# Prepend after "# Changelog\n" (line 1 + blank line 2; entries start at line 3)
TMP="$(mktemp)"
{
    head -2 "$CHANGELOG"
    printf '## [%s] — %s\n\n%s\n\n' "$NEW_VER" "$DATE" "$COMMITS"
    tail -n +3 "$CHANGELOG"
} > "$TMP"
mv "$TMP" "$CHANGELOG"

git -C "$REPO_DIR" add "$CHANGELOG"
git -C "$REPO_DIR" commit -m "Update changelog for v$NEW_VER"

COUNT="$(echo "$COMMITS" | wc -l | tr -d ' ')"
log "Prepended v$NEW_VER ($COUNT commits) to CHANGELOG.md"
