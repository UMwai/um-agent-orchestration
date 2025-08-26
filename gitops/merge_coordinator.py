from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from monitoring.metrics import METRICS
from orchestrator.settings import load_settings


class MergeStatus(str, Enum):
    QUEUED = "queued"
    REBASING = "rebasing"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class MergePriority(int, Enum):
    SECURITY = 1
    BUG = 2
    FEATURE = 3
    DOCS = 4


@dataclass
class MergeRequest:
    pr_id: str
    branch: str
    priority: MergePriority
    created_at: datetime
    status: MergeStatus = MergeStatus.QUEUED
    conflict_files: list[str] = None

    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class MergeCoordinator:
    def __init__(self):
        self.settings = load_settings()
        self.merge_queue: list[MergeRequest] = []
        self.active_merge: MergeRequest | None = None
        self.merge_lock = asyncio.Lock()

    def detect_branch_priority(self, branch: str) -> MergePriority:
        """Detect priority based on branch name patterns"""
        branch_lower = branch.lower()
        if any(keyword in branch_lower for keyword in ["security", "sec", "vuln"]):
            return MergePriority.SECURITY
        elif any(keyword in branch_lower for keyword in ["fix", "bug", "hotfix"]):
            return MergePriority.BUG
        elif any(keyword in branch_lower for keyword in ["docs", "doc", "readme"]):
            return MergePriority.DOCS
        else:
            return MergePriority.FEATURE

    def detect_conflicts(self, branch: str) -> list[str]:
        """Check if branch would have conflicts when merged to dev"""
        try:
            # Fetch latest dev branch
            subprocess.run(
                ["git", "fetch", self.settings.default_remote, self.settings.dev_branch],
                cwd=self.settings.repo_path,
                check=True,
                capture_output=True,
            )

            # Check for merge conflicts without actually merging
            result = subprocess.run(
                [
                    "git",
                    "merge-tree",
                    f"{self.settings.default_remote}/{self.settings.dev_branch}",
                    branch,
                ],
                cwd=self.settings.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0 or "<<<<<<< " in result.stdout:
                # Parse conflict files from merge-tree output
                conflict_files = []
                for line in result.stdout.splitlines():
                    if line.startswith("changed in both"):
                        conflict_files.append(line.split()[-1])
                return conflict_files
            return []

        except subprocess.CalledProcessError:
            return ["unknown_conflict"]

    async def add_to_queue(
        self, pr_id: str, branch: str, priority: MergePriority | None = None
    ) -> str:
        """Add PR to merge queue with priority detection"""
        if priority is None:
            priority = self.detect_branch_priority(branch)

        # Check for conflicts
        conflict_files = self.detect_conflicts(branch)

        merge_req = MergeRequest(
            pr_id=pr_id,
            branch=branch,
            priority=priority,
            created_at=datetime.utcnow(),
            conflict_files=conflict_files,
            status=MergeStatus.CONFLICT if conflict_files else MergeStatus.QUEUED,
        )

        # Insert in priority order
        self.merge_queue.append(merge_req)
        self.merge_queue.sort()

        METRICS.merge_requests_queued.inc()

        if conflict_files:
            METRICS.merge_conflicts_detected.inc()
            return f"PR {pr_id} queued with conflicts in: {', '.join(conflict_files)}"

        return f"PR {pr_id} queued with priority {priority.name}"

    def attempt_auto_rebase(self, merge_req: MergeRequest) -> bool:
        """Attempt to auto-rebase branch onto latest dev"""
        try:
            merge_req.status = MergeStatus.REBASING

            # Create temporary worktree for rebase
            temp_path = os.path.join(self.settings.repo_path, "temp_rebase", merge_req.pr_id)
            os.makedirs(temp_path, exist_ok=True)

            # Add worktree and perform rebase
            subprocess.run(
                ["git", "worktree", "add", temp_path, merge_req.branch],
                cwd=self.settings.repo_path,
                check=True,
            )

            # Fetch latest dev
            subprocess.run(
                ["git", "fetch", self.settings.default_remote, self.settings.dev_branch],
                cwd=temp_path,
                check=True,
            )

            # Attempt rebase
            result = subprocess.run(
                ["git", "rebase", f"{self.settings.default_remote}/{self.settings.dev_branch}"],
                cwd=temp_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Push rebased branch
                subprocess.run(
                    [
                        "git",
                        "push",
                        "--force-with-lease",
                        self.settings.default_remote,
                        merge_req.branch,
                    ],
                    cwd=temp_path,
                    check=True,
                )

                # Clean up temp worktree
                subprocess.run(
                    ["git", "worktree", "remove", temp_path],
                    cwd=self.settings.repo_path,
                    check=True,
                )

                merge_req.status = MergeStatus.QUEUED
                merge_req.conflict_files = []
                METRICS.auto_rebases_successful.inc()
                return True
            else:
                # Clean up temp worktree
                subprocess.run(
                    ["git", "worktree", "remove", "--force", temp_path],
                    cwd=self.settings.repo_path,
                    check=False,
                )

                merge_req.status = MergeStatus.CONFLICT
                METRICS.auto_rebases_failed.inc()
                return False

        except Exception:
            merge_req.status = MergeStatus.FAILED
            return False

    async def process_merge_queue(self) -> dict[str, Any]:
        """Process the merge queue sequentially"""
        async with self.merge_lock:
            if self.active_merge is not None:
                return {"status": "busy", "active_merge": self.active_merge.pr_id}

            # Find next queued item
            next_merge = None
            for req in self.merge_queue:
                if req.status == MergeStatus.QUEUED:
                    next_merge = req
                    break

            if not next_merge:
                return {"status": "idle", "queue_length": len(self.merge_queue)}

            self.active_merge = next_merge

            try:
                # If has conflicts, try auto-rebase first
                if next_merge.conflict_files:
                    if not self.attempt_auto_rebase(next_merge):
                        return {
                            "status": "conflict_unresolved",
                            "pr_id": next_merge.pr_id,
                            "conflicts": next_merge.conflict_files,
                        }

                # Attempt merge
                next_merge.status = MergeStatus.MERGING
                result = await self.merge_pr(next_merge.pr_id)

                if result["success"]:
                    next_merge.status = MergeStatus.COMPLETED
                    self.merge_queue.remove(next_merge)
                    METRICS.prs_merged.inc()

                    # Trigger rebase of remaining queue
                    await self.rebase_pending_prs()
                else:
                    next_merge.status = MergeStatus.FAILED

                return result

            finally:
                self.active_merge = None

    async def merge_pr(self, pr_id: str) -> dict[str, Any]:
        """Merge a specific PR using GitHub CLI"""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "merge",
                    pr_id,
                    "--squash",  # or --merge/--rebase based on preference
                    "--delete-branch",
                ],
                cwd=self.settings.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )

            return {"success": True, "pr_id": pr_id, "output": result.stdout}

        except subprocess.CalledProcessError as e:
            return {"success": False, "pr_id": pr_id, "error": e.stderr}

    async def rebase_pending_prs(self):
        """Rebase all pending PRs onto latest dev after a successful merge"""
        for req in self.merge_queue:
            if req.status == MergeStatus.QUEUED:
                # Update conflict detection
                req.conflict_files = self.detect_conflicts(req.branch)
                if req.conflict_files:
                    req.status = MergeStatus.CONFLICT

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status for monitoring"""
        return {
            "active_merge": self.active_merge.pr_id if self.active_merge else None,
            "queue": [
                {
                    "pr_id": req.pr_id,
                    "branch": req.branch,
                    "priority": req.priority.name,
                    "status": req.status.value,
                    "conflicts": req.conflict_files or [],
                }
                for req in self.merge_queue
            ],
            "queue_length": len(self.merge_queue),
        }


# Global instance - lazy loaded to avoid circular imports
merge_coordinator = None


def get_merge_coordinator():
    global merge_coordinator
    if merge_coordinator is None:
        merge_coordinator = MergeCoordinator()
    return merge_coordinator
