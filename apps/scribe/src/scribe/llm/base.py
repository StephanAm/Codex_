from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMBackend(Protocol):
    @property
    def model_name(self) -> str: ...

    def generate(self, system: str, user: str) -> str:
        """Send a system prompt and a user message; return the model's text response."""
        ...
