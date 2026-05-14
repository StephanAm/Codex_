from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Note:
    id: int
    body: str
    created_at: datetime
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)


@dataclass
class Entity:
    id: int
    name: str
    entity_type: str | None
