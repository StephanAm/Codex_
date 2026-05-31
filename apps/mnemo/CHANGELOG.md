# Changelog

## [1.4.0] — 2026-05-31

- feat: add AtlasSidebar and AtlasView components for managing and displaying nodes and pages
- Update documentation to reflect the correct naming convention for Mnemo_ and its tools
- Add toolbar with copy markdown functionality to BulletinView
- Add BulletinSidebar and BulletinView components with filtering functionality for notes
- Add InstancePicker component and integrate instance filtering in NoteList
- Add export script for exporting notes from SQLite to JSONL format

## [1.3.2] — 2026-05-26

- Remove version specification for pnpm action in Windows build workflow

## [1.3.1] — 2026-05-26

- Refactor permissions in settings.json to streamline Bash commands and remove obsolete entries
- Update release command documentation and add permission for Mnemo release script
- Add check script and documentation; update settings and CLI options
- Remove auto-commit and reminder scripts from Claude settings
- Format option help text for clarity in search command
- Fix Tauri build command in build_linux.sh to remove unnecessary dashes

## [1.3.0] — 2026-05-26

- Add mnemo-gui package with dependencies to Cargo.lock
- Port Mnemo into the codex monorepo
- Add export_kb_all function to export all knowledge base instances

## [1.2.7] — 2026-05-25

- Add new features for daily report generation and knowledge base export
- Add recall sidebar header and button for new pinned notes
- Set default time period to "today" in App component
- Remove outdated version test for __version__

## [1.2.6] — 2026-05-21

- Add mypy and pytest commands to stop hooks for enhanced checks
- Update mypy configuration and fix type ignore for Google Drive credentials
- Refactor code for consistency and readability
- Refactor code and update configurations for improved functionality and readability
- Add Windows build workflow for backend and frontend

## [1.2.5] — 2026-05-21

- Enhance instance management and YAML import functionality

## [1.2.4] — 2026-05-21

- Add deterministic changelog update script
- Add CHANGELOG.md

## [1.2.4] — 2026-05-21

- Add CHANGELOG.md

## [1.2.3] — 2026-05-21

- Sync kinds and instances across devices
- Add sync architecture doc and update CLAUDE.md

## [1.2.2] — 2026-05-21

- Load pinned notes during sync state updates in App component

## [1.2.1] — 2026-05-16

- Enhance note management features by adding pinning functionality to NoteEditor and NoteDetail components, and update sidebar layout in App component.

## [1.2.0] — 2026-05-14

- Add KindDetail component and integrate with InstanceDetail and InstanceSidebar
- Add instance detail view with Kind metadata label
- Add create affordances for kinds and instances in the sidebar
- Associate instances with @reference tokens via instance_references join table
- Use Kind name in empty group copy rather than generic "instances"
- Fix empty state copy to use "kinds" not "types"
- Add plural field to InstanceKind and use it for sidebar group headings
- Fix sidebar section heading to read "kinds" per spec
- Add Kind/Instance domain model with sidebar, API, and DB schema
- Refactor note entities to references across the application
- Refactor note detail actions with icon buttons and improve accessibility
- Enhance recall sidebar with drag-and-drop functionality and arrow key navigation
- Implement pinned notes feature with drag-and-drop reordering in recall sidebar
- Add recall sidebar component and enhance sidebar navigation shortcuts

## [1.1.1] — 2026-04-22

- Add backend lifecycle config flags to GUI
- Add release script to automate build, version bump, and push process
- Refactor NoteEditor to ensure body ends with a newline; add cursor positioning on edit

## [1.1.0] — 2026-04-18

- Refactor time period handling and update dropdown options for filtering notes
- Implement TODO tag parsing and normalization; update related tests
- Add clear button to TagEntityPicker and style adjustments for picker
- Add watermark and version display to the app interface
- Add watermark component to the editor background

## [1.0.0] — 2026-04-10

- Remove sync-on-exit behaviour
