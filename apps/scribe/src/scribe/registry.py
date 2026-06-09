# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Registry sync: mirrors Mnemo Kinds and Instances into the Obsidian vault."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from scribe.store import InstanceRecord, KindRecord

# Keys that Mnemo owns in each file type. Lines belonging to these keys (and
# any list items directly under them) are replaced on every sync.
_INSTANCE_OWNED: frozenset[str] = frozenset({"name", "description", "refs"})
_MANIFEST_OWNED: frozenset[str] = frozenset({"name", "plural", "description"})

SyncStatus = Literal["created", "updated", "unchanged"]


# ---------------------------------------------------------------------------
# Frontmatter builders
# ---------------------------------------------------------------------------


def _q(value: str) -> str:
    """Quote a string as a JSON-style YAML scalar (handles colons, quotes, etc.)."""
    return json.dumps(value)


def _build_instance_frontmatter(instance: InstanceRecord) -> str:
    refs = sorted(f"@{r}" for r in instance.references)
    ref_lines = "".join(f"\n  - {r}" for r in refs)
    ref_block = f"refs:{ref_lines}\n" if refs else ""
    return f"---\nname: {_q(instance.name)}\ndescription: {_q(instance.description)}\n{ref_block}---\n"


def _build_manifest_frontmatter(kind: KindRecord) -> str:
    return f"---\nname: {_q(kind.name)}\nplural: {_q(kind.plural)}\ndescription: {_q(kind.description)}\n---\n"


# ---------------------------------------------------------------------------
# Idempotent file sync
# ---------------------------------------------------------------------------


def _rewrite_frontmatter(fm_lines: list[str], new_fm: str, owned_keys: frozenset[str]) -> str:
    """Return a new frontmatter block with owned keys replaced by new_fm content.

    Preserves all lines that do not belong to an owned key. Owned scalar lines
    and list items under owned keys are dropped; the new values are appended at
    the end before the closing `---`.
    """
    kept: list[str] = []
    in_owned_list = False

    for line in fm_lines:
        stripped = line.rstrip("\n")

        # Detect start of an owned list field (e.g. "refs:")
        if stripped.rstrip(":").rstrip() in owned_keys and stripped.endswith(":"):
            in_owned_list = True
            continue

        # Detect a plain owned scalar field (e.g. "name: ...")
        key = stripped.split(":")[0].strip()
        if key in owned_keys and not in_owned_list:
            continue

        # Inside a list block, skip list items; exit on anything else
        if in_owned_list:
            if stripped.startswith("  - "):
                continue
            in_owned_list = False

        kept.append(line)

    # Extract just the field lines from new_fm (strip surrounding ---)
    new_field_lines = new_fm.splitlines(keepends=True)[1:-1]  # skip opening and closing ---

    return "---\n" + "".join(kept) + "".join(new_field_lines) + "---\n"


def _sync_file(path: Path, new_frontmatter: str, owned_keys: frozenset[str]) -> SyncStatus:
    """Create or update a file, preserving non-owned frontmatter and body."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_frontmatter + "\n", encoding="utf-8")
        return "created"

    content = path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        # No existing frontmatter — prepend it
        updated = new_frontmatter + "\n" + content
        path.write_text(updated, encoding="utf-8")
        return "updated"

    # Split: opening ---, frontmatter lines, closing ---, body
    lines = content.splitlines(keepends=True)
    try:
        close_idx = next(i for i, ln in enumerate(lines) if i > 0 and ln.rstrip("\n") == "---")
    except StopIteration:
        # Malformed frontmatter (no closing ---) — prepend fresh block
        updated = new_frontmatter + "\n" + content
        path.write_text(updated, encoding="utf-8")
        return "updated"

    fm_lines = lines[1:close_idx]  # lines between the two ---
    body_lines = lines[close_idx + 1 :]  # everything after closing ---

    new_fm_block = _rewrite_frontmatter(fm_lines, new_frontmatter, owned_keys)
    updated = new_fm_block + "".join(body_lines)

    if updated == content:
        return "unchanged"

    path.write_text(updated, encoding="utf-8")
    return "updated"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def sync_registry(archive_dir: Path, db_path: Path) -> tuple[int, int, int]:
    """Sync all Kinds and Instances from the Cartographer DB into the vault.

    Returns (created, updated, unchanged).
    """
    from scribe.store import fetch_instances, fetch_kinds

    created = updated = unchanged = 0

    kinds: list[KindRecord] = fetch_kinds(db_path)

    for kind in kinds:
        kind_dir = archive_dir / kind.plural
        kind_dir.mkdir(parents=True, exist_ok=True)

        # MANIFEST.md
        manifest_path = kind_dir / "MANIFEST.md"
        status = _sync_file(manifest_path, _build_manifest_frontmatter(kind), _MANIFEST_OWNED)
        if status == "created":
            created += 1
        elif status == "updated":
            updated += 1
        else:
            unchanged += 1

        # Instance files
        instances: list[InstanceRecord] = fetch_instances(kind.id, db_path)
        for instance in instances:
            inst_path = kind_dir / f"{instance.name}.md"
            status = _sync_file(inst_path, _build_instance_frontmatter(instance), _INSTANCE_OWNED)
            if status == "created":
                created += 1
            elif status == "updated":
                updated += 1
            else:
                unchanged += 1

    return created, updated, unchanged
