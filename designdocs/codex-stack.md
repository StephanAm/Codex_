# The Codex Stack

> A personal intelligence system built in layers. Each layer has a single responsibility. Each feeds the next.

---

## Philosophy

The stack is built on a simple principle: capture everything, synthesise progressively. Raw signal at the bottom, refined intelligence at the top. No layer does more than its job. No magic, no inference without instruction.

---

## The Layers

### Mnemo_
**Role:** Capture and store.

The source of truth. Four tools sharing one SQLite database:

- **Stylus** — fast capture. A personal log of notes: atomic, timestamped, plain text. Structure comes from inline syntax: `#tags`, `@references`, `~dates`.
- **Atlas** — structured knowledge. A hierarchy of curated, long-lived pages. The encyclopedia to Stylus's journal.
- **Registry** — named subjects. Kinds define categories (Person, Team, Project); Instances name specific things (Alice Smith, Engineering, PBHL).
- **Bulletin** — summaries. Digest views over Stylus notes.

- Stack: Tauri + React (GUI), FastAPI on port 8765, SQLite
- Sync: Google Drive or local folder, tombstone-first, last-write-wins
- MCP server exposes read-only access to external LLM clients

---

### Cartographer_
**Role:** Retrieve over Mnemo_.

The RAG pipeline over Mnemo_'s data. Maintains its own embeddings (local via Ollama) as an extension of the Mnemo_ database schema. An independent sync peer — not a sidecar.

Retrieval is hybrid: semantic search over note bodies and Atlas page bodies, combined with exact-match structured filters on tags, references, and Instance context. Tags and references are never embedded — they are structured filters only.

Annotation inheritance (e.g. Atlas page hierarchy) is a Cartographer_ concern, not a UI concern.

---

### Scribe_
**Role:** Synthesise over Mnemo_ via Cartographer_.

A CLI tool. Orchestrates Cartographer_'s retrieval and an LLM backend to produce written outputs from the raw log. Output is plain text to stdout or file. Designed to be composed via Just recipes and scheduled as cron jobs.

**Commands:**

| Command | Purpose |
|---|---|
| `scribe ask "<question>"` | Ad-hoc retrieval and synthesis. Answers a specific question against the full log and KB. |
| `scribe bulletin` | Deduplicated bullet-list summary of all notes in a date range. |
| `scribe todo` | Numbered action-item list extracted from `#todo`-tagged notes in a date range. |
| `scribe brief @Reference` | Person or project briefing. Synthesises all relevant notes and KB context into a coherent narrative. Run before a 1:1 or meeting. |
| `scribe open-items` | Extracts explicit and implicit commitments, follow-ups, and unresolved questions from recent notes. |
| `scribe patterns` | Analyses a note corpus over a time window for recurring themes, sentiment shifts, and persistent blockers. |
| `scribe digest` | Structured summary of activity over a time window, grouped by team, project, or tag. The reporting-up tool. |
| `scribe config` | View or initialise Scribe_ configuration. |

**Common flags:** `--date`, `--from`, `--to`, `--output`, `--top-k`, `--backend`, `--dry-run`

Scribe_ writes its output to the Archive — a directory of dated markdown files. It does not own the Archive; it simply writes to it.

---

### The Archive
**Role:** Structured, versioned intelligence.

A directory of dated markdown files produced by Scribe_. Plain files. No database, no special format. Open to any tool that can read text.

```
archive/
├── digests/
│   ├── 2026-W23-weekly.md
│   └── 2026-W22-weekly.md
├── briefs/
│   ├── 2026-06-04-AliceSmith.md
│   └── 2026-06-03-ProjectAtlas.md
├── open-items/
│   └── 2026-06-04.md
└── patterns/
    └── 2026-06-01-Engineering.md
```

The Archive is the boundary between the raw log layer and the intelligence layer. Below it: noisy, atomic, high-volume. Above it: synthesised, structured, lower-volume, higher-signal.

---

### Carto2
**Role:** Retrieve over the Archive.

Retrieval layer over the Archive. Exact implementation TBD — may be full embeddings (Cartographer_ extended) or a simpler date-scoped file loader given the Archive's lower volume and higher structure. The right answer emerges as the Archive grows.

---

### Marshal
**Role:** Personal chief of staff.

A conversational interface over the Archive, via Carto2. Marshal knows your world: your people, your responsibilities, your history, and your organisation. You talk to it; it gives you straight answers.

**Context sources:**
- **The Archive** — synthesised history retrieved via Carto2
- **Domain documents** — static context: org charts, project charters, strategic priorities, reporting lines. Things that change slowly but shape how everything else is interpreted.
- **Conversation history** — within a session at minimum, optionally persisted across sessions

**Interaction patterns:**
- "What should I be paying attention to this week?"
- "How is @AliceSmith tracking?"
- "What's the history between @TeamA and @ProjectAtlas?"
- "What have I been neglecting?"
- "Draft my update to leadership for this week."

Marshal reasons over intelligence, not noise. The hard retrieval and synthesis work has already been done by Scribe_. That is a meaningful quality advantage over a generic RAG chatbot.

---

## Databases

Two SQLite databases. Each has a single owner and a single purpose.

### Mnemo DB (`~/.codex_/mnemo_/notes.db`)
Data only. Mnemo_'s exclusive source of truth. It stores notes, Atlas pages, Registry Kinds and Instances, and sync metadata. Nothing else writes to it. Scribe_ and Cartographer_ are consumers, not owners.

### Cartographer DB (`~/.codex_/cartographer/index.db`)
Cartographer_'s exclusive source of truth. A superset of the Mnemo DB: it mirrors all Mnemo_ data (notes, registry, atlas) and extends the schema with its own indexing tables (`embeddings`, `index_state`). Cartographer_ populates it by merging from one or more Mnemo DBs. It is not read-only — Cartographer_ owns and writes to it freely. All other tools are read-only consumers of it.

The key distinction: **Mnemo DB is the input; Cartographer DB is the working copy.** Changes written to Cartographer DB are overwritten on the next sync. Durable changes go to Mnemo DB.

### Separation rules — non-negotiable

- **Mnemo_ never touches the Cartographer DB.** It does not read from it, write to it, or call any Cartographer_ API. Mnemo_ is completely ignorant that Cartographer_ exists.
- **Cartographer_ never touches the Mnemo DB.** It reads Mnemo DBs as an input to populate its own DB, but it never writes to them.
- **All other tools that need access to Mnemo_ data must go through Cartographer_** — either by querying Cartographer_ directly or by reading the Cartographer DB. They must never touch the Mnemo DB. The Mnemo DB is never the answer for any tool outside Mnemo_.
- **Only Cartographer_ may write to the Cartographer DB.** All other tools are strictly read-only consumers of it.
- No tool ever calls or imports from Mnemo_ directly.

### Interaction matrix

Rows = actor. Columns = target. `R` = read, `W` = write, `X` = calls/invokes, `—` = no interaction permitted.

|  | Mnemo DB | Carto DB | Carto (process) | Archive | Mnemo_ (process) |
|---|---|---|---|---|---|
| **Mnemo_** | R/W | — | — | — | — |
| **Cartographer_** | R | R/W | — | — | — |
| **Scribe_** | — | R | X | R/W | — |
| **Carto2** | — | R | X | R | — |
| **Marshal** | — | — | — | R | — |

**Notes:**
- Cartographer_ reads the Mnemo DB only as a sync source — it never writes to it.
- Scribe_ is a read-only consumer of the Carto DB. It never writes to the Carto DB directly.
- When Scribe_ needs to trigger a write (e.g. `registry pull`), it does so by calling the Carto process via subprocess. Carto receives the request and applies the write to its own DB. Carto always gatekeeps the Carto DB.
- No tool ever calls or imports from Mnemo_ directly.

---

## Stack Summary

| Tool | Layer | Input | Output |
|---|---|---|---|
| **Mnemo_** | Capture | Keystrokes | Notes, Atlas pages, Instances |
| **Cartographer_** | Retrieve | Queries | Relevant notes + Atlas context |
| **Scribe_** | Synthesise | Cartographer_ retrieval + LLM | Dated markdown reports |
| **Archive** | Store | Scribe_ output | Ordered markdown files |
| **Carto2** | Retrieve | Queries | Relevant archive documents |
| **Marshal** | Converse | Natural language | Answers, drafts, insights |

---

## Design Principles

- **No magic.** Every output is traceable to source material.
- **Plain text throughout.** Notes, reports, domain documents — all markdown or plain text.
- **Composable.** Each tool has a clean interface. Scribe_ is a CLI. Marshal is a chat interface. Neither owns the other's data.
- **Progressive synthesis.** Raw signal is never discarded. It is refined upward through the stack, not replaced.
- **Local and private.** Embeddings run locally via Ollama. No data leaves the machine unless explicitly synced.
