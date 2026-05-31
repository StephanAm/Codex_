from cartographer.embeddings.base import EmbeddingBackend

VALID_BACKENDS = ("fastembed", "ollama")
DEFAULT_MODELS: dict[str, str] = {
    "fastembed": "BAAI/bge-small-en-v1.5",
    "ollama": "nomic-embed-text",
}


def build_backend(
    backend: str,
    model: str | None = None,
    ollama_url: str = "http://localhost:11434",
) -> EmbeddingBackend:
    if backend == "fastembed":
        from cartographer.embeddings.fastembed_backend import FastEmbedBackend
        return FastEmbedBackend(model or DEFAULT_MODELS["fastembed"])
    if backend == "ollama":
        from cartographer.embeddings.ollama_backend import OllamaBackend
        return OllamaBackend(model or DEFAULT_MODELS["ollama"], ollama_url)
    raise ValueError(
        f"Unknown embedding backend {backend!r}. "
        f"Choose one of: {', '.join(VALID_BACKENDS)}"
    )


__all__ = ["EmbeddingBackend", "build_backend", "VALID_BACKENDS", "DEFAULT_MODELS"]
