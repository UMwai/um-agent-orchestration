from __future__ import annotations
import glob, os, yaml
from typing import Tuple
from orchestrator.settings import load_settings
from orchestrator.models import TaskSpec
from agents.generic import GenericAgent

def _load_role_prompts_from_dir(dir_path: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not os.path.isdir(dir_path):
        return out
    for p in glob.glob(os.path.join(dir_path, "*.yaml")):
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "prompt" in data:
            name = data.get("name") or os.path.splitext(os.path.basename(p))[0]
            out[name] = data
    return out

def get_role(role_name: str) -> Tuple[str, list[str], str]:
    """
    Returns (branch_prefix, reviewers, role_prompt) for role_name.
    Searches config roles + roles_dir/*.yaml entries.
    """
    s = load_settings()
    # config inline roles
    if role_name in s.roles:
        r = s.roles[role_name]
        return r.get("branch_prefix", f"feat/{role_name}"), r.get("reviewers", []), r.get("prompt", "")

    # roles/*.yaml
    roles = _load_role_prompts_from_dir(s.roles_dir)
    if role_name in roles:
        r = roles[role_name]
        return r.get("branch_prefix", f"feat/{role_name}"), r.get("reviewers", []), r.get("prompt", "")

    # default
    return f"feat/{role_name}", [], f"You are an autonomous agent for role '{role_name}'."

def get_agent_for_task(spec: TaskSpec) -> GenericAgent:
    branch_prefix, reviewers, prompt = get_role(spec.role)
    from orchestrator.settings import load_settings
    from gitops import branch_manager, worktrees

    # create feature branch
    feature_branch = branch_manager.prepare_feature_branch(team=spec.role, task_id=spec.id)
    wt_path = worktrees.ensure_worktree(feature_branch)

    settings = load_settings()
    agent = GenericAgent(settings=settings, workdir=wt_path, feature_branch=feature_branch, spec=spec, role_prompt=prompt)
    return agent