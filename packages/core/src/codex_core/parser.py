import re
from dataclasses import dataclass

_TAG_RE = re.compile(r"#(\w+)")
_ENTITY_RE = re.compile(r"@(\w+)")
_TODO_RE = re.compile(r"\bTODO\s*[:\-]", re.IGNORECASE)


@dataclass
class ParsedNote:
    tags: list[str]
    entities: list[str]


def normalise(text: str) -> str:
    """Replace todo shorthand forms (TODO:, TODO-, TODO :, TODO -) with #todo."""
    return _TODO_RE.sub("#todo", text)


def parse(text: str) -> ParsedNote:
    # Preserve order, deduplicate, normalise to lowercase
    tags = list(dict.fromkeys(m.lower() for m in _TAG_RE.findall(text)))
    entities = list(dict.fromkeys(m.lower() for m in _ENTITY_RE.findall(text)))
    if _TODO_RE.search(text) and "todo" not in tags:
        tags.append("todo")
    return ParsedNote(tags=tags, entities=entities)
