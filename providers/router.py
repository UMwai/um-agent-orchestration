from __future__ import annotations

from orchestrator.settings import load_settings
from providers import (
    anthropic_provider,
    claude_cli_provider,
    claude_interactive_provider,
    codex_cli_provider,
    codex_interactive_provider,
    cursor_cli_provider,
    gemini_api_provider,
    gemini_cli_provider,
    openai_provider,
)


def call_models(
    prompt: str,
    cwd: str | None = None,
    full_access: bool = False,
    provider_override: str | None = None,
    model_override: str | None = None,
) -> tuple[str, str, str]:
    """
    Call AI models with optional provider and model override.
    Returns: (response, used_provider, used_model)
    """
    s = load_settings()

    # If specific provider is requested, try that first
    if provider_override and provider_override in s.providers:
        provider_order = [provider_override]
        # Fall back to configured order if override fails
        fallback_order = (
            s.full_access_order if full_access and s.full_access_order else s.provider_order
        )
        provider_order.extend([p for p in fallback_order if p != provider_override])
    else:
        # Choose provider order based on full_access mode
        provider_order = (
            s.full_access_order if full_access and s.full_access_order else s.provider_order
        )

    for name in provider_order:
        cfg = s.providers.get(name)
        if not cfg:
            continue

        try:
            # Override model if specified
            if model_override:
                cfg = cfg.copy()
                cfg.model = model_override

            response = None
            if name == "claude_interactive" and cfg.mode == "interactive":
                response = claude_interactive_provider.call_claude_interactive(prompt, cfg, cwd=cwd)
            elif name == "codex_interactive" and cfg.mode == "interactive":
                response = codex_interactive_provider.call_codex_interactive(prompt, cfg, cwd=cwd)
            elif name == "claude_cli" and cfg.mode == "cli":
                response = claude_cli_provider.call_claude_cli(prompt, cfg, cwd=cwd)
            elif name == "codex_cli" and cfg.mode == "cli":
                response = codex_cli_provider.call_codex_cli(prompt, cfg, cwd=cwd)
            elif name == "gemini_cli" and cfg.mode == "cli":
                response = gemini_cli_provider.call_gemini_cli(prompt, cfg, cwd=cwd)
            elif name == "cursor_cli" and cfg.mode == "cli":
                response = cursor_cli_provider.call_cursor_cli(prompt, cfg, cwd=cwd)
            elif name == "anthropic_api" and cfg.mode == "api":
                response = anthropic_provider.call_claude_api(prompt, cfg)
            elif name == "openai_api" and cfg.mode == "api":
                response = openai_provider.call_openai_api(prompt, cfg)
            elif name == "gemini_api" and cfg.mode == "api":
                response = gemini_api_provider.call_gemini_api(prompt, cfg)

            if response:
                return response, name, cfg.model or "unknown"

        except Exception as e:
            print(f"[provider:{name}] failed: {e}")
            # If this was the specifically requested provider, still try fallbacks
            if provider_override and name == provider_override:
                print(
                    f"[provider:{name}] was specifically requested but failed, trying fallbacks..."
                )
            continue

    raise RuntimeError("No provider succeeded.")


# Backward compatibility wrapper
def call_models_legacy(prompt: str, cwd: str | None = None, full_access: bool = False) -> str:
    """Legacy wrapper that returns only the response"""
    response, _, _ = call_models(prompt, cwd, full_access)
    return response
