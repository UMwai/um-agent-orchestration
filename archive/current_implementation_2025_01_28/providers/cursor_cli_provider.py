from __future__ import annotations

import subprocess

from orchestrator.settings import ProviderCfg


def call_cursor_cli(prompt: str, cfg: ProviderCfg, cwd: str | None = None) -> str:
    """
    Cursor CLI print mode: 'cursor-agent -p "..."' with optional --output-format text|json.
    """
    binary = cfg.binary or "cursor-agent"
    args = cfg.args or ["-p", "--output-format", "text"]
    full = [binary] + args + [prompt]
    proc = subprocess.run(full, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "cursor CLI failed")
    return proc.stdout
