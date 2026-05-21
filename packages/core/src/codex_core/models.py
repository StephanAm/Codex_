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
    references: list[str] = field(default_factory=list)


@dataclass
class Reference:
    id: int
    name: str


@dataclass
class InstanceKind:
    id: int
    name: str
    plural: str
    description: str
    uuid: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Instance:
    id: int
    name: str
    description: str
    type: InstanceKind
    references: list[str] = field(default_factory=list)
    uuid: str = ""
    created_at: str = ""
    updated_at: str = ""
