from __future__ import annotations

import hashlib
import os
import subprocess

from orchestrator.settings import load_settings


def ensure_worktree(branch: str, repository_url: str = None, base_branch: str = None) -> str:
    s = load_settings()

    if repository_url:
        # Handle external repository
        repo_hash = hashlib.md5(repository_url.encode()).hexdigest()[:8]
        repo_name = repository_url.split("/")[-1].replace(".git", "")
        repo_dir = f"{repo_name}_{repo_hash}"

        # Base directory for external repos
        external_base = os.path.join(os.path.dirname(s.repo_path), "external_repos")
        os.makedirs(external_base, exist_ok=True)

        repo_path = os.path.join(external_base, repo_dir)

        # Clone repository if it doesn't exist
        if not os.path.exists(repo_path):
            subprocess.run(["git", "clone", repository_url, repo_path], check=True)

        # Create worktree within the external repo
        base = os.path.join(repo_path, "worktrees")
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, branch.replace("/", "_"))

        if not os.path.exists(path):
            # Fetch latest changes first
            subprocess.run(["git", "fetch"], cwd=repo_path, check=True)
            # Create worktree from specified base branch or default
            if base_branch:
                # Use specified base branch (e.g., "staging", "dev")
                target_branch = f"origin/{base_branch}"
                # Verify the branch exists
                try:
                    subprocess.run(
                        ["git", "rev-parse", target_branch],
                        cwd=repo_path,
                        check=True,
                        capture_output=True,
                    )
                except subprocess.CalledProcessError:
                    # Fallback to default if specified branch doesn't exist
                    target_branch = get_default_branch(repo_path)
            else:
                target_branch = get_default_branch(repo_path)
            subprocess.run(
                ["git", "worktree", "add", path, "-b", branch, target_branch],
                cwd=repo_path,
                check=True,
            )

        return path
    else:
        # Handle current repository (existing logic)
        repo = os.path.abspath(s.repo_path)
        base = os.path.join(repo, s.worktrees_base_dir)
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, branch.replace("/", "_"))
        if not os.path.exists(path):
            # Check if branch already exists
            branch_exists = (
                subprocess.run(
                    ["git", "rev-parse", "--verify", branch], cwd=repo, capture_output=True
                ).returncode
                == 0
            )

            if branch_exists:
                # Branch exists, create worktree from it
                subprocess.run(["git", "worktree", "add", path, branch], cwd=repo, check=True)
            else:
                # Branch doesn't exist, create it from dev branch
                base_branch = base_branch or s.dev_branch
                subprocess.run(
                    ["git", "worktree", "add", path, "-b", branch, f"origin/{base_branch}"],
                    cwd=repo,
                    check=True,
                )
        return path


def get_default_branch(repo_path: str) -> str:
    """Get the default branch (main/master) of a repository"""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().replace("refs/remotes/origin/", "")
    except subprocess.CalledProcessError:
        # Fallback to common defaults
        for branch in ["main", "master"]:
            try:
                subprocess.run(
                    ["git", "rev-parse", f"origin/{branch}"],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                )
                return f"origin/{branch}"
            except subprocess.CalledProcessError:
                continue
        return "origin/main"  # Final fallback
