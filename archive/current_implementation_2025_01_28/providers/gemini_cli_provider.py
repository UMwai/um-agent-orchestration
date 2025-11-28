from __future__ import annotations

import subprocess

from orchestrator.settings import ProviderCfg


def call_gemini_cli(prompt: str, cfg: ProviderCfg, cwd: str | None = None) -> str:
    """
    Gemini CLI non-interactive mode uses '-p "..."'.
    """
    binary = cfg.binary or "gemini"
    args = cfg.args or ["-p"]
    full = [binary] + args + [prompt]
    proc = subprocess.run(full, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gemini CLI failed")
    return proc.stdout
