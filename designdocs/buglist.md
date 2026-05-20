# Buglist

Known bugs and defects that need fixing. When a bug is spotted during active work but fixing it would derail the current task, park it here.

Each entry should include a short description of what's broken and how to reproduce it.

---

## Recall sidebar: drag-to-reorder does not work

Dragging a pinned note in the recall sidebar has no effect — the order does not change. Likely caused by the browser treating the `draggable` attribute on `<li>` elements as conflicting with the click handler, or the `onDragOver` / `onDrop` events not firing correctly. Reproduce: pin two or more notes, switch to recall view, attempt to drag one up or down.

## Arrow key navigation ignores active sidebar

The up/down arrow key handler in `App.tsx` always navigates through `displayedNotes` (the log sidebar list), regardless of whether the recall sidebar is currently active. When the recall sidebar is shown, arrows should navigate through `pinnedNotes` instead. Reproduce: switch to the recall sidebar (⌘2), then press ↑ or ↓ — the selected note changes based on the log order rather than the recall order.
