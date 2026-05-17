import shutil
from pathlib import Path


class LocalFolderAdapter:
    def __init__(self, folder: Path) -> None:
        self._folder = folder

    def upload(self, device_id: str, local_db: Path) -> None:
        self._folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_db, self._folder / f"{device_id}.db")

    def list_devices(self) -> list[str]:
        if not self._folder.exists():
            return []
        return [p.stem for p in self._folder.glob("*.db")]

    def download(self, device_id: str) -> bytes:
        path = self._folder / f"{device_id}.db"
        if not path.exists():
            raise FileNotFoundError(f"No remote DB for device {device_id!r}")
        return path.read_bytes()
