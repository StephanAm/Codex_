import json
import urllib.request
from urllib.error import URLError

_DEFAULT_MODEL = "nomic-embed-text"
_DEFAULT_URL = "http://localhost:11434"


class OllamaBackend:
    def __init__(self, model: str = _DEFAULT_MODEL, url: str = _DEFAULT_URL) -> None:
        self._model_name = model
        self._url = url.rstrip("/")

    @property
    def model_name(self) -> str:
        return f"ollama/{self._model_name}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self._model_name, "input": texts}).encode()
        req = urllib.request.Request(
            f"{self._url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
        except URLError as exc:
            raise RuntimeError(
                f"Ollama is not reachable at {self._url}. Make sure Ollama is running: ollama serve"
            ) from exc
        result: list[list[float]] = data["embeddings"]
        return result
