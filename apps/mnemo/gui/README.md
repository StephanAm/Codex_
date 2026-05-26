# Mnemo — desktop GUI

A Tauri desktop window wrapping a React/TypeScript frontend. The UI talks to a
local FastAPI server (part of the main Python package) over HTTP on port 8765.

**Design system:** all colour, typography, component, and copy rules are in
[`../../../designdocs/mnemo-design-system.md`](../../../designdocs/mnemo-design-system.md). Prompt that file
when making UI changes and follow every rule exactly.

## How to run

Run from anywhere — paths are derived from the script's location:

```bash
# Terminal 1 — Python API server
./apps/mnemo/gui/gui.sh api        # starts FastAPI on http://localhost:8765

# Terminal 2 — Tauri desktop window
./apps/mnemo/gui/gui.sh dev        # starts Vite + opens the Tauri window

# Build check (TypeScript + Vite, no Tauri)
./apps/mnemo/gui/gui.sh build

# Stop the API server
./apps/mnemo/gui/gui.sh kill
```

The `api` command runs `uv run --package mnemo uvicorn mnemo.api:app` from the
workspace root, picking up the shared `.venv`. The `dev` command requires
Rust/Cargo; see the workspace [`CLAUDE.md`](../../../CLAUDE.md) for one-time setup
instructions.

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
│   └── components/             # Mnemo-specific components — generic primitives
│       │                       # (TagBadge, TagReferencePicker, SyncButton)
│       │                       # live in @codex/ui (packages/ui/).
│       ├── NoteList.tsx        # left panel: search bar + scrollable list of notes
│       ├── NoteDetail.tsx      # right panel: read-only view of the selected note
│       ├── NoteEditor.tsx      # right panel: create / edit form (body + tag/reference pickers)
│       ├── SplashScreen.tsx    # startup screen: polls /health until backend is ready
│       └── ConfigPanel.tsx     # right panel: view/edit app config (default tags, sync adapter, sync path)
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
| `src/api.ts` | All HTTP calls to the Python backend. Also defines the shared `Note`, `Reference`, `Config`, and `Session` TypeScript interfaces. |
| `src/App.tsx` | Owns all top-level state (`notes`, `selected`, `mode`, `query`). Renders the header, `NoteList`, and the active right-panel component based on `mode` (`view` / `add` / `edit` / `config`). |
| `src/App.css` | Single stylesheet with CSS custom properties for colours/spacing. Badge colours (`--tag-bg`, `--ent-bg`, …) are defined here. |
| `src/components/NoteEditor.tsx` | Used for both create and edit. Accepts `initialBody`, `initialTags`, `initialReferences` props and calls `onSave(body, tags, references)` on submit. |
| `src-tauri/capabilities/default.json` | Controls which Tauri APIs the frontend can call (e.g. `http`, `shell`). Edit this if you need new native capabilities. |

## Architecture notes

- The frontend never imports from the Python package. All data access goes
  through the REST API (`src/api.ts → localhost:8765`).
- There is no client-side routing library — `App.tsx` uses a `mode` enum
  (`"view" | "add" | "edit" | "config"`) to switch between panels.
- Tags and references are treated symmetrically in the UI. Both are called
  "references" throughout the codebase.
