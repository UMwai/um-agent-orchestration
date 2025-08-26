from __future__ import annotations
import json
from dataclasses import dataclass
from agents.base import Agent
from orchestrator.settings import load_settings
from providers import router
from gitops import branch_manager, utils

@dataclass
class GenericAgent(Agent):
    role_prompt: str = ""

    def _llm(self, prompt: str) -> str:
        return router.call_models(prompt, cwd=self.workdir)

    def plan_and_execute(self) -> None:
        # Rebase onto latest dev
        branch_manager.rebase_onto_dev(self.feature_branch)

        s = load_settings()
        preamble = f"""
You are an autonomous agent for role: {self.spec.role}.
Role guidance:
{self.role_prompt}

Task: {self.spec.title}
Description: {self.spec.description}

Acceptance (JSON):
{json.dumps(self.spec.acceptance, indent=2)}
Working directory: {self.workdir}

Rules:
- Produce minimal, high-quality patches.
- Run ruff, mypy, and pytest (or role-specific checks) before iterating.
- Follow Conventional Commits.
"""
        first = self._llm(preamble + "\nNow output the first patch as unified diffs or '=== file:PATH ===' blocks.")
        utils.apply_patchlike_text(self.workdir, first)
        self._run_cmd(["git", "add", "-A"])
        self._run_cmd(["git", "commit", "-m", f"feat({self.spec.role}): initial patch for {self.spec.id}"])

        # feedback loop
        for i in range(1, 8):
            logs = utils.run_checks_and_tests(self.workdir)
            if logs["status"] == "pass":
                break
            fix = self._llm(
                f"""Tests/lints failed on iteration {i}. Logs:

<LOGS>
{logs['combined'][:8000]}
</LOGS>

Return ONLY a minimal patch (diffs or file blocks) to resolve failures."""
            )
            utils.apply_patchlike_text(self.workdir, fix)
            self._run_cmd(["git", "add", "-A"])
            self._run_cmd(["git", "commit", "-m", f"fix({self.spec.role}): iter {i} for {self.spec.id}"])
        else:
            raise RuntimeError("Feedback loop exhausted without passing tests")

        # final checkpoint
        self._run_cmd(["git", "commit", "--allow-empty", "-m", f"chore({self.spec.role}): ready for PR {self.spec.id}"])