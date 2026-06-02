from __future__ import annotations

import subprocess

_DEFAULT_BIN = "claude"


class ClaudeBackend:
    """LLM backend that calls the Claude CLI in non-interactive print mode."""

    def __init__(self, bin_path: str = _DEFAULT_BIN, model: str | None = None) -> None:
        self._bin = bin_path
        self._model = model

    @property
    def model_name(self) -> str:
        return f"claude/{self._model}" if self._model else "claude"

    def generate(self, system: str, user: str) -> str:
        cmd = [self._bin, "-p", "--output-format", "text", "--system-prompt", system]
        if self._model:
            cmd += ["--model", self._model]

        try:
            result = subprocess.run(cmd, input=user, capture_output=True, text=True)
        except FileNotFoundError:
            raise RuntimeError(
                f"Claude CLI not found: {self._bin!r}. "
                "Make sure the claude CLI is installed and on PATH, "
                "or set SCRIBE_CLAUDE_BIN to the correct path."
            )

        if result.returncode != 0:
            detail = result.stderr.strip() or "(no stderr)"
            raise RuntimeError(f"Claude CLI failed (exit {result.returncode}): {detail}")

        return result.stdout.strip()
