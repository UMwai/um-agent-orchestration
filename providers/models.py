"""
Model lists and constants for different AI providers.
"""

# Anthropic API Models
ANTHROPIC_MODELS = [
    "claude-opus-4-1-20250805",  # Latest and most capable model
    "claude-sonnet-4",  # High-performance model with exceptional reasoning
    "claude-opus-4",  # Previous flagship model
    "claude-3-5-sonnet-latest",  # Legacy model - latest 3.5 Sonnet
    "claude-3-5-sonnet-20241022",  # Legacy model - specific 3.5 version
    "claude-3-5-haiku-latest",  # Legacy model - latest 3.5 Haiku
    "claude-3-5-haiku-20241022",  # Legacy model - specific 3.5 Haiku
]

# OpenAI API Models
OPENAI_MODELS = [
    "gpt-5",  # Latest flagship model replacing GPT-4o
    "gpt-5-mini",  # GPT-5 mini variant for efficiency
    "gpt-5-nano",  # GPT-5 nano variant for lightweight tasks
    "o3",  # Latest reasoning model in o-series
    "o4-mini",  # Optimized reasoning model for fast, cost-efficient tasks
    "gpt-4.1",  # Specialized model for coding tasks
    "gpt-4o",  # Legacy flagship model
    "gpt-4o-mini",  # Legacy efficient model
]

# Google Gemini API Models
GEMINI_API_MODELS = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-pro-latest",
    "gemini-1.5-pro",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
    "gemini-1.0-pro",
]

# CLI Providers - typically use default/latest models managed by the CLI
CLI_DEFAULT_MODELS = {
    "claude_cli": ["default", "sonnet", "opus", "haiku"],
    "codex_cli": ["default", "o4-mini", "o3", "gpt-5", "gpt-4.1"],
    "gemini_cli": ["default", "gemini-2.5-pro", "gemini-2.5-flash"],
    "cursor_cli": ["default"],
}

# Interactive providers inherit from their CLI counterparts
INTERACTIVE_DEFAULT_MODELS = {
    "claude_interactive": CLI_DEFAULT_MODELS["claude_cli"],
    "codex_interactive": CLI_DEFAULT_MODELS["codex_cli"],
}


def get_models_for_provider(provider_name: str) -> list[str]:
    """
    Get the list of available models for a given provider.

    Args:
        provider_name: Name of the provider (e.g., 'anthropic_api', 'claude_cli')

    Returns:
        List of available model names
    """
    if provider_name == "anthropic_api":
        return ANTHROPIC_MODELS
    elif provider_name == "openai_api":
        return OPENAI_MODELS
    elif provider_name == "gemini_api":
        return GEMINI_API_MODELS
    elif provider_name in CLI_DEFAULT_MODELS:
        return CLI_DEFAULT_MODELS[provider_name]
    elif provider_name in INTERACTIVE_DEFAULT_MODELS:
        return INTERACTIVE_DEFAULT_MODELS[provider_name]
    else:
        return ["default"]


def get_provider_type(provider_name: str, mode: str) -> str:
    """
    Determine the provider type based on provider name and mode.

    Args:
        provider_name: Name of the provider
        mode: Provider mode ("cli", "api", "interactive")

    Returns:
        Provider type ("cli" or "api")
    """
    if mode == "api":
        return "api"
    elif mode in ["cli", "interactive"]:
        return "cli"
    else:
        # Fallback based on naming convention
        if "_api" in provider_name:
            return "api"
        else:
            return "cli"
