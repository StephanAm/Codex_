"""Entry point for `uv run gui` — wraps GUI development commands."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_REPO_DIR = Path(__file__).parent.parent.parent
_GUI_DIR = _REPO_DIR / "gui"
_PORT = 8765


def _find_pid_on_port() -> str:
    result = subprocess.run(["lsof", "-ti", f":{_PORT}"], capture_output=True, text=True)
    return result.stdout.strip()


def _kill_port() -> None:
    pid = _find_pid_on_port()
    if pid:
        os.kill(int(pid), signal.SIGTERM)
        print(f"Stopped process {pid} (was on port {_PORT}).")
    else:
        print(f"Nothing is listening on port {_PORT}.")


def _npm(args: list[str]) -> None:
    nvm_sh = os.path.expanduser("~/.nvm/nvm.sh")
    cargo_bin = os.path.expanduser("~/.cargo/bin")
    parts: list[str] = []
    if os.path.exists(nvm_sh):
        parts += [f'source "{nvm_sh}"', "nvm use 24 --silent"]
    parts += [f'export PATH="{cargo_bin}:$PATH"', " ".join(["npm"] + args)]
    subprocess.run(["bash", "-c", " && ".join(parts)], cwd=_GUI_DIR, check=True)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: gui {api|kill|dev|build}", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "kill":
        _kill_port()

    elif cmd == "api":
        pid = _find_pid_on_port()
        if pid:
            proc = subprocess.run(["ps", "-p", pid, "-o", "comm="], capture_output=True, text=True).stdout.strip()
            print(f"Port {_PORT} is held by '{proc}' (pid {pid}) — stopping it.")
            os.kill(int(pid), signal.SIGTERM)
            time.sleep(0.5)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "note_taker.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(_PORT),
                "--reload",
            ],
            cwd=_REPO_DIR,
            check=True,
        )

    elif cmd == "dev":
        _npm(["run", "tauri", "dev"])

    elif cmd == "build":
        _npm(["run", "build"])

    else:
        print(f"Unknown command: {cmd!r}", file=sys.stderr)
        print("Usage: gui {api|kill|dev|build}", file=sys.stderr)
        sys.exit(1)
