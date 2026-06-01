from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastembed import TextEmbedding

_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class FastEmbedBackend:
    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model_name = model
        self._model: TextEmbedding | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load(self) -> Any:
        if self._model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise ImportError(
                    "fastembed support requires the embeddings extra: "
                    "uv sync --all-packages --extra embeddings"
                ) from exc
            self._model = TextEmbedding(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        return [v.tolist() for v in model.embed(texts)]
