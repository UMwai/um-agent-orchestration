from __future__ import annotations
import subprocess
import os
from orchestrator.settings import ProviderCfg

def call_claude_interactive(prompt: str, cfg: ProviderCfg, cwd: str | None = None) -> str:
    """
    Claude Code interactive/full access mode. 
    Starts an interactive session and passes the repository context.
    """
    binary = cfg.binary or "claude"
    
    # Full access mode with dangerously-skip-permissions
    repo_path = cwd or os.getcwd()
    
    # Context prompt for full access mode
    context_prompt = f"""
You are being invoked by the AutoDev orchestration system in full access mode.

Repository: {repo_path}
System: Multi-agent orchestration with CLI-first approach
Architecture: FastAPI orchestrator + Redis + Git worktrees + Role-based agents

Available commands from this repo:
- make dev (start orchestrator)
- make run (start Redis + workers) 
- make install (setup dependencies)
- pytest (run tests)
- ruff (lint/format)

Task context: {prompt}

You have FULL ACCESS with permissions bypassed to read, modify, create, and delete files.
You can execute system commands and make any changes needed.
Please implement the requested functionality following the existing patterns.
"""
    
    # Use the configured args (should include --dangerously-skip-permissions)
    args = cfg.args or ["--dangerously-skip-permissions"]
    full = [binary] + args + ["-p", context_prompt]
    
    # Run Claude in full access mode with prompt
    try:
        proc = subprocess.run(full, cwd=cwd, capture_output=True, text=True)
        
        if proc.returncode != 0:
            raise RuntimeError(stderr.strip() or "claude full access CLI failed")
            
        return proc.stdout
        
    except Exception as e:
        # Fallback to normal mode if full access fails
        fallback_args = ["-p", "--output-format", "text"]
        fallback_cmd = [binary] + fallback_args + [context_prompt]
        proc = subprocess.run(fallback_cmd, cwd=cwd, capture_output=True, text=True)
        
        if proc.returncode != 0:
            raise RuntimeError(f"Full access mode failed: {e}. Fallback also failed: {proc.stderr}")
            
        return proc.stdout