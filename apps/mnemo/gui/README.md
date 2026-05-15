# GUI — note-taker desktop app

A Tauri desktop window wrapping a React/TypeScript frontend. The UI talks to a
local FastAPI server (part of the main Python package) over HTTP on port 8765.

## How to run

```bash
# Terminal 1 — Python API server
./gui/gui.sh api        # starts FastAPI on http://localhost:8765

# Terminal 2 — Tauri desktop window
./gui/gui.sh dev        # starts Vite + opens the Tauri window

# Build check (TypeScript + Vite, no Tauri)
./gui/gui.sh build

# Stop the API server
./gui/gui.sh kill
```

The `api` command runs `uvicorn note_taker.api:app` from the repo root using the
project's `.venv`. The `dev` command requires Rust/Cargo; see the top-level
CLAUDE.md for one-time setup instructions.

## Directory layout

```
gui/
├── gui.sh                  # dev helper: api | dev | build | kill
├── index.html              # Vite entry point
├── package.json
│
├── src/                    # React/TypeScript frontend
│   ├── main.tsx            # mounts <App /> into index.html
│   ├── App.tsx             # root component — layout, routing between modes, keyboard shortcuts
│   ├── App.css             # all styles (single stylesheet, CSS variables for theming)
│   ├── api.ts              # typed API client (fetch wrappers + shared interfaces)
│   │
│   └── components/
│       ├── NoteList.tsx        # left panel: search bar + scrollable list of notes
│       ├── NoteDetail.tsx      # right panel: read-only view of the selected note
│       ├── NoteEditor.tsx      # right panel: create / edit form (body + tag/entity pickers)
│       ├── TagEntityPicker.tsx # reusable dropdown for selecting tags or references
│       ├── TagBadge.tsx        # small coloured badge for a single tag or reference
│       ├── SyncButton.tsx      # header button that triggers Google Drive sync
│       └── ConfigPanel.tsx     # right panel: view/edit app config (default tags, sync folder)
│
└── src-tauri/              # Rust/Tauri shell
    ├── src/
    │   ├── main.rs         # binary entry point (delegates to lib.rs)
    │   └── lib.rs          # Tauri builder setup
    ├── Cargo.toml
    └── capabilities/
        └── default.json    # Tauri v2 capability/permission declarations
```

## Key files

| File | What it does |
|---|---|
| `src/api.ts` | All HTTP calls to the Python backend. Also defines the shared `Note`, `Entity`, `Config`, and `Session` TypeScript interfaces. |
| `src/App.tsx` | Owns all top-level state (`notes`, `selected`, `mode`, `query`). Renders the header, `NoteList`, and the active right-panel component based on `mode` (`view` / `add` / `edit` / `config`). |
| `src/App.css` | Single stylesheet with CSS custom properties for colours/spacing. Badge colours (`--tag-bg`, `--ent-bg`, …) are defined here. |
| `src/components/NoteEditor.tsx` | Used for both create and edit. Accepts `initialBody`, `initialTags`, `initialEntities` props and calls `onSave(body, tags, entities)` on submit. |
| `src-tauri/capabilities/default.json` | Controls which Tauri APIs the frontend can call (e.g. `http`, `shell`). Edit this if you need new native capabilities. |

## Architecture notes

- The frontend never imports from the Python package. All data access goes
  through the REST API (`src/api.ts → localhost:8765`).
- There is no client-side routing library — `App.tsx` uses a `mode` enum
  (`"view" | "add" | "edit" | "config"`) to switch between panels.
- Tags and references are treated symmetrically in the UI. Internally the
  Python layer calls them "entities"; the UI calls them "references". Both
  terms refer to the same thing.
