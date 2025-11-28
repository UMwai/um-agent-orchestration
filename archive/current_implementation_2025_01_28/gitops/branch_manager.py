from __future__ import annotations

import subprocess

from orchestrator.settings import load_settings


def prepare_feature_branch(team: str, task_id: str) -> str:
    s = load_settings()
    branch = f"auto/{team}/{task_id}"
    # Fetch latest changes to ensure we have up-to-date refs
    subprocess.run(["git", "fetch", s.default_remote, s.dev_branch], cwd=s.repo_path, check=True)
    # Branch creation will be handled by worktrees.ensure_worktree()
    return branch


def rebase_onto_dev(branch: str, workdir: str = None) -> None:
    s = load_settings()
    cwd = workdir or s.repo_path

    # Fetch latest changes
    subprocess.run(["git", "fetch", s.default_remote, s.dev_branch], cwd=cwd, check=True)

    # If we have a workdir (worktree), we're already on the correct branch
    # Otherwise, checkout the branch in main repo
    if not workdir:
        subprocess.run(["git", "checkout", branch], cwd=cwd, check=True)

    # Rebase onto latest dev branch
    subprocess.run(
        ["git", "rebase", "--autostash", f"{s.default_remote}/{s.dev_branch}"],
        cwd=cwd,
        check=True,
    )


def rebase_all_pending_prs() -> list[str]:
    """Rebase all auto/* branches onto latest dev branch"""
    s = load_settings()
    repo = s.repo_path

    # Fetch latest dev
    subprocess.run(["git", "fetch", s.default_remote, s.dev_branch], cwd=repo, check=True)

    # Get all auto/* branches
    branches = (
        subprocess.check_output(
            ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/auto/"], cwd=repo
        )
        .decode()
        .splitlines()
    )

    rebased_branches = []
    failed_branches = []

    for branch in branches:
        try:
            # Switch to branch and rebase
            subprocess.run(["git", "checkout", branch], cwd=repo, check=True)
            result = subprocess.run(
                ["git", "rebase", "--autostash", f"{s.default_remote}/{s.dev_branch}"],
                cwd=repo,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Force push the rebased branch
                subprocess.run(
                    ["git", "push", "--force-with-lease", s.default_remote, branch],
                    cwd=repo,
                    check=True,
                )
                rebased_branches.append(branch)
            else:
                # Rebase failed, likely conflicts
                subprocess.run(["git", "rebase", "--abort"], cwd=repo, check=False)
                failed_branches.append(branch)

        except subprocess.CalledProcessError:
            failed_branches.append(branch)

    return rebased_branches, failed_branches


def get_branch_conflicts(branch: str) -> list[str]:
    """Get list of files that would conflict when merging branch to dev"""
    s = load_settings()
    try:
        subprocess.run(
            ["git", "fetch", s.default_remote, s.dev_branch], cwd=s.repo_path, check=True
        )

        result = subprocess.run(
            ["git", "merge-tree", f"{s.default_remote}/{s.dev_branch}", branch],
            cwd=s.repo_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or "<<<<<<< " in result.stdout:
            conflict_files = []
            for line in result.stdout.splitlines():
                if line.startswith("changed in both"):
                    conflict_files.append(line.split()[-1])
            return conflict_files
        return []

    except subprocess.CalledProcessError:
        return ["unknown_conflict"]
