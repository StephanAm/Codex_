from scribe.llm.base import LLMBackend

VALID_BACKENDS = ("ollama", "claude", "dummy")
DEFAULT_MODELS: dict[str, str] = {
    "ollama": "llama3",
    "claude": "",
    "dummy": "dummy",
}


def build_backend(
    backend: str,
    model: str | None = None,
    url: str = "http://localhost:11434",
    claude_bin: str = "claude",
) -> LLMBackend:
    if backend == "ollama":
        from scribe.llm.ollama_backend import OllamaBackend

        return OllamaBackend(model or DEFAULT_MODELS["ollama"], url)
    if backend == "claude":
        from scribe.llm.claude_backend import ClaudeBackend

        return ClaudeBackend(bin_path=claude_bin, model=model or None)
    if backend == "dummy":
        from scribe.llm.dummy_backend import DummyBackend

        return DummyBackend()
    raise ValueError(f"Unknown LLM backend {backend!r}. Choose one of: {', '.join(VALID_BACKENDS)}")


__all__ = ["LLMBackend", "build_backend", "VALID_BACKENDS", "DEFAULT_MODELS"]
