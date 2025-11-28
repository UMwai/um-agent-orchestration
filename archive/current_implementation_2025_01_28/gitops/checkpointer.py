from __future__ import annotations

import subprocess

from monitoring.metrics import METRICS
from orchestrator.settings import load_settings


def checkpoint_all_worktrees():
    """
    Stage and commit changes in every active worktree with a WIP message if there are diffs.
    This is intended to be run by a systemd timer every 30 minutes.
    """
    s = load_settings()
    repo = s.repo_path

    # list worktrees
    out = subprocess.check_output(["git", "worktree", "list", "--porcelain"], cwd=repo).decode()
    paths = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            paths.append(line.split(" ", 1)[1].strip())

    for p in paths:
        # if there are changes, commit
        diff = subprocess.run(
            ["git", "status", "--porcelain"], cwd=p, capture_output=True, text=True
        )
        if diff.stdout.strip():
            subprocess.run(["git", "add", "-A"], cwd=p, check=True)
            subprocess.run(["git", "commit", "-m", "chore: wip checkpoint"], cwd=p, check=True)
            METRICS.commits_made.inc()


if __name__ == "__main__":
    checkpoint_all_worktrees()
