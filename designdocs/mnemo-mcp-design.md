# Mnemo MCP Server — Build Instructions

> Build a Model Context Protocol (MCP) server that exposes the Mnemo notes API as tools an LLM can call. The server is a thin translation layer between MCP (stdio transport) and the existing Mnemo REST API.

---

## Context

Mnemo is a personal note-taking tool with a FastAPI backend (`api.py`) running on `localhost:8765`. Its OpenAPI spec is available alongside these instructions. Notes are plain text with inline syntax for tags (`#TagName`), entity references (`@PersonName`), and dates (`~{YYYY-MM-DD}`).

This MCP server lets an LLM query notes via natural language by exposing a small set of read-only tools over the standard input/output (stdio) MCP transport. It is single-user, local-only, and read-only. No writes, no auth, no networking beyond a localhost HTTP call to the Mnemo API.

---

## Note shape

The Mnemo API returns notes with the following structure. This is the shape the MCP server passes through to the LLM.

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Auto-incrementing primary key. Use this for `get_note`. |
| `uuid` | string | Stable UUID for sync. Do not surface to the LLM unless explicitly asked. |
| `body` | string | Full plain-text body including inline `#tags`, `@refs`, and `~{date}` syntax. |
| `tags` | array of string | Parsed tags, lowercase. |
| `entities` | array of string | Parsed entity references, lowercase. |
| `created_at` | ISO 8601 string | When the note was written. |
| `updated_at` | ISO 8601 string | Last edit. |
| `time_stamp` | ISO 8601 string | Parsed `~{date}` from the body, or equal to `created_at` if no date was specified. **This is the field to use for "when did this happen".** |

---

## Location and structure

Build the server inside the existing Mnemo repository as a subpackage:

```
mnemo/
├── api.py
├── mcp_server/
│   ├── __init__.py
│   ├── server.py        # main entry point, tool definitions
│   ├── client.py        # thin httpx wrapper over the Mnemo API
│   └── README.md        # how to run and connect to it
├── pyproject.toml       # add the new dependencies and entry point
```

Do not create a separate package, separate repo, or separate test pipeline. This is a sibling module to the CLI and TUI, sharing the project's existing tooling.

---

## Dependencies

Add via `uv`:

```
uv add mcp httpx
```

- `mcp` — official Anthropic MCP SDK for Python
- `httpx` — modern HTTP client, async-capable

No other dependencies. No FastAPI, no Pydantic v1, no requests, no aiohttp.

---

## Configuration

The server reads its configuration from environment variables.

| Variable | Default | Purpose |
|---|---|---|
| `MNEMO_API_URL` | `http://localhost:8765` | Base URL of the Mnemo REST API |

Do not hardcode `localhost:8765` anywhere. Always read from the env var with the default as fallback.

---

## Transport

Use stdio only. Do not implement HTTP, SSE, or any other transport. The server is a subprocess spawned by an MCP client (e.g. Claude CLI, Claude Desktop) and communicates via standard input and standard output.

Use the SDK's built-in stdio transport. Do not implement framing or JSON-RPC manually.

---

## Tools to expose

Expose exactly the following five read-only tools. No more, no fewer. Do not expose the Mnemo API's config, session, sync, auth, shutdown, or health endpoints. The tool names must match exactly.

### 1. `search_notes`

Search notes by free-text query, tag, and entity. The primary workhorse tool.

- **Input schema:**
  - `q` (string, optional) — free-text search query against note body
  - `tag` (string, optional) — filter by a single tag (lowercase, no `#` prefix)
  - `entity` (string, optional) — filter by a single entity (lowercase, no `@` prefix)
- **Behaviour:** maps to `GET /notes` with the supplied query parameters. Per the API, when `q` is provided, `tag` and `entity` are ignored. All parameters are optional; if none are supplied, recent notes are returned.
- **Returns:** the JSON array of `NoteResponse` objects from the API, untransformed.
- **Description (for the LLM):** "Search Mnemo notes by free-text query, tag, or entity. Use this to find notes matching a topic, person, or keyword. Tag and entity values should be lowercase and supplied without the `#` or `@` prefix. Note: when `q` is provided, `tag` and `entity` are ignored — call this tool again with the structured filter if you need to narrow further. Returns up to 500 notes ordered by creation date descending."

### 2. `get_note`

Fetch a single note by ID.

- **Input schema:**
  - `note_id` (integer, required)
- **Behaviour:** maps to `GET /notes/{note_id}`. The API returns 404 if no note with that ID exists; surface this as an MCP error.
- **Returns:** a single `NoteResponse` object.
- **Description (for the LLM):** "Fetch the full content of a single Mnemo note by its numeric ID. Use this after `search_notes` to retrieve a specific note's full body and metadata."

### 3. `list_tags`

Return the full list of known tags.

- **Input schema:** none
- **Behaviour:** maps to `GET /tags`.
- **Returns:** the JSON array of tag strings as returned by the API. All tags are lowercase.
- **Description (for the LLM):** "List all tags used across Mnemo notes, sorted alphabetically. Use this to discover what topics or projects exist before searching, or to validate that a tag the user mentioned actually exists."

### 4. `list_entities`

Return the full list of known entities (people, teams, named things referenced by `@`).

- **Input schema:** none
- **Behaviour:** maps to `GET /entities`.
- **Returns:** the JSON array as returned by the API.
- **Description (for the LLM):** "List all entities (people, teams, named references) tracked in Mnemo. Use this to discover who or what is referenced in notes, or to validate that an entity the user mentioned actually exists."

### 5. `get_recent_notes`

Return the most recent N notes in chronological order. Useful for digest-style questions ("what have I been doing lately").

- **Input schema:**
  - `limit` (integer, optional, default 20, max 100)
- **Behaviour:** maps to `GET /notes` with no filters. The API already returns notes in creation-date-descending order. Truncate client-side to `limit`.
- **Returns:** the truncated JSON array of `NoteResponse` objects.
- **Description (for the LLM):** "Fetch the most recent N notes from Mnemo. Use this when the user asks about recent activity, what they've been working on, or for time-bounded summaries. For 'when did X happen' style questions, prefer the `time_stamp` field over `created_at`, as it reflects the date the user wrote in the note body if one was specified."

---

## Implementation guidance

### `client.py`

Wrap the Mnemo API in a small async class. One method per tool. No abstraction beyond that. Use `httpx.AsyncClient` with a sensible timeout (5 seconds). Read `MNEMO_API_URL` from the environment on construction.

The client class is the only place that knows about the HTTP layer. Tool handlers in `server.py` import and call it; they should not import `httpx` directly.

Map non-2xx responses to exceptions:

- 404 from `GET /notes/{id}` → raise a custom `NoteNotFound` exception with the requested ID
- Other non-2xx → raise a generic `MnemoAPIError` with status code and response body

### `server.py`

This is the MCP server entry point. Use the SDK's high-level `Server` API (or `FastMCP` if the SDK version you install supports it; check the docs at install time). Define each tool as a decorated async function. Each handler is small: call the client, return the result.

Handlers should:

- Validate input lightly (e.g. integer bounds on `limit`)
- Call the client method
- Return the result as a JSON-serialisable Python object (dict or list)
- Catch `NoteNotFound` from `get_note` and surface it as a clean MCP error
- Let other transport errors propagate; the SDK will surface them

Do not implement retries, caching, or rate-limiting. The Mnemo API is local and responsive; if something fails, surface the failure.

### Entry point

Register a console script in `pyproject.toml`:

```toml
[project.scripts]
mnemo-mcp = "mnemo.mcp_server.server:main"
```

`main()` should set up the server and start the stdio transport. Use the SDK's recommended pattern for this. The result is that running `mnemo-mcp` from the command line starts the server on stdio, ready to be spawned by a client.

---

## Limits and edge cases

- **500-note ceiling on `GET /notes`.** The Mnemo API caps unfiltered note listings at 500. There is no pagination. For a personal note-taker, this is fine, but the tool descriptions should not promise the LLM exhaustive results from an unfiltered `search_notes` call. The current description wording is accurate.
- **Empty results.** Empty arrays are valid. Return them as-is. Do not transform into errors.
- **Note IDs are integers.** UUIDs exist but the LLM-facing surface uses the integer ID only. Do not expose UUID lookups.

---

## How a client connects to it

This is for the README, not the implementation. Once installed, an MCP client configures the server by pointing at the `mnemo-mcp` binary. For Claude CLI, the config entry looks like:

```json
{
  "mcpServers": {
    "mnemo": {
      "command": "mnemo-mcp",
      "env": {
        "MNEMO_API_URL": "http://localhost:8765"
      }
    }
  }
}
```

Include a working example for both Claude CLI and Claude Desktop in the `mcp_server/README.md`.

---

## Testing

Add a `tests/test_mcp_server.py` alongside Mnemo's existing tests. Cover:

1. The client class against a mocked Mnemo API (use `httpx.MockTransport`). Include a 404 case for `get_note`.
2. Each tool handler with a mocked client.
3. One end-to-end test that runs the server as a subprocess, sends an `initialize` and `tools/list` JSON-RPC pair, and asserts the expected five tools appear in the response.

Do not test the MCP SDK internals or the underlying transport — those are upstream concerns.

---

## What not to do

- Do not bypass the Mnemo REST API and read SQLite directly. Always go through the API.
- Do not implement write tools (`create_note`, `edit_note`, `delete_note`). Read-only only.
- Do not expose `/config`, `/session`, `/sync`, `/auth/google`, `/health`, or `/shutdown` as tools.
- Do not add HTTP, SSE, or WebSocket transports. Stdio only.
- Do not add auth, API keys, or token handling. The server runs as the user, talking to a localhost API.
- Do not add a database, cache, or any persistent state. The server is stateless.
- Do not log to stdout. Stdout is reserved for the MCP transport. Log to stderr or a file.
- Do not transform or filter the API responses beyond what the tool definitions specify. Pass `NoteResponse` objects through as-is.
- Do not introduce dependencies beyond `mcp` and `httpx`.

---

## Acceptance criteria

The build is complete when:

1. `uv sync` installs cleanly with the new dependencies.
2. `mnemo-mcp` runs from the command line and accepts stdio input without crashing.
3. The five tools listed above appear in response to a `tools/list` JSON-RPC request.
4. Each tool, when invoked, makes the correct HTTP call to the Mnemo API and returns a sensible result.
5. `get_note` with a non-existent ID surfaces a clean MCP error rather than crashing the server.
6. The tests pass.
7. The `mcp_server/README.md` documents how to install, configure, and connect a client.

---

## Reference material

- MCP specification: https://modelcontextprotocol.io/
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Mnemo OpenAPI spec: provided alongside these instructions