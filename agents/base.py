from __future__ import annotations

import subprocess
from dataclasses import dataclass

from gitops import branch_manager
from monitoring.metrics import METRICS
from orchestrator.models import TaskSpec
from orchestrator.settings import Settings
from providers import router


@dataclass
class Agent:
    settings: Settings
    workdir: str
    feature_branch: str
    spec: TaskSpec

    def _llm(self, prompt: str) -> tuple[str, str, str]:
        """
        Call LLM with configured provider/model preferences.
        Returns: (response, used_provider, used_model)
        """
        return router.call_models(
            prompt,
            cwd=self.workdir,
            full_access=self.spec.full_access,
            provider_override=self.spec.provider_override,
            model_override=self.spec.model,
        )

    def _llm_response(self, prompt: str) -> str:
        """Legacy method that returns only the response"""
        response, _, _ = self._llm(prompt)
        return response

    def _run_cmd(self, cmd: list[str]) -> None:
        print(f"[RUN] {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=self.workdir)
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    def plan_and_execute(self) -> dict:
        # Optionally overridden in derived classes; GenericAgent implements feedback loop
        branch_manager.rebase_onto_dev(self.feature_branch)
        # No-op here; GenericAgent is used for dynamic roles
        METRICS.commits_made.inc()

        # Return basic metadata - subclasses should override
        return {
            "provider": self.spec.provider_override or "default",
            "model": self.spec.model or "default",
            "completed": True,
        }
