from scribe.llm.base import LLMBackend

VALID_BACKENDS = ("ollama",)
DEFAULT_MODELS: dict[str, str] = {
    "ollama": "llama3",
}


def build_backend(
    backend: str,
    model: str | None = None,
    url: str = "http://localhost:11434",
) -> LLMBackend:
    if backend == "ollama":
        from scribe.llm.ollama_backend import OllamaBackend
        return OllamaBackend(model or DEFAULT_MODELS["ollama"], url)
    raise ValueError(
        f"Unknown LLM backend {backend!r}. "
        f"Choose one of: {', '.join(VALID_BACKENDS)}"
    )


__all__ = ["LLMBackend", "build_backend", "VALID_BACKENDS", "DEFAULT_MODELS"]
