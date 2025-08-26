from __future__ import annotations
import os
from openai import OpenAI
from orchestrator.settings import ProviderCfg

def call_openai_api(prompt: str, cfg: ProviderCfg) -> str:
    """
    Use OpenAI Responses API (modern replacement; Codex models deprecated Mar 2023).
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    model = cfg.model or "gpt-4o"
    try:
        resp = client.responses.create(
            model=model,
            input=[{"role": "user", "content": prompt}],
        )
        return resp.output_text
    except Exception:
        # Fallback to chat completions if responses not available
        chat = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return chat.choices[0].message.content or ""