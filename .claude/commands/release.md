Run a full Mnemo release: build, commit pending changes, bump version, and push.

## Arguments

`$ARGUMENTS` may be `patch`, `minor`, `major` (default: `patch`), or an explicit version like `0.2.0`. Passed directly to `scripts/bump_version.sh`.

## Steps

Stop and report if any step fails.

### 1. Build

```bash
./gui/gui.sh build
```

### 2. Generate OpenAPI spec

```bash
uv run note-openapi > openapi.json
```

### 3. Commit pending changes

Check `git status`. If there are uncommitted changes, stage and commit them with a descriptive message summarising the work. If the working tree is already clean, skip this step.

### 4. Bump version and tag

```bash
./scripts/bump_version.sh ${ARGUMENTS:-patch}
```

This updates `VERSION`, `pyproject.toml`, `src/note_taker/__init__.py`, `gui/src-tauri/tauri.conf.json`, and `gui/package.json`, commits the bump, and creates a git tag.

### 5. Push branch and tags

```bash
git push origin main
git push origin --tags
```

### 6. Report

Print: previous version → new version, tag created.
