from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Note:
    id: int
    uuid: str
    body: str
    created_at: datetime
    updated_at: datetime
    time_stamp: datetime
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)


@dataclass
class Entity:
    id: int
    name: str
    entity_type: str | None
