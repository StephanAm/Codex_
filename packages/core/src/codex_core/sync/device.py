import socket
from pathlib import Path
from uuid import uuid4

from ..db import connect


def get_device_id(db_path: Path | None = None) -> str:
    conn = connect(db_path)
    row = conn.execute("SELECT value FROM config WHERE key = 'device_id'").fetchone()
    if row:
        return str(row["value"])
    host = socket.gethostname().split(".")[0][:16]
    device_id = f"{host}-{str(uuid4())[:8]}"
    conn.execute("INSERT INTO config (key, value) VALUES ('device_id', ?)", (device_id,))
    conn.commit()
    return device_id
