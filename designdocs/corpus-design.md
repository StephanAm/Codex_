# Cartographer_ — Corpus Design

> The corpus is the set of content types that Cartographer_ indexes and searches. Each type maps to a distinct Mnemo_ tool and has its own retrieval and scoring behaviour.

---

## Corpus Types

The `embeddings` table stores vectors for four `source_type` values, grouped into three logical corpora:

| Corpus | `source_type` value(s) | Mnemo_ tool | Budget |
|---|---|---|---|
| Notes | `note` | Stylus | 5 |
| Atlas pages | `atlas_page` | Atlas | 5 |
| Definitions | `instance_kind`, `instance` | Registry | 2 (combined) |

These constants are defined in [search.py:42–44](../apps/cartographer/src/cartographer/search.py#L42-L44).

---

## Notes (`note`)

Stylus notes from the `notes` table. Each note is indexed as a single chunk (`chunk_index = 0`).

**What gets indexed:** the full `body` field.

**Title:** first line of the body, truncated to 80 characters.

**Metadata carried into retrieval:** `time_stamp`, `created_at`, tags (via `note_tags`), references (via `note_references`).

**Date filtering:** notes can be pre-filtered by date window at the SQL level before scoring. The anchor is `COALESCE(time_stamp, created_at)`.

**Temporal decay:** notes are the only corpus type that ages. Score is multiplied by an exponential decay factor with a half-life of 90 days, anchored to `time_stamp` (or `created_at` if absent). Atlas pages and definitions do not decay.

---

## Atlas Pages (`atlas_page`)

Structured reference pages from the `atlas_pages` table. Each page is a node in the Atlas tree.

**What gets indexed:** the `body` field of each page.

**Title:** the `title` column.

**Metadata carried into retrieval:** tags and references are **inherited from ancestors** in the tree (see `_build_ancestor_annotations` in search.py). A page picks up any tags or references attached to its parent nodes all the way to the root. This means a broad tag on a parent section applies to all its children during retrieval.

**No temporal decay:** Atlas pages have no `time_stamp` and are not subject to decay.

---

## Definitions (`instance_kind` + `instance`)

Registry entities from the `instance_kinds` and `instances` tables. Both types are retrieved together and share a combined budget of 2.

**What gets indexed:** the `description` field (for both kinds and instances).

**Title:** the `name` column.

**No tags, references, or decay:** definitions carry no tag or reference metadata and are not time-weighted.

---

## Scoring

After per-corpus retrieval, all candidates are scored with:

```
final_score = similarity × decay × reference_boost × tag_boost
```

| Factor | Applies to | Values |
|---|---|---|
| `similarity` | All | Cosine similarity vs query vector |
| `decay` | Notes only | Exponential, half-life 90 days |
| `reference_boost` | All | 1.5× (hard `@mention` match), 1.2× (soft inferred), 1.0× (none) |
| `tag_boost` | All | 1.2× if any tag matches, 1.0× otherwise |

Candidates below `MIN_SIMILARITY = 0.65` are dropped after scoring.

---

## Result Assembly

After scoring, results are assembled in two passes:

1. **Guarantee at least one representative per corpus** — the top-scoring candidate from each of `note`, `atlas_page`, `instance_kind`, `instance` is promoted first (if one exists above the threshold).
2. **Fill remaining slots** — remaining candidates are appended in score order up to `MAX_RESULTS = 15`.
3. **Final sort** — the full result list is re-sorted by `final_score` descending.

This ensures every active corpus has at least one entry in the context even when notes dominate by score.

---

## `embeddings` Table Schema

```sql
CREATE TABLE embeddings (
    id          INTEGER PRIMARY KEY,
    source_uuid TEXT    NOT NULL,
    source_type TEXT    NOT NULL
        CHECK (source_type IN ('note', 'atlas_page', 'instance_kind', 'instance')),
    chunk_index INTEGER NOT NULL DEFAULT 0,
    model       TEXT    NOT NULL,
    vector      BLOB    NOT NULL,
    indexed_at  TEXT    NOT NULL,
    UNIQUE (source_uuid, source_type, chunk_index, model)
)
```

All four corpus types share this single table, keyed by `(source_uuid, source_type, chunk_index, model)`. Currently only `chunk_index = 0` is used (single-chunk indexing).

---

## Output Shape

The search pipeline produces an `LLMContext` value:

```python
@dataclass
class LLMContext:
    query: str
    semantic_query: str
    references: list[str]
    tags: list[str]
    date_window: DateWindow | None
    chunks: list[ContextChunk]

@dataclass
class ContextChunk:
    corpus_type: str   # one of: "note", "atlas_page", "instance_kind", "instance"
    content: str
    score: float
    title: str
    tags: list[str]
    references: list[str]
    time_stamp: str | None
```

Consumers (Scribe_, `carto search --json`) receive this structure directly.
