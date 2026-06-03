# Mnemo_ — Atlas Design

> Reference document for the Atlas feature. Covers concept, data model, annotation behaviour, and Cartographer_ integration.

---

## What is Atlas?

Atlas is the wiki-like component of Mnemo. Where notes are transient -- a stream of captures whose relevance decays over time -- Atlas pages form a curated, long-lived knowledge base. If notes are the journal, Atlas is the encyclopedia.

Atlas is not a document editor. Pages are plain text with the same inline syntax as notes. The difference is intent: a note records something that happened; an Atlas page defines something that is.

---

## Structure

Atlas pages are organised hierarchically. A page can have any number of child pages. There is no fixed depth limit.

Each page has:

- A title
- A plain-text body
- A position in the hierarchy (parent reference)
- Zero or more explicit annotations (see below)
- An optional canonical Instance link

The hierarchy is the primary organisational mechanism. Navigation, browsing, and visual structure are all driven by the tree.

---

## Annotations

Atlas pages support the same inline syntax as notes:

| Syntax | Name | Purpose |
|---|---|---|
| `#TagName` | Tag | Categorise this page by topic or type |
| `@ReferenceName` | Reference | Associate this page with a person, team, or named subject |
| `~{YYYY-MM-DD}` | Date | Associate this page with a specific point in time |

Annotations on Atlas pages are **explicit and deliberate**. The user adds them; the system does not infer them from position in the hierarchy or from any other source.

### Example

```
Review Feedback                    #ReviewFeedback
└── Andre                          @Andre
    ├── Midyear 2025               ~{2025-07-01}
    └── Year End 2025              ~{2025-12-01}
└── Bronwyn                        @Bronwyn
    ├── Midyear 2025               ~{2025-07-01}
    └── Year End 2025              ~{2025-12-01}
```

The hierarchy level at which an annotation is applied is a user decision, not a system convention. Tags, references, and dates can appear at any level in any combination.

---

## Instance Link

An Atlas page may be linked to a specific Instance via a canonical foreign key. This is distinct from an `@reference` token in the body.

- An `@reference` token means: this page *mentions* or *relates to* this subject
- A canonical Instance link means: this page *is the knowledge base entry for* this Instance

A page about the PBHL project would carry a canonical link to the PBHL Instance (Kind: Project). The Instance record holds the definition; the Atlas page holds the working knowledge.

A page may have at most one canonical Instance link. Not all pages need one.

---

## UI Behaviour

In the Atlas UI, only **explicit annotations** are used for filtering and search. A filter on `@Andre` returns pages that have `@Andre` annotated directly. It does not surface ancestor pages that happen to have `@Andre`-tagged descendants.

The hierarchy is navigation. Annotations are metadata. They are independent concerns.

---

## Cartographer_ Integration

Cartographer_ embeds Atlas pages as part of its RAG pipeline. The following rules govern how Atlas pages are handled.

### Embedding

Each Atlas page is embedded independently, on its own body content. Ancestor body content is not concatenated or otherwise included. This keeps embeddings focused and prevents generic ancestor content from diluting the signal of specific leaf pages.

### Annotation Inheritance

At retrieval time, Cartographer_ walks the ancestor chain of each Atlas page and aggregates all annotations into a structured metadata payload for that page. A leaf page inherits the tags, references, and dates of every ancestor above it.

This inherited metadata is used for hybrid retrieval -- as exact-match structured filters alongside the vector similarity search -- following the same pattern as tags and references on notes.

Inheritance flows **downward only**. A parent page does not acquire the annotations of its children.

Duplicate annotations (where a page and an ancestor share the same annotation) are deduplicated.

### Summary

| Concern | Behaviour |
|---|---|
| Embedding | Per-page, body content only |
| Ancestor body content | Not inherited |
| Ancestor annotations | Inherited and aggregated at retrieval time |
| Inheritance direction | Downward only (leaf inherits from ancestors) |
| UI filtering | Explicit annotations only, no inheritance |

---

## What Atlas is Not

- Not a task manager or project tracker
- Not a replacement for Instance/Kind definitions -- those live in the Instance record
- Not a note -- pages are curated and maintained, not captured and left
- Not a graph -- the structure is a tree, not a network