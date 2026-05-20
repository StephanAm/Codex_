import re
from dataclasses import dataclass

_TAG_RE = re.compile(r"#(\w+)")
_REFERENCE_RE = re.compile(r"@(\w+)")
_TODO_RE = re.compile(r"\bTODO\s*[:\-]", re.IGNORECASE)


@dataclass
class ParsedNote:
    tags: list[str]
    references: list[str]


def normalise(text: str) -> str:
    """Replace todo shorthand forms (TODO:, TODO-, TODO :, TODO -) with #todo."""
    return _TODO_RE.sub("#todo", text)


def parse(text: str) -> ParsedNote:
    # Preserve order, deduplicate, normalise to lowercase
    tags = list(dict.fromkeys(m.lower() for m in _TAG_RE.findall(text)))
    references = list(dict.fromkeys(m.lower() for m in _REFERENCE_RE.findall(text)))
    if _TODO_RE.search(text) and "todo" not in tags:
        tags.append("todo")
    return ParsedNote(tags=tags, references=references)
