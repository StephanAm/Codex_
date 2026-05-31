# Changelog

## [1.0.0] — 2026-05-31

- feat: implement embedding backends and indexing pipeline
- feat: add Google Drive and local folder adapters for syncing device DBs

## [0.1.0] — 2026-05-31

- Initial implementation: self-contained SQLite mirror of Mnemo data (notes, kinds, instances, Atlas)
- Three sync sources: google_drive (default), local_folder, mnemo_local
- Read-only merge logic (tombstone-first, last-write-wins) adapted from codex_core
- CLI: status, sync pull/auth/config, index (stub)
