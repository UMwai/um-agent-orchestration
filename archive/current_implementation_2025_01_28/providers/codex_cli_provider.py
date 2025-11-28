from __future__ import annotations

import subprocess

from orchestrator.settings import ProviderCfg


def call_codex_cli(prompt: str, cfg: ProviderCfg, cwd: str | None = None) -> str:
    """
    OpenAI Codex CLI (terminal agent). Non-interactive 'automation' mode is 'codex exec "..."'.
    The CLI uses OpenAI Responses API under the hood (not the deprecated 2021 Codex model).
    """
    binary = cfg.binary or "codex"
    args = cfg.args or ["exec"]
    full = [binary] + args + [prompt]
    proc = subprocess.run(full, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "codex CLI failed")
    return proc.stdout
