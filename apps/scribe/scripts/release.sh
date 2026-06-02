#!/usr/bin/env bash
# Full release: build → changelog → version bump → push.
# Usage: release.sh [patch|minor|major|X.Y.Z]  (default: patch)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUMP_ARG="${1:-patch}"

log() { echo "▶ [release] $*"; }
die() { echo "✗ [release] $*" >&2; exit 1; }

# ── 1. Require clean working tree ─────────────────────────────────────────────
if ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; then
    die "Uncommitted changes detected. Commit or stash before releasing."
fi

# ── 2. Build ──────────────────────────────────────────────────────────────────
log "Building..."
"$REPO_DIR/scripts/build_linux.sh"

PREV_VER="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"

# ── 3. Update changelog ───────────────────────────────────────────────────────
log "Updating changelog..."
"$REPO_DIR/scripts/update_changelog.sh" "$BUMP_ARG"

# ── 4. Bump version and tag ───────────────────────────────────────────────────
log "Bumping version ($BUMP_ARG)..."
"$REPO_DIR/scripts/bump_version.sh" "$BUMP_ARG"

NEW_VER="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"

# ── 5. Push branch and tags ───────────────────────────────────────────────────
log "Pushing to origin..."
git -C "$REPO_DIR" push origin main
git -C "$REPO_DIR" push origin --tags

echo ""
log "Released: $PREV_VER → $NEW_VER (tag: scribe-v$NEW_VER)"
