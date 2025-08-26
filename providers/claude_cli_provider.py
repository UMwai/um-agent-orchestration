from __future__ import annotations
import subprocess
from orchestrator.settings import ProviderCfg

def call_claude_cli(prompt: str, cfg: ProviderCfg, cwd: str | None = None) -> str:
    # Claude Code CLI: non-interactive via -p; supports --output-format json|text
    binary = cfg.binary or "claude"
    args = cfg.args or ["-p", "--output-format", "text"]
    full = [binary] + args + [prompt]
    proc = subprocess.run(full, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "claude CLI failed")
    return proc.stdout