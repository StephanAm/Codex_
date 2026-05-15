import json
import os
from pathlib import Path


def _session_path() -> Path:
    return Path(f"/tmp/note-taker-session-{os.getuid()}.json")


def get_session_context() -> tuple[list[str], list[str]]:
    """Returns (tags, entities) active for the current session."""
    p = _session_path()
    if not p.exists():
        return [], []
    try:
        data = json.loads(p.read_text())
        return data.get("tags", []), data.get("entities", [])
    except (json.JSONDecodeError, OSError):
        return [], []


def set_session_context(tags: list[str], entities: list[str]) -> None:
    p = _session_path()
    p.write_text(json.dumps({"tags": tags, "entities": entities}))


def clear_session_context() -> None:
    p = _session_path()
    if p.exists():
        p.unlink()
