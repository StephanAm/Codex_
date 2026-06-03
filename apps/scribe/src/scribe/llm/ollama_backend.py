from __future__ import annotations

_DEFAULT_MODEL = "llama3"
_DEFAULT_URL = "http://localhost:11434"


class OllamaBackend:
    def __init__(self, model: str = _DEFAULT_MODEL, url: str = _DEFAULT_URL) -> None:
        self._model = model
        self._url = url.rstrip("/")

    @property
    def model_name(self) -> str:
        return f"ollama/{self._model}"

    def generate(self, system: str, user: str) -> str:
        try:
            import ollama
        except ImportError as exc:
            raise RuntimeError("The 'ollama' package is required. Install it with: uv add ollama") from exc

        client = ollama.Client(host=self._url)
        try:
            response = client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            # Catch connection errors, model-not-found, etc.
            raise RuntimeError(
                f"Ollama request failed (model={self._model!r}, url={self._url!r}): {exc}\n"
                f"Make sure Ollama is running and the model is available: ollama pull {self._model}"
            ) from exc

        return response.message.content or ""
