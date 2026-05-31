from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingBackend(Protocol):
    @property
    def model_name(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...
