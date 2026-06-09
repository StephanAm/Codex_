# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Registry sync: mirrors Mnemo Kinds and Instances into the Obsidian vault."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import frontmatter

if TYPE_CHECKING:
    from scribe.store import InstanceRecord, KindRecord

_INSTANCE_OWNED: frozenset[str] = frozenset({"name", "description", "refs", "synced_at"})
_MANIFEST_OWNED: frozenset[str] = frozenset({"name", "plural", "description"})

SyncStatus = Literal["created", "updated", "unchanged"]
Strategy = Literal["timestamp", "local", "remote", "clobber"]


def _read_post(path: Path) -> frontmatter.Post | None:
    if not path.exists():
        return None
    try:
        return frontmatter.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _instance_metadata(
    instance: InstanceRecord,
    existing_post: frontmatter.Post | None,
    strategy: Strategy,
) -> dict[str, object]:
    meta: dict[str, object] = {
        "name": instance.name,
        "description": instance.description,
    }
    refs = sorted(f"@{r}" for r in instance.references)
    if refs:
        meta["refs"] = refs

    if strategy in ("local", "clobber"):
        for name, (value, _) in instance.properties.items():
            meta[name] = value
    elif strategy == "remote":
        for name, (value, _) in instance.properties.items():
            remote_value = existing_post.metadata.get(name) if existing_post else None
            if remote_value is None or str(remote_value) == value:
                meta[name] = value
            # else: values differ, remote wins — don't include
    else:  # "timestamp"
        synced_at = str(existing_post.metadata.get("synced_at", "")) if existing_post else ""
        for name, (value, updated_at) in instance.properties.items():
            remote_value = existing_post.metadata.get(name) if existing_post else None
            if remote_value is not None and str(remote_value) != value:
                if synced_at and updated_at > synced_at:
                    meta[name] = value
                # else: remote is newer (user edited in vault), leave it alone
            else:
                meta[name] = value  # new property or identical value

    meta["synced_at"] = datetime.now(UTC).isoformat()
    return meta


def _manifest_metadata(kind: KindRecord) -> dict[str, object]:
    return {
        "name": kind.name,
        "plural": kind.plural,
        "description": kind.description,
    }


def _sync_file(
    path: Path,
    owned: dict[str, object],
    owned_keys: frozenset[str],
    *,
    clobber: bool = False,
) -> SyncStatus:
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

    if clobber:
        post.metadata.clear()
    else:
        for key in owned_keys:
            post.metadata.pop(key, None)
    post.metadata.update(owned)

    updated = frontmatter.dumps(post) + "\n"
    if updated == original:
        return "unchanged"

    path.write_text(updated, encoding="utf-8")
    return "updated"


def sync_registry(archive_dir: Path, db_path: Path, strategy: Strategy = "timestamp") -> tuple[int, int, int]:
    """Sync all Kinds and Instances from the Cartographer DB into the vault.

    Returns (created, updated, unchanged).
    """
    from scribe.store import fetch_instances, fetch_kinds

    created = updated = unchanged = 0
    needs_existing = strategy in ("timestamp", "remote")

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
            file_path = kind_dir / f"{instance.name}.md"
            existing_post = _read_post(file_path) if needs_existing else None
            owned = _instance_metadata(instance, existing_post, strategy)
            status = _sync_file(file_path, owned, _INSTANCE_OWNED, clobber=(strategy == "clobber"))
            if status == "created":
                created += 1
            elif status == "updated":
                updated += 1
            else:
                unchanged += 1

    return created, updated, unchanged
