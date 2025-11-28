from __future__ import annotations

import os

import anthropic

from orchestrator.settings import ProviderCfg


def call_claude_api(prompt: str, cfg: ProviderCfg) -> str:
    # Anthropic Messages API official
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    model = cfg.model or "claude-opus-4-1-20250805"
    resp = client.messages.create(
        model=model,
        max_tokens=cfg.max_tokens or 4096,
        messages=[{"role": "user", "content": prompt}],
    )
    out = []
    for blk in resp.content:
        if blk.type == "text":
            out.append(blk.text)
    return "\n".join(out)
