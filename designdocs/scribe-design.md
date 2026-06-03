# Scribe_ — Design Document

> Scribe_ is a standalone CLI app that generates AI-written documents from Mnemo_ notes. It reads notes from the Cartographer_ database, retrieves semantically relevant context chunks, and passes the structured input to an LLM to produce markdown output.

---

## What Scribe Does

Takes a date range, reads notes from the Cartographer_ SQLite database, retrieves semantically relevant chunks via the Cartographer_ CLI, and passes the full structured context to an LLM to produce a markdown document. Emits a file.

Scribe_ owns nothing persistent. It has no database, no daemon, no config beyond what it needs to talk to its two dependencies.

---

## Positioning

| Tool | Responsibility |
|---|---|
| Cartographer_ DB | Notes, tags, semantic index |
| Cartographer_ CLI | Embedding-based chunk retrieval |
| LLM (Claude or Ollama) | Document generation |
| **Scribe_** | Orchestration, prompt assembly, markdown export |

Scribe_ is a consumer of both. It adds no new data concepts.

---

## Location

Scribe_ is a standalone app in the Codex monorepo, sibling to Mnemo_ and Cartographer_:

```
codex/
└── apps/
    ├── mnemo/
    ├── cartographer/
    └── scribe/
        └── src/scribe/
            ├── cli.py          # Click CLI entry point
            ├── bulletin.py     # Bulletin generation logic
            ├── todo.py         # To-do list generation logic
            ├── store.py        # Reads notes from Cartographer DB
            ├── cartographer.py # Cartographer subprocess wrapper
            ├── config.py       # Configuration resolution
            ├── llm/            # LLM backends (claude, ollama, dummy)
            └── pyproject.toml
```

---

## Dependencies

```
click>=8.0
ollama>=0.3
```

- `click` — CLI framework
- `ollama` — Ollama Python library (used when `SCRIBE_BACKEND=ollama`)
- Claude is invoked via the `claude` CLI subprocess (no Python SDK dependency)

---

## Configuration

Resolution order: environment variable → `~/.codex_/scribe/config.toml` → built-in default.

Run `scribe config init` to write a default config file. Run `scribe config show` to see the resolved values.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `CARTOGRAPHER_DB` | `~/.codex_/cartographer/index.db` | Path to Cartographer SQLite DB |
| `CARTOGRAPHER_BIN` | `cartographer` | Path to the Cartographer executable |
| `SCRIBE_BACKEND` | `claude` | LLM backend: `claude` \| `ollama` \| `dummy` |
| `SCRIBE_MODEL` | *(empty)* | Model override (backend-specific) |
| `SCRIBE_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `SCRIBE_CLAUDE_BIN` | `claude` | Path to the `claude` CLI binary |
| `SCRIBE_TOP_K` | `10` | Chunks to retrieve per command |

### config.toml sections

```toml
[cartographer]
db  = "~/.codex_/cartographer/index.db"
bin = "cartographer"

[llm]
backend    = "claude"
model      = ""
ollama_url = "http://localhost:11434"
claude_bin = "claude"

[retrieval]
top_k = 10
```

---

## CLI Interface

```
scribe bulletin [OPTIONS]
scribe todo     [OPTIONS]
scribe config show
scribe config init
```

### `scribe bulletin`

Generate a deduplicated bullet-list bulletin from all notes in a date range.

| Option | Type | Description |
|---|---|---|
| `--date` | `YYYY-MM-DD` | Single day (default: today). Mutually exclusive with `--from`/`--to`. |
| `--from` | `YYYY-MM-DD` | Start of date range (inclusive). |
| `--to` | `YYYY-MM-DD` | End of date range (inclusive). |
| `--title` | string | Report title. Default: `Bulletin — {date}`. |
| `--output` | path | Output file. Default: `./bulletin-{date}.md`. |
| `--top-k` | integer | Chunks to retrieve. Overrides `SCRIBE_TOP_K`. |
| `--backend` | string | LLM backend override. |
| `--dry-run` | flag | Print fetched notes; skip Cartographer retrieval and LLM. |

### `scribe todo`

Generate a numbered action-item list from notes tagged `#todo` in a date range.

| Option | Type | Description |
|---|---|---|
| `--date` | `YYYY-MM-DD` | Single day (default: today). Mutually exclusive with `--from`/`--to`. |
| `--from` | `YYYY-MM-DD` | Start of date range (inclusive). |
| `--to` | `YYYY-MM-DD` | End of date range (inclusive). |
| `--title` | string | Report title. Default: `To-Do — {date}`. |
| `--output` | path | Output file. Default: `./todo-{date}.md`. |
| `--top-k` | integer | Chunks to retrieve. Overrides `SCRIBE_TOP_K`. |
| `--backend` | string | LLM backend override. |
| `--dry-run` | flag | Print fetched notes; skip Cartographer retrieval and LLM. |

### Examples

```bash
scribe bulletin --date 2025-07-15
scribe bulletin --from 2025-07-01 --to 2025-07-15 --output ./july-mid.md
scribe todo --date 2025-07-15
scribe todo --from 2025-07-01 --to 2025-07-15 --backend ollama
```

---

## Pipeline

Both commands follow the same pipeline:

### Step 1 — Resolve date range

Parse `--date` / `--from` / `--to`. Default to today if none supplied. `--date` and `--from`/`--to` are mutually exclusive.

### Step 2 — Fetch notes from Cartographer DB

Open the Cartographer SQLite DB read-only. For `bulletin`: fetch all notes whose semantic date falls in the range. For `todo`: fetch only notes tagged `#todo`.

### Step 3 — Dry-run exit (if `--dry-run`)

Print the period and note list to stdout. Exit without calling Cartographer or the LLM.

### Step 4 — Check output path

Create parent directories if needed. Touch the output file to verify it is writable before calling the LLM.

### Step 5 — Retrieve context chunks

Call `cartographer retrieve --note-ids <ids> --top-k <k>` as a subprocess. Capture and parse the JSON array from stdout.

### Step 6 — Generate with LLM

Build the configured LLM backend, assemble the prompt, and call the LLM. `bulletin` asks for an ordered, deduplicated bullet list. `todo` asks for a numbered action-item list.

### Step 7 — Write output

Write the markdown to the output path and print the path to stderr.

---

## Cartographer_ Subprocess Contract

Cartographer_ is a CLI tool with no HTTP interface. Scribe_ invokes it as a subprocess.

```bash
cartographer retrieve --note-ids 1,4,7,23 --top-k 10
```

Cartographer writes a JSON array to stdout and exits:

```json
{
  "chunks": [
    {
      "chunk_id": "abc123",
      "note_id": 4,
      "text": "...",
      "score": 0.91
    }
  ]
}
```

Scribe_ captures stdout, parses the JSON, and proceeds. Cartographer_'s stderr passes through to the terminal.

If the subprocess exits non-zero, Scribe_ treats it as a fatal error and exits.

---

## Prompt Design

The system prompt instructs the LLM to act as a technical writer. For `bulletin`: produce an ordered, deduplicated bullet list with no invented content beyond the notes. For `todo`: produce a numbered list of discrete action items extracted from `#todo`-tagged notes.

Prompt templates live in `scribe/bulletin.py` and `scribe/todo.py` as module-level constants.

---

## Error Handling

- Cartographer DB not found → exit with message including the expected path
- Cartographer_ binary not found or exits non-zero → fatal exit with message
- No notes found for parameters → clean exit with message; do not call LLM
- LLM call fails → exit with message; do not write partial output
- Output path not writable → exit before calling LLM

All errors print to stderr. Nothing is written to stdout except `--dry-run` output.

---

## What Scribe Is Not

- Not a note viewer or browser
- Not a sync tool
- Not a persistent service
- Not aware of the Mnemo_ API — reads Cartographer_ DB directly
- Not responsible for managing Ollama models or Cartographer_'s embedding lifecycle

---

## Acceptance Criteria

1. `scribe bulletin` with a valid date range produces a markdown bulletin at the specified output path.
2. `scribe todo` with a valid date range produces a markdown to-do list at the specified output path.
3. `--dry-run` prints the fetched note structure and exits without calling Cartographer_ or the LLM.
4. Cartographer_ DB missing and Cartographer_ binary missing each produce a clear, distinct error message.
5. No notes matching the parameters produces a clean exit with a message, not a crash.
