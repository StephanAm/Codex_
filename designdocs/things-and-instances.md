# Mnemo — Domain Concepts: Kind & Instance

## Overview

This document defines two new first-class domain concepts introduced as part of the entity feature. These definitions should be used as the reference point for all product, design, and engineering decisions related to this feature.

---

## Kind

A **Kind** is a user-defined common noun that classifies a named real-world subject.

- Kinds are created explicitly by the user before any instances can be created
- A Kind has a name, which must be a singular common noun (e.g. `Person`, `Team`, `Company`)
- A Kind has an optional description
- The Kind name is used directly in the UI as a group label and creation affordance -- there is no separate generic word for this concept
- The user specifies the plural form of the Kind name; the system generates a sensible default which the user can accept or correct

**Examples:** `Person`, `Team`, `Company`, `Customer`, `Stakeholder`, `Vendor`

**Linguistic note:** A Kind is a common noun. It denotes a category of things rather than a specific thing.

---

## Instance

An **Instance** is a proper noun -- a specific, named real-world subject that belongs to a Kind.

- An Instance cannot exist without a Kind
- An Instance has a name (a proper noun, e.g. `John Smith`, `Acme Corp`, `Engineering`)
- An Instance has an optional description body
- An Instance may be associated with one or more `@reference` tokens, connecting it indirectly to notes
- An Instance has no direct relationship to notes -- the connection is always via references

**Examples:** `John Smith` (of kind Person), `Acme Corp` (of kind Company), `Engineering` (of kind Team)

**Linguistic note:** An Instance is a proper noun. It names a specific thing that *is* a Kind.

---

## Relationship

The two concepts mirror standard linguistic structure:

| Concept | Linguistic type | Example |
|---|---|---|
| Kind | Common noun | `Person` |
| Instance | Proper noun | `John Smith` |

> John Smith **is a** Person. Acme Corp **is a** Company. Engineering **is a** Team.

The Kind name *becomes* the natural language descriptor for its instances. This is why no generic word (e.g. "entity", "contact", "record") is used in the UI -- the Kind name does that job directly.

---

## UI Naming Conventions

| Context | Copy |
|---|---|
| Sidebar section heading | `KINDS` |
| Group heading in sidebar | Kind name, pluralised (e.g. `People`, `Teams`) |
| Create kind affordance | `+ new kind` |
| Create instance affordance | `+ new [kind name]` (e.g. `+ new person`) |
| Detail view metadata label | Kind name (e.g. `Person`) |

The word "entity" is an internal engineering term only. It must never appear in the UI.

---

## Internal Naming (DB & API)

For clarity, the mapping between user-facing language and internal naming is:

| User-facing | Code model | DB table | API route |
|---|---|---|---|
| Kind | `InstanceKind` | `instance_kinds` | `/instance-kinds` |
| Instance | `Instance` | `instances` | `/instances` |