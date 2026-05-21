"""PyInstaller entry point for the FastAPI backend.

Runs uvicorn directly (no --reload) so it works inside a frozen executable.
The note_taker.api:serve() function uses reload=True which forks a subprocess
watcher — incompatible with PyInstaller's single-file mode.
"""

import uvicorn

from note_taker.api import PORT, app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
