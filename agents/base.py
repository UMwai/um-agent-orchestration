from __future__ import annotations
import subprocess
from dataclasses import dataclass
from orchestrator.settings import Settings
from orchestrator.models import TaskSpec
from providers import router
from monitoring.metrics import METRICS
from gitops import branch_manager, utils

@dataclass
class Agent:
    settings: Settings
    workdir: str
    feature_branch: str
    spec: TaskSpec

    def _llm(self, prompt: str) -> str:
        return router.call_models(prompt, cwd=self.workdir)

    def _run_cmd(self, cmd: list[str]) -> None:
        print(f"[RUN] {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=self.workdir)
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    def plan_and_execute(self) -> None:
        # Optionally overridden in derived classes; GenericAgent implements feedback loop
        branch_manager.rebase_onto_dev(self.feature_branch)
        # No-op here; GenericAgent is used for dynamic roles
        METRICS.commits_made.inc()