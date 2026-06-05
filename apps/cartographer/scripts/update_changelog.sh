#!/usr/bin/env bash
# Prepend a release entry to CHANGELOG.md for an explicit version.
# Stages CHANGELOG.md but does NOT commit — release.sh owns the commit.
# Usage: update_changelog.sh X.Y.Z
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHANGELOG="$REPO_DIR/CHANGELOG.md"
RELEASE_VER="${1:?Usage: update_changelog.sh X.Y.Z}"
TAG_PREFIX="cartographer-v"

log() { echo "▶ [changelog] $*"; }

DATE="$(date +%Y-%m-%d)"

PREV_TAG="$(git -C "$REPO_DIR" tag --sort=-version:refname \
    | grep -E "^${TAG_PREFIX}[0-9]+\.[0-9]+\.[0-9]+$" | head -1 || true)"

RANGE="${PREV_TAG:+$PREV_TAG..}HEAD"

COMMITS="$(git -C "$REPO_DIR" log "$RANGE" \
    --pretty=format:"- %s" \
    --no-merges \
    -- . \
    | grep -v '^- Bump cartographer version' \
    | grep -v '^- Release cartographer' \
    | grep -v '^- Update changelog' \
    || true)"

if [[ -z "$COMMITS" ]]; then
    log "No commits to log — skipping"
    exit 0
fi

TMP="$(mktemp)"
{
    head -2 "$CHANGELOG"
    printf '## [%s] — %s\n\n%s\n\n' "$RELEASE_VER" "$DATE" "$COMMITS"
    tail -n +3 "$CHANGELOG"
} > "$TMP"
mv "$TMP" "$CHANGELOG"

git -C "$REPO_DIR" add "$CHANGELOG"

COUNT="$(echo "$COMMITS" | wc -l | tr -d ' ')"
log "Prepended v$RELEASE_VER ($COUNT commits) to CHANGELOG.md"
