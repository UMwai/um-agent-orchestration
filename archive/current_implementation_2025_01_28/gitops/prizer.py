from __future__ import annotations

import datetime as dt
import json
import subprocess

from monitoring.metrics import METRICS
from orchestrator.settings import load_settings


def open_pr_if_needed():
    """
    For each feature branch with new commits since last PR, open or update a PR to dev.
    Uses GitHub CLI 'gh pr create'.
    """
    s = load_settings()
    repo = s.repo_path
    # list local branches matching our auto/* pattern
    branches = (
        subprocess.check_output(
            ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/auto/"], cwd=repo
        )
        .decode()
        .splitlines()
    )
    for br in branches:
        # push branch
        subprocess.run(["git", "push", s.default_remote, br], cwd=repo, check=False)

        # check if PR exists
        pr_list = subprocess.run(
            ["gh", "pr", "list", "--head", br, "--json", "number"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        existing = json.loads(pr_list.stdout or "[]")
        if existing:
            # PR exists, add to merge queue if not already there
            pr_number = str(existing[0]["number"])
            try:
                import asyncio

                from gitops.merge_coordinator import get_merge_coordinator

                loop = asyncio.get_event_loop()
                coordinator = get_merge_coordinator()
                _ = loop.create_task(coordinator.add_to_queue(pr_number, br))
            except (RuntimeError, ImportError):
                pass
            continue

        title = f"{br} ready for review"
        body = f"Automated PR for {br} created at {dt.datetime.utcnow().isoformat()}Z"
        # reviewers optional; could parse config/teams for mapping
        cmd = [
            "gh",
            "pr",
            "create",
            "--base",
            s.dev_branch,
            "--head",
            br,
            "--title",
            title,
            "--body",
            body,
        ]
        result = subprocess.run(cmd, cwd=repo, check=False, capture_output=True, text=True)

        if result.returncode == 0:
            # Extract PR number from output
            pr_number = None
            for line in result.stderr.splitlines():
                if "Pull request created:" in line or "https://github.com" in line:
                    pr_number = line.split("/")[-1]
                    break

            if pr_number:
                # Add to merge coordinator queue
                try:
                    import asyncio

                    from gitops.merge_coordinator import get_merge_coordinator

                    loop = asyncio.get_event_loop()
                    coordinator = get_merge_coordinator()
                    _ = loop.create_task(coordinator.add_to_queue(pr_number, br))
                except (RuntimeError, ImportError):
                    # No event loop running, schedule for later
                    pass

            METRICS.prs_opened.inc()


if __name__ == "__main__":
    open_pr_if_needed()
