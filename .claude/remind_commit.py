"""PostToolUse hook: remind Claude to write a commit message after every file edit."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path("/home/stephan/Code/note-taker")
MSG_FILE = REPO / ".git" / "CLAUDE_COMMIT_MSG"

data = json.load(sys.stdin)
edited = data.get("tool_input", {}).get("file_path", "")

if not edited.startswith(str(REPO)):
    sys.exit(0)

if MSG_FILE.exists():
    sys.exit(0)

result = subprocess.run(
    ["git", "status", "--porcelain"],
    cwd=REPO,
    capture_output=True,
    text=True,
)
if not result.stdout.strip():
    sys.exit(0)

print(
    "COMMIT REMINDER: there are uncommitted changes in this repo. "
    "Before you stop, write a commit message to "
    f"{MSG_FILE} using the Write tool."
)
