from __future__ import annotations
import os, subprocess
from orchestrator.settings import load_settings

def ensure_worktree(branch: str) -> str:
    s = load_settings()
    repo = os.path.abspath(s.repo_path)
    base = os.path.join(repo, s.worktrees_base_dir)
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, branch.replace("/", "_"))
    if not os.path.exists(path):
        subprocess.run(["git", "worktree", "add", path, branch], cwd=repo, check=True)
    return path