# Mnemo_ — Context and Intent

> Prompt this file when working on any part of Mnemo_ to establish shared understanding of what the product is and what it is trying to do.

---

## What is Mnemo_?

Mnemo_ is a desktop application that houses a suite of focused personal productivity tools. It is built for people who think in text — developers, writers, anyone who lives in a terminal or wants a fast, keyboard-driven interface.

The name is short for *mnemonic* — the art of remembering. The tagline is: **Remember everything.**

Mnemo_ is the application shell. The tools and services that live inside it are:

| Name | Type | Function |
|---|---|---|
| **Stylus** | Tool | Fast capture — notes, thoughts, decisions, references |
| **Atlas** | Tool | Structured knowledge — pages and long-form content |
| **Bulletin** | Tool | Summaries — digest views over Stylus notes |
| **Cartographer** | Service | Vector indexing — semantic search across the corpus |

---

## Core philosophy

**Speed above all.** The friction of capturing a thought should be as close to zero as possible. If it takes more than a few keystrokes to record something, the thought gets lost. Every design and UX decision in Stylus should be evaluated against this.

**Plain text, always.** Notes are stored as plain text strings. There is no rich text, no markdown rendering, no formatting toolbar. Structure comes from a lightweight inline syntax that is readable as raw text.

**Search is the primary retrieval mechanism.** Notes are not organised into folders or hierarchies. Instead, they are tagged and filtered. Full-text search is always available. The mental model is: capture fast, find fast.

**Each tool does one thing well.** Feature additions should be evaluated critically per tool — every new concept added to the mental model is a cost. Tools are composable; they share a data layer but maintain clear boundaries.

---

## Stylus

Stylus is Mnemo_'s fast-capture note-taking tool. It is not a document editor, a wiki, or a project management tool. It is a fast, searchable log of thoughts, decisions, references, and observations. Notes are plain text. Structure is applied through inline syntax, not forms.

### Inline syntax

Notes support three types of inline annotations, parsed automatically from the body text:

| Syntax | Name | Purpose |
|---|---|---|
| `#TagName` | Tag | Categorise a note by topic, project, or type |
| `@PersonName` | Reference | Link a note to a person, team, or named reference |
| `~{YYYY-MM-DD}` | Date | Associate a note with a specific date or time |

Tags and references use CamelCase. They are stored lowercase in the database. Dates use the `~{...}` syntax and are rendered as human-readable labels in the GUI.

### Use cases

Stylus is designed for:

- **Meeting notes** — quick record of what was discussed, who was involved, what was decided
- **Decision log** — why was this approach chosen? what were the alternatives?
- **Reference capture** — a URL, a command, a snippet worth keeping
- **Daily log** — what happened today, what's outstanding, what needs to happen next
- **Thought capture** — an idea that should not be lost, captured before it evaporates

Stylus is not designed for:
- Long-form writing or documents (that is Atlas)
- Task management or to-do lists
- Structured data or tables
- Collaboration (it is a single-user tool with sync, not a shared workspace)

### Interfaces

Stylus is built in three layers, all sharing the same SQLite database:

| Interface | Status | Description |
|---|---|---|
| CLI (`note`) | Done | Click-based terminal commands for scripting and quick capture |
| TUI (`note-tui`) | Done | Interactive curses UI for keyboard-driven browsing and editing |
| GUI (inside Mnemo_) | In progress | Tauri + React desktop app; talks to the Python API over HTTP |

The CLI and TUI import directly from the Python store layer. The GUI is fully decoupled — it talks to a local FastAPI server (`api.py`) running on port 8765, which is the only Python module the frontend touches.

---

## Sync

Notes sync across devices via a pluggable adapter. Two adapters are supported:

- **Google Drive** — the default; uses a folder in the user's Drive
- **Local folder** — for syncing via a shared network drive or cloud-synced folder (e.g. Dropbox)

Sync is manual (push/pull), not continuous. A 3-way merge reconciles diverged databases.

---

## Design

The GUI follows a strict design system (`designdocs/mnemo-design-system.md`). Key constraints:

- One typeface: IBM Plex Mono
- Seven permitted colours, no others
- No drop shadows, gradients, glows, or blur
- No border-radius beyond 4px (except the app icon)
- Motion is minimal — only the text cursor blinks

The aesthetic is precise and monochrome with controlled colour pops. Retro-informed, not retro-themed. The product should feel engineered, not decorated.

---

## What Mnemo_ is not trying to be

- Notion, Obsidian, or any graph-based knowledge tool
- A replacement for a proper task manager
- A chat interface or AI-first product
- Cross-platform mobile (desktop and terminal only)
