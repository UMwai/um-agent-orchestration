from __future__ import annotations
import subprocess
from orchestrator.settings import load_settings

def prepare_feature_branch(team: str, task_id: str) -> str:
    s = load_settings()
    branch = f"auto/{team}/{task_id}"
    # create from latest dev
    subprocess.run(["git", "fetch", s.default_remote, s.dev_branch], cwd=s.repo_path, check=True)
    # create branch if missing
    res = subprocess.run(["git", "rev-parse", "--verify", branch], cwd=s.repo_path)
    if res.returncode != 0:
        subprocess.run(["git", "checkout", "-B", branch, f"{s.default_remote}/{s.dev_branch}"], cwd=s.repo_path, check=True)
    return branch

def rebase_onto_dev(branch: str) -> None:
    s = load_settings()
    subprocess.run(["git", "fetch", s.default_remote, s.dev_branch], cwd=s.repo_path, check=True)
    # Use autostash to avoid dirty-tree issues during rebase
    subprocess.run(["git", "checkout", branch], cwd=s.repo_path, check=True)
    subprocess.run(["git", "rebase", "--autostash", f"{s.default_remote}/{s.dev_branch}"], cwd=s.repo_path, check=True)