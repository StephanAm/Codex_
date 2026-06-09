# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Registry sync: mirrors Mnemo Kinds and Instances into the Obsidian vault."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

import frontmatter

if TYPE_CHECKING:
    from scribe.store import InstanceRecord, KindRecord

_INSTANCE_OWNED: frozenset[str] = frozenset({"name", "description", "refs"})
_MANIFEST_OWNED: frozenset[str] = frozenset({"name", "plural", "description"})

SyncStatus = Literal["created", "updated", "unchanged"]


def _instance_metadata(instance: InstanceRecord) -> dict[str, object]:
    meta: dict[str, object] = {
        "name": instance.name,
        "description": instance.description,
    }
    refs = sorted(f"@{r}" for r in instance.references)
    if refs:
        meta["refs"] = refs
    return meta


def _manifest_metadata(kind: KindRecord) -> dict[str, object]:
    return {
        "name": kind.name,
        "plural": kind.plural,
        "description": kind.description,
    }


def _sync_file(path: Path, owned: dict[str, object], owned_keys: frozenset[str]) -> SyncStatus:
    """Create or update a file, preserving non-owned frontmatter and body."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        post = frontmatter.Post("")
        post.metadata.update(owned)
        path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
        return "created"

    original = path.read_text(encoding="utf-8")
    try:
        post = frontmatter.loads(original)
    except Exception:
        # Unparseable frontmatter (e.g. unquoted @ written by older code).
        # Salvage the body by finding the closing --- manually.
        lines = original.splitlines(keepends=True)
        body = original
        if lines and lines[0].strip() == "---":
            try:
                close = next(i for i, ln in enumerate(lines) if i > 0 and ln.strip() == "---")
                body = "".join(lines[close + 1 :])
            except StopIteration:
                pass
        post = frontmatter.Post(body)

    for key in owned_keys:
        post.metadata.pop(key, None)
    post.metadata.update(owned)

    updated = frontmatter.dumps(post) + "\n"
    if updated == original:
        return "unchanged"

    path.write_text(updated, encoding="utf-8")
    return "updated"


def sync_registry(archive_dir: Path, db_path: Path) -> tuple[int, int, int]:
    """Sync all Kinds and Instances from the Cartographer DB into the vault.

    Returns (created, updated, unchanged).
    """
    from scribe.store import fetch_instances, fetch_kinds

    created = updated = unchanged = 0

    for kind in fetch_kinds(db_path):
        kind_dir = archive_dir / kind.plural.title()
        kind_dir.mkdir(parents=True, exist_ok=True)

        status = _sync_file(kind_dir / "MANIFEST.md", _manifest_metadata(kind), _MANIFEST_OWNED)
        if status == "created":
            created += 1
        elif status == "updated":
            updated += 1
        else:
            unchanged += 1

        for instance in fetch_instances(kind.id, db_path):
            status = _sync_file(kind_dir / f"{instance.name}.md", _instance_metadata(instance), _INSTANCE_OWNED)
            if status == "created":
                created += 1
            elif status == "updated":
                updated += 1
            else:
                unchanged += 1

    return created, updated, unchanged
