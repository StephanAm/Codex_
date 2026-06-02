# Changelog

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
