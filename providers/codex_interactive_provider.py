from __future__ import annotations
import subprocess
import os
from orchestrator.settings import ProviderCfg

def call_codex_interactive(prompt: str, cfg: ProviderCfg, cwd: str | None = None) -> str:
    """
    Codex interactive/full access mode.
    Provides full repository context and interactive capabilities.
    """
    binary = cfg.binary or "codex"
    repo_path = cwd or os.getcwd()
    
    # Full access context for Codex
    context_prompt = f"""
You are being invoked by the AutoDev orchestration system in full access mode.

Repository: {repo_path}
System: Multi-agent orchestration with CLI-first approach
Architecture: FastAPI orchestrator + Redis + Git worktrees + Role-based agents

Repository structure:
- orchestrator/: FastAPI server and task dispatching
- agents/: Role-based agents (backend, frontend, data, ml, generic)
- providers/: CLI and API providers for different models
- gitops/: Git worktree management and automated hygiene
- config/: System configuration and role definitions
- roles/: Custom role YAML definitions

Available development commands:
- make dev: Start FastAPI server at localhost:8000
- make run: Start Redis server and RQ worker
- make install: Install dependencies and pre-commit hooks
- pytest: Run test suite
- ruff: Lint and format code
- mypy: Type checking

Task context: {prompt}

You have FULL ACCESS with auto-approval and danger-full-access sandbox.
You can execute any commands, modify any files, and make system changes.
Please implement the requested functionality following existing patterns.
"""
    
    # Use full access configuration
    args = cfg.args or ["--ask-for-approval", "never", "--sandbox", "danger-full-access", "exec"]
    full = [binary] + args + [context_prompt]
    
    try:
        proc = subprocess.run(full, cwd=cwd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "codex full access CLI failed")
        return proc.stdout
        
    except Exception as e:
        # Fallback to normal exec mode
        fallback_cmd = [binary, "exec", context_prompt]
        proc = subprocess.run(fallback_cmd, cwd=cwd, capture_output=True, text=True)
        
        if proc.returncode != 0:
            raise RuntimeError(f"Full access mode failed: {e}. Fallback also failed: {proc.stderr}")
            
        return proc.stdout