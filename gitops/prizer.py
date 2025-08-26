from __future__ import annotations
import os, subprocess, json, datetime as dt
from orchestrator.settings import load_settings
from monitoring.metrics import METRICS

def open_pr_if_needed():
    """
    For each feature branch with new commits since last PR, open or update a PR to dev.
    Uses GitHub CLI 'gh pr create'.
    """
    s = load_settings()
    repo = s.repo_path
    # list local branches matching our auto/* pattern
    branches = subprocess.check_output(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/auto/"],
                                      cwd=repo).decode().splitlines()
    for br in branches:
        # push branch
        subprocess.run(["git", "push", s.default_remote, br], cwd=repo, check=False)

        # check if PR exists
        pr_list = subprocess.run(["gh", "pr", "list", "--head", br, "--json", "number"],
                                 cwd=repo, capture_output=True, text=True)
        existing = json.loads(pr_list.stdout or "[]")
        if existing:
            continue

        title = f"{br} ready for review"
        body = f"Automated PR for {br} created at {dt.datetime.utcnow().isoformat()}Z"
        # reviewers optional; could parse config/teams for mapping
        cmd = ["gh", "pr", "create", "--base", s.dev_branch, "--head", br, "--title", title, "--body", body]
        subprocess.run(cmd, cwd=repo, check=False)
        METRICS.prs_opened.inc()

if __name__ == "__main__":
    open_pr_if_needed()