"""Stop hook: auto-commit pending changes if a commit message file exists.

Behavior:
  - No uncommitted changes                → exit 0 (nothing to do)
  - Changes + .git/CLAUDE_COMMIT_MSG      → stage all, commit, delete file, exit 0
  - Changes + no commit message file      → print error to stderr, exit 1
                                            (non-zero causes Claude to be re-invoked
                                             with the error as a reminder)
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MSG_FILE = REPO / ".git" / "CLAUDE_COMMIT_MSG"
CO_AUTHOR = "Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"


def has_uncommitted_changes() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def main() -> int:
    if not has_uncommitted_changes():
        return 0

    if not MSG_FILE.exists():
        print(
            "STOP. ACTION REQUIRED BEFORE YOU DO ANYTHING ELSE:\n"
            "There are uncommitted changes and no commit message file.\n"
            f"Use the Write tool to create {MSG_FILE} with a concise commit message.\n"
            "Run `git diff --stat HEAD` first if you need to see what changed.\n"
            "Do not respond to the user, do not do any other work — write the file and stop.",
            file=sys.stderr,
        )
        return 1

    msg = MSG_FILE.read_text().strip()
    if not msg:
        print(f"🚨 Commit message file {MSG_FILE} is empty.", file=sys.stderr)
        return 1

    full_msg = f"{msg}\n\n{CO_AUTHOR}"

    subprocess.run(["git", "add", "-A"], cwd=REPO, check=True)

    result = subprocess.run(
        ["git", "commit", "-m", full_msg],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"🚨 git commit failed:\n{result.stderr}", file=sys.stderr)
        return result.returncode

    print(result.stdout.strip())
    MSG_FILE.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
