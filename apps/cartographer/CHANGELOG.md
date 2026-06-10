# Changelog

## [1.1.8] — 2026-06-10

- Refactor Google Drive integration: streamline dependencies and update installation instructions

## [1.1.8] — 2026-06-10

- Add version verification for built binaries in build scripts
- Add missing INSTALLER file creation for PyInstaller compatibility
- Add instance property management commands to CLI
- Add codex-core dependency and update documentation for Cartographer DB interactions
- Add instance properties management with CRUD operations and merge support
- Add type ignore comment for Credentials instantiation in GoogleDriveAdapter
- Implement sync push functionality and add device ID retrieval in config

## [1.1.8] — 2026-06-10

- Add instance property management commands to CLI
- Add codex-core dependency and update documentation for Cartographer DB interactions
- Add instance properties management with CRUD operations and merge support
- Add type ignore comment for Credentials instantiation in GoogleDriveAdapter
- Implement sync push functionality and add device ID retrieval in config

## [1.1.7] — 2026-06-09

- Refactor optional dependencies in pyproject.toml and uv.lock, removing google-drive support

## [1.1.6] — 2026-06-09

- Add frontmatter option to bulletin generation and archive directory configuration

## [1.1.5] — 2026-06-05

- Add VERSION.PEP440; migrate version format to semver canonical
- Migrate release scripts to RC-based flow

## [1.1.4] — 2026-06-05

- Add version option to CLI for Cartographer

## [1.1.3] — 2026-06-05

- feat: enhance retrieval functions and add corpus design documentation

## [1.1.2] — 2026-06-04

- feat: implement 'scribe ask' command for question answering with context retrieval
- refactor: rename 'cartographer' to 'carto' for consistency across scripts and code
- fix: update script name from 'cartographer' to 'carto' for consistency
- Add copyright and license information to source files
- Refactor code for improved readability and consistency
- feat: migrate user data to new ~/.codex_ layout and update paths in configuration

## [1.1.1] — 2026-06-03

- fix(cartographer): bundle fastembed and Google Drive libs in binary

## [1.1.0] — 2026-06-02

- feat(scribe): implement bulletin generation with date range and context retrieval
- feat(retrieve): add retrieve command for semantically related chunk retrieval by note IDs
- fix(search): update candidate filtering to use final_score instead of similarity
- feat(atlas): Enhance AtlasPage model with tags, references, and date annotations

## [1.0.0] — 2026-05-31

- feat: implement embedding backends and indexing pipeline
- feat: add Google Drive and local folder adapters for syncing device DBs

## [0.1.0] — 2026-05-31

- Initial implementation: self-contained SQLite mirror of Mnemo data (notes, kinds, instances, Atlas)
- Three sync sources: google_drive (default), local_folder, Mnemo_local
- Read-only merge logic (tombstone-first, last-write-wins) adapted from codex_core
- CLI: status, sync pull/auth/config, index (stub)
