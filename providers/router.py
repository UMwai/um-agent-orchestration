from __future__ import annotations
from typing import Optional
from orchestrator.settings import load_settings
from providers import (
    anthropic_provider,
    openai_provider,
    claude_cli_provider,
    codex_cli_provider,
    gemini_cli_provider,
    cursor_cli_provider,
    claude_interactive_provider,
    codex_interactive_provider,
)

def call_models(prompt: str, cwd: Optional[str] = None, full_access: bool = False) -> str:
    s = load_settings()
    
    # Choose provider order based on full_access mode
    provider_order = s.full_access_order if full_access and hasattr(s, 'full_access_order') else s.provider_order
    
    for name in provider_order:
        cfg = s.providers.get(name)
        if not cfg:
            continue
        try:
            if name == "claude_interactive" and cfg.mode == "interactive":
                return claude_interactive_provider.call_claude_interactive(prompt, cfg, cwd=cwd)
            if name == "codex_interactive" and cfg.mode == "interactive":
                return codex_interactive_provider.call_codex_interactive(prompt, cfg, cwd=cwd)
            if name == "claude_cli" and cfg.mode == "cli":
                return claude_cli_provider.call_claude_cli(prompt, cfg, cwd=cwd)
            if name == "codex_cli" and cfg.mode == "cli":
                return codex_cli_provider.call_codex_cli(prompt, cfg, cwd=cwd)
            if name == "gemini_cli" and cfg.mode == "cli":
                return gemini_cli_provider.call_gemini_cli(prompt, cfg, cwd=cwd)
            if name == "cursor_cli" and cfg.mode == "cli":
                return cursor_cli_provider.call_cursor_cli(prompt, cfg, cwd=cwd)
            if name == "anthropic_api" and cfg.mode == "api":
                return anthropic_provider.call_claude_api(prompt, cfg)
            if name == "openai_api" and cfg.mode == "api":
                return openai_provider.call_openai_api(prompt, cfg)
        except Exception as e:
            print(f"[provider:{name}] failed: {e}")
            continue
    raise RuntimeError("No provider succeeded.")