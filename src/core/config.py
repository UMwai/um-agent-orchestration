"""
Centralized configuration management for the Agent Orchestrator
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class OrchestratorConfig:
    """Configuration settings for the orchestrator"""

    # Database settings
    db_path: str = "tasks.db"

    # Directory settings
    base_dir: str = "/tmp/agent_orchestrator"
    context_dir: Optional[str] = None
    planning_sessions_dir: Optional[str] = None

    # Agent settings
    max_agents: int = 3
    agent_timeout: int = 30
    # Maximum runtime for spawned CLI agents before being considered stale.
    # Set to 0 or negative to disable auto-kill.
    max_agent_runtime_hours: Optional[int] = 24

    # Timeout for autonomous harness BashTool commands.
    # Set to 0 or negative to disable timeout.
    bash_timeout_seconds: Optional[int] = 120

    # Cleanup settings
    cleanup_days: int = 7

    # CLI settings
    use_api_mode: bool = False
    api_key: Optional[str] = None

    def __post_init__(self):
        """Set derived paths and load from environment"""
        # Load from environment
        self.db_path = os.getenv("ORCHESTRATOR_DB_PATH", self.db_path)
        self.base_dir = os.getenv("ORCHESTRATOR_BASE_DIR", self.base_dir)
        self.max_agents = int(os.getenv("MAX_AGENTS", self.max_agents))
        self.cleanup_days = int(os.getenv("CLEANUP_DAYS", self.cleanup_days))
        self.use_api_mode = os.getenv("USE_API_MODE", "false").lower() == "true"
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

        max_runtime_env = os.getenv("MAX_AGENT_RUNTIME_HOURS")
        if max_runtime_env is not None:
            try:
                self.max_agent_runtime_hours = int(max_runtime_env)
            except ValueError:
                pass

        bash_timeout_env = os.getenv("BASH_TOOL_TIMEOUT_SECONDS")
        if bash_timeout_env is not None:
            try:
                self.bash_timeout_seconds = int(bash_timeout_env)
            except ValueError:
                pass

        # Set derived paths
        if not self.context_dir:
            self.context_dir = f"{self.base_dir}/context"
        if not self.planning_sessions_dir:
            self.planning_sessions_dir = f"{self.base_dir}/planning_sessions"

    @property
    def base_path(self) -> Path:
        """Get base directory as Path object"""
        return Path(self.base_dir)

    @property
    def context_path(self) -> Path:
        """Get context directory as Path object"""
        return Path(self.context_dir)

    @property
    def planning_path(self) -> Path:
        """Get planning sessions directory as Path object"""
        return Path(self.planning_sessions_dir)


# Global configuration instance
config = OrchestratorConfig()


def get_config() -> OrchestratorConfig:
    """Get the global configuration instance"""
    return config


def update_config(**kwargs) -> OrchestratorConfig:
    """Update configuration with new values"""
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    config.__post_init__()  # Recalculate derived values
    return config
