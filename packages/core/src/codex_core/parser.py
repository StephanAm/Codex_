import re
from dataclasses import dataclass

_TAG_RE = re.compile(r"#(\w+)")
_ENTITY_RE = re.compile(r"@(\w+)")


@dataclass
class ParsedNote:
    tags: list[str]
    entities: list[str]


def parse(text: str) -> ParsedNote:
    # Preserve order, deduplicate, normalise to lowercase
    tags = list(dict.fromkeys(m.lower() for m in _TAG_RE.findall(text)))
    entities = list(dict.fromkeys(m.lower() for m in _ENTITY_RE.findall(text)))
    return ParsedNote(tags=tags, entities=entities)
