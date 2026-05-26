#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="$(cd "$REPO_DIR/../.." && pwd)"
BUMP_ARG="${1:-patch}"

log() { echo "▶ [release] $*"; }
die() { echo "✗ [release] $*" >&2; exit 1; }

# Step 1: Require clean working tree
if ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; then
    die "Uncommitted changes detected. Commit or stash before releasing."
fi

# Step 2: Build
log "Building GUI..."
"$REPO_DIR/gui/gui.sh" build

# Step 3: Generate OpenAPI spec (designdocs lives at the workspace root)
log "Generating OpenAPI spec..."
(cd "$WORKSPACE_ROOT" && uv run --package mnemo note-openapi) > "$WORKSPACE_ROOT/designdocs/openapi.json"

# Step 4: Commit OpenAPI spec if it changed
if ! git -C "$REPO_DIR" diff --quiet -- "$WORKSPACE_ROOT/designdocs/openapi.json"; then
    log "OpenAPI spec changed — committing..."
    git -C "$REPO_DIR" add "$WORKSPACE_ROOT/designdocs/openapi.json"
    git -C "$REPO_DIR" commit -m "Update OpenAPI spec"
fi

# Capture version before bump
PREV_VER="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"

# Step 5: Update changelog
log "Updating changelog..."
"$REPO_DIR/scripts/update_changelog.sh" "$BUMP_ARG"

# Step 6: Bump version and tag
log "Bumping version ($BUMP_ARG)..."
"$REPO_DIR/scripts/bump_version.sh" "$BUMP_ARG"

NEW_VER="$(tr -d '[:space:]' < "$REPO_DIR/VERSION")"

# Step 6: Push branch and tags
log "Pushing to origin..."
git -C "$REPO_DIR" push origin main
git -C "$REPO_DIR" push origin --tags

# Step 7: Report
echo ""
log "Released: $PREV_VER → $NEW_VER (tag: v$NEW_VER)"
