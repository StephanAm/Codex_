# Scribe — Design Document

> Scribe is a standalone CLI tool that generates AI-written reports from Mnemo notes. It orchestrates retrieval from Cartographer, data from the Mnemo API, and an LLM to produce structured markdown documents.

---

## What Scribe Does

Takes a set of report parameters, fetches and groups notes from Mnemo, retrieves semantically relevant chunks from Cartographer, and passes the full structured context to an LLM to rewrite each section. Emits a markdown file.

Scribe owns nothing persistent. It has no database, no daemon, no config beyond what it needs to talk to its three dependencies.

---

## Positioning

| Tool | Responsibility |
|---|---|
| Mnemo API | Notes, tags, references, grouping |
| Cartographer | Embedding-based chunk retrieval |
| LLM (via Ollama) | Section rewriting |
| **Scribe** | Orchestration, prompt assembly, markdown export |

Scribe is a consumer of all three. It adds no new data concepts.

---

## Location

Scribe is a standalone app in the Codex monorepo, sibling to Mnemo and Cartographer:

```
codex/
└── apps/
    ├── mnemo/
    ├── cartographer/
    └── scribe/
        ├── __init__.py
        ├── cli.py          # Click CLI entry point
        ├── pipeline.py     # Orchestration logic
        ├── cartographer.py # Cartographer subprocess wrapper
        ├── mnemo.py        # Mnemo API client
        ├── llm.py          # Ollama client via ollama Python lib
        ├── renderer.py     # Markdown assembly
        ├── pyproject.toml
        └── README.md
```

---

## Dependencies

Add via `uv` from `apps/scribe/`:

```
uv add click httpx ollama
```

- `click` — CLI framework
- `httpx` — HTTP client for Mnemo API calls
- `ollama` — official Ollama Python library

No new dependencies beyond these. Ollama is called via its existing REST API, same as Cartographer does.

---

## Configuration

All configuration via environment variables with sensible defaults:

| Variable | Default | Purpose |
|---|---|---|
| `MNEMO_API_URL` | `http://localhost:8765` | Mnemo API base URL |
| `CARTOGRAPHER_BIN` | `cartographer` | Path to the Cartographer executable |
| `SCRIBE_MODEL` | `llama3` | Ollama model to use for rewriting |
| `SCRIBE_TOP_K` | `10` | Chunks to retrieve per section before dedup |

---

## CLI Interface

```
scribe report [OPTIONS]
```

### Options

| Option | Type | Description |
|---|---|---|
| `--tag` | string (multiple) | Include notes with this tag. Repeatable. |
| `--reference` | string (multiple) | Include notes with this reference. Repeatable. |
| `--group-by` | `tag` \| `reference` | How to split notes into sections. Default: `tag`. |
| `--title` | string | Report title. Default: `Report`. |
| `--output` | path | Output file path. Default: `./report.md`. |
| `--top-k` | integer | Chunks per section. Overrides env var. |
| `--dry-run` | flag | Fetch and group notes, print structure, skip LLM and export. |

### Example

```bash
scribe report \
  --tag backend \
  --tag architecture \
  --reference alice \
  --group-by tag \
  --title "Backend Review" \
  --output ./backend-review.md
```

---

## Pipeline

### Step 1 — Fetch notes

Call `GET /notes` on the Mnemo API for each tag/reference parameter. Merge and dedup by note ID.

### Step 2 — Group notes

Group the note set by the `--group-by` dimension. Each group becomes a report section with a heading derived from the tag or reference name.

A note may appear in multiple groups if it matches multiple tags/references.

### Step 3 — Retrieve chunks

For each section, send the section's note IDs to Cartographer's retrieval endpoint. Request top-K chunks. Collect all chunks across all sections, then dedup by chunk ID.

### Step 4 — Assemble prompt

Build a single prompt containing:

- Report title and metadata
- All sections with their grouped notes (raw body text)
- All retrieved chunks as additional context
- Instructions to rewrite each section as coherent prose, referencing the chunks where relevant, without repeating information across sections

The LLM receives the full report structure in one call.

### Step 5 — Emit markdown

Write the LLM's output to the specified output path. Prepend a metadata header (title, date, parameters used).

---

## Cartographer Subprocess Contract

Cartographer is a CLI tool with no HTTP interface. Scribe invokes it as a subprocess.

Cartographer requires a new `retrieve` subcommand:

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

Scribe captures stdout, parses the JSON, and proceeds. Cartographer's stderr is left to pass through to the terminal.

The `cartographer retrieve` subcommand does not yet exist — it is part of the Cartographer work required to support Scribe.

The path to the Cartographer binary is configured via:

| Variable | Default | Purpose |
|---|---|---|
| `CARTOGRAPHER_BIN` | `cartographer` | Path to the Cartographer executable |

If the subprocess exits non-zero, Scribe treats it as a fatal error and exits.

---

## Prompt Design

The system prompt instructs the LLM to act as a technical writer producing a structured report. It must:

- Rewrite each section as coherent prose, not a bullet dump
- Draw on the provided chunks for additional context and depth
- Avoid repeating the same information in multiple sections
- Use the section headings as provided — do not invent new ones
- Produce valid markdown

The user message contains the full structured input: title, sections with notes, and the chunk corpus.

Prompt templates live in `scribe/pipeline.py` as module-level constants, not external files.

---

## Output Format

```markdown
# {title}

*Generated: {ISO date}*
*Tags: backend, architecture*
*References: alice*

---

## Backend

{LLM-written prose for this section}

---

## Architecture

{LLM-written prose for this section}
```

---

## Entry Point

Register in `apps/scribe/pyproject.toml`:

```toml
[project.scripts]
scribe = "scribe.cli:main"
```

---

## Error Handling

- Mnemo API unreachable → exit with clear message, suggest checking `MNEMO_API_URL`
- Cartographer binary not found or exits non-zero → exit with clear message; Cartographer is required, not optional
- No notes found for parameters → exit with message, do not call LLM
- LLM call fails → exit with message, do not write partial output; check that the model specified by `SCRIBE_MODEL` is available in Ollama
- Output path not writable → exit before calling LLM

All errors print to stderr. Nothing is written to stdout except `--dry-run` output.

---

## What Scribe Is Not

- Not a note viewer or browser
- Not a sync tool
- Not a persistent service
- Not aware of the Mnemo database directly — always via the API
- Not responsible for managing Ollama models or Cartographer's embedding lifecycle

---

## Acceptance Criteria

1. `scribe report` with valid parameters produces a markdown file at the specified output path.
2. `--dry-run` prints the grouped note structure and exits without calling the LLM or Cartographer.
3. All three dependencies being unreachable each produce a clear, distinct error message.
4. No notes matching the parameters produces a clean exit with a message, not a crash.
5. The Cartographer `POST /retrieve` contract is documented and agreed before implementation begins.