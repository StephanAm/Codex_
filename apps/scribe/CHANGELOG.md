# Changelog

## [1.2.11] — 2026-06-10

- Add version verification for built binaries in build scripts

## [1.2.9] — 2026-06-09

- Capitalize kind directory names in registry and cli functions

## [1.2.8] — 2026-06-09

- Add registry sync command and data models for Kinds and Instances

## [1.2.7] — 2026-06-08

- Rename output files for bulletins and digests to include descriptive suffixes

## [1.2.6] — 2026-06-08

- Add frontmatter option to digest generation for YAML metadata
- Add frontmatter option to bulletin generation and archive directory configuration

## [1.2.5] — 2026-06-05

- Add VERSION.PEP440; migrate version format to semver canonical
- Migrate release scripts to RC-based flow

## [1.2.4] — 2026-06-05

- Add period option to bulletin and todo commands for date range selection

## [1.2.2] — 2026-06-05

- feat: add new Scribe commands for briefings, open items, patterns, and digests
- feat: enhance retrieval functions and add corpus design documentation

## [1.2.1] — 2026-06-04

- feat: implement 'scribe ask' command for question answering with context retrieval
- refactor: rename 'cartographer' to 'carto' for consistency across scripts and code
- Add copyright and license information to source files
- Refactor code for improved readability and consistency

## [1.2.0] — 2026-06-03

- feat: add 'todo' command to generate to-do lists from tagged notes

## [1.1.0] — 2026-06-03

- feat: add configuration commands for Scribe, including show and init
- feat: migrate user data to new ~/.codex_ layout and update paths in configuration
- feat: add installation script and bulletin generation script for scribe

## [1.0.1] — 2026-06-02

- fix(scribe): update build entry points to import main instead of cli

## [1.0.0] — 2026-06-02

- feat(scribe): remove outdated bulletin file for the period 2025-05-18 to 2026-06-02
- feat(scribe): add support for Claude backend and update bulletin generation with metadata
- feat(scribe): implement bulletin generation with date range and context retrieval
- feat(ollama): integrate Ollama backend with model support and error handling
- feat(retrieve): add retrieve command for semantically related chunk retrieval by note IDs
- feat(scribe): add Scribe CLI tool for AI report generation with initial setup and design documentation

## [0.1.0] — 2026-06-02

- Initial scaffold
