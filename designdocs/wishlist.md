# Wishlist

Ideas and feature requests that are worth building, but not right now. When a new idea comes up during active work, it gets parked here so it doesn't derail the current task.

Each entry should include a short description of what the feature is and why it would be valuable.

---

## #12 — Additional time filter options
The time filter dropdown is missing common periods. Add: Yesterday, This week, This month — alongside the existing options.

## ~~#11 — Clear all in tag/reference dropdowns~~ ✓
The Tags and References filter dropdowns need a "clear all" option to reset the selection in one click, rather than deselecting items one by one.

## #10 — Auto-tag TODO items
When saving a note, any `TODO:` text should be automatically interpreted as a `#TODO` tag, so the note is tagged without the user having to add it manually.

## ~~#9 — Add background~~ ✓
Add a background to the GUI.

## ~~#8 — Clickable hyperlinks~~ ✓
URLs in note bodies should be rendered as clickable links that open in the default browser. Reduces friction when notes contain references to external resources.

## #7 — Flag syntax (`!flags`)
Inline `!flag` annotations in note bodies (e.g. `!urgent`, `!blocked`) rendered in `--color-flag` (#FF9500). Would need parser support to extract flags like tags and entities, a `.flag` style in the renderer, and optionally a filter in the sidebar.

## ~~#6 — Enter to open note~~ ✓
Pressing `Enter` on a focused note in the list should open it in the editor. Pairs naturally with arrow key navigation (#5).

## ~~#5 — Arrow key navigation in note list~~ ✓
Allow moving up and down through the note list using the arrow keys, with the selected note updating as you go.

## ~~#4 — 'e' key leaks into editor~~ ✓
Pressing `e` to edit a note while the note list has focus incorrectly inserts the character into the editor. The shortcut should only fire when no editable element is focused.

## ~~#3 — Fix dropdown colours~~ ✓
The filter and search dropdowns don't fully follow the design system. Colours, borders, and focus states need to be brought in line with the rest of the UI.

## ~~#2 — Time tagging~~ ✓
A way to associate a duration or time reference with a note (e.g. a meeting time, a logged work period). Could be a structured field or a special tag syntax.

## ~~#1 — Split note~~ ✗
Ability to split a single note into two separate notes at a chosen point in the body. Useful when a note grows and naturally contains two distinct ideas.

Decided against — notes are intentionally atomic. If a note grows too large, the right move is to create a new one manually.
