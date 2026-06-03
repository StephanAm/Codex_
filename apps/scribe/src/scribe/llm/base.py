# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMBackend(Protocol):
    @property
    def model_name(self) -> str: ...

    def generate(self, system: str, user: str) -> str:
        """Send a system prompt and a user message; return the model's text response."""
        ...
