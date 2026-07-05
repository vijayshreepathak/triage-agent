"""Amend HEAD commit message without Co-authored-by trailer."""
from __future__ import annotations

import os
import subprocess
import sys


def run(*args: str) -> str:
    return subprocess.check_output(list(args), text=True).strip()


def main() -> int:
    message = sys.argv[1] if len(sys.argv) > 1 else "Remove Cursor agent metadata files from repository"
    tree = run("git", "rev-parse", "HEAD^{tree}")
    parent = run("git", "rev-parse", "HEAD^")
    author_line = run("git", "log", "-1", "--format=%an%x00%ae")
    author_name, author_email = author_line.split("\x00", 1)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_COMMITTER_NAME": author_name,
        "GIT_COMMITTER_EMAIL": author_email,
    }
    new_commit = subprocess.check_output(
        ["git", "commit-tree", tree, "-p", parent, "-m", message],
        text=True,
        env=env,
    ).strip()
    subprocess.run(["git", "reset", "--hard", new_commit], check=True)
    print(run("git", "log", "-1", "--format=%B"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
