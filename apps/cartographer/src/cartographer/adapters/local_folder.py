from pathlib import Path


class LocalFolderAdapter:
    def __init__(self, folder: Path) -> None:
        self._folder = folder

    def list_devices(self) -> list[str]:
        if not self._folder.exists():
            return []
        return [p.stem for p in self._folder.glob("*.db")]

    def download(self, device_id: str) -> bytes:
        path = self._folder / f"{device_id}.db"
        if not path.exists():
            raise FileNotFoundError(f"No DB for device {device_id!r}")
        return path.read_bytes()
