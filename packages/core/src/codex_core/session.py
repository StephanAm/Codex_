# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import os
from pathlib import Path


def _session_path() -> Path:
    return Path(f"/tmp/codex-session-{os.getuid()}.json")


def get_session_context() -> tuple[list[str], list[str]]:
    """Returns (tags, references) active for the current session."""
    p = _session_path()
    if not p.exists():
        return [], []
    try:
        data = json.loads(p.read_text())
        # Accept old "entities" key from pre-migration session files
        references = data.get("references", data.get("entities", []))
        return data.get("tags", []), references
    except (json.JSONDecodeError, OSError):
        return [], []


def set_session_context(tags: list[str], references: list[str]) -> None:
    p = _session_path()
    p.write_text(json.dumps({"tags": tags, "references": references}))


def clear_session_context() -> None:
    p = _session_path()
    if p.exists():
        p.unlink()
