# Changelog

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
