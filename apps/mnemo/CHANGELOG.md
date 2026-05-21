# Changelog

All notable changes to Mnemo are documented here. Versions follow [Semantic Versioning](https://semver.org/).

---

## [1.2.3] — 2026-05-21

### Added
- Kinds and Instances now sync across devices. Each record gets a stable UUID and timestamps; merge is tombstone-first, last-write-wins on `updated_at`. Name collisions between independently-created kinds are resolved with a UUID suffix.
- `designdocs/sync.md` — full sync architecture reference doc.

---

## [1.2.2] — 2026-05-21

### Fixed
- Pinned notes are now reloaded correctly after a sync pull.

---

## [1.2.1] — 2026-05-16

### Added
- Pin/unpin notes directly from the note editor and note detail view.

---

## [1.2.0] — 2026-05-14

### Added
- **Kinds and Instances** — define named categories (Kinds) and the specific people, teams, or things that belong to them (Instances). Accessible from a new KINDS section in the sidebar.
- Instance detail view with Kind metadata label.
- Create affordances for new kinds and instances from the sidebar.
- Instances link to notes via `@reference` tokens through the `instance_references` join table.
- Plural field on Kind, used for sidebar group headings (e.g. "People", "Teams").
- Recall sidebar with drag-and-drop reordering and arrow-key navigation.
- Pinned notes with drag-and-drop reordering in the recall sidebar.

### Changed
- Note entities renamed to references throughout (UI, API, DB).
- Note detail actions refactored to icon buttons.

### Fixed
- Sidebar section heading now reads "KINDS" per spec.
- Empty state copy uses "kinds" rather than "types".

---

## [1.1.1] — 2026-04-22

### Added
- Release script (`scripts/release.sh`) to automate build, version bump, and push.
- Backend lifecycle config flags exposed to the GUI.

### Fixed
- NoteEditor now ensures note body ends with a newline; cursor positioned correctly on edit.

---

## [1.1.0] — 2026-04-18

### Added
- `#TODO` tag parsing and normalisation.
- Watermark and version display in the app interface.
- Clear button on the tag/entity picker.

### Changed
- Time period handling and filter dropdown options refactored.

---

## [1.0.0] — 2026-04-10

### Changed
- Removed sync-on-exit behaviour.

---

*Earlier versions (0.x) were pre-release development iterations.*
