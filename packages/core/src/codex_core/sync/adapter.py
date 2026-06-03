# Copyright (C) 2026 Stephan Marais
# SPDX-License-Identifier: AGPL-3.0-or-later

from pathlib import Path
from typing import Protocol, runtime_checkable


class AuthRequired(Exception):
    """Raised when an interactive OAuth flow is needed before sync can proceed."""


@runtime_checkable
class StorageAdapter(Protocol):
    def upload(self, device_id: str, local_db: Path) -> None: ...
    def list_devices(self) -> list[str]: ...
    def download(self, device_id: str) -> bytes: ...
