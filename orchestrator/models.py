from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    id: str
    title: str
    description: str
    role: str  # e.g., "backend", "data_analyst", "computational_biologist", "fund_manager"
    acceptance: dict[str, Any] = Field(default_factory=dict)
    target_dir: str = "."
    full_access: bool = False  # Enable full access mode
    provider_override: str | None = None  # Override specific provider
    model: str | None = None  # Specific model to use (e.g., "claude-3-5-sonnet-latest", "gpt-4o")
    repository_url: str | None = None  # Git repository URL (if different from current)
    base_branch: str | None = (
        None  # Base branch to create feature branch from (e.g., "staging", "dev")
    )


class TaskStatus(BaseModel):
    id: str
    role: str
    branch: str
    state: str  # "queued" | "running" | "passed" | "failed" | "error"
    last_error: str | None = None
    provider: str | None = None  # Which provider was used
    model: str | None = None  # Which model was used


class ProviderInfo(BaseModel):
    name: str
    display_name: str
    mode: str  # "cli", "api", "interactive"
    provider_type: str  # "cli" or "api" - distinguishes between CLI tools and API providers
    model: str | None = None
    available_models: list[str] = Field(default_factory=list)
    description: str | None = None
    available: bool = True
    capabilities: list[str] = Field(default_factory=list)
    status_details: dict = Field(default_factory=dict)


class ModelPreference(BaseModel):
    user_id: str = "default"  # For future multi-user support
    preferred_provider: str | None = None
    preferred_model: str | None = None
    full_access_preferred: bool = False
    role_preferences: dict[str, str] = Field(default_factory=dict)  # role -> provider mapping


# CLI Session Management Models


class SessionStatus(str, Enum):
    """CLI session status enumeration."""

    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    IDLE = "idle"
    ERROR = "error"
    TERMINATED = "terminated"


class Message(BaseModel):
    """Session message model for history tracking."""

    type: str  # "command", "response", "error", "system"
    content: str
    timestamp: datetime
    direction: str  # "input" or "output"
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class Session(BaseModel):
    """CLI session model with comprehensive state management."""

    id: str
    provider: str  # "claude", "codex", "gemini", "cursor"
    process_id: int | None = None
    user_id: str = "default"
    created_at: datetime
    last_activity: datetime
    status: SessionStatus = SessionStatus.INITIALIZING
    history: list[Message] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Session configuration
    working_directory: str | None = None
    environment_vars: dict[str, str] = Field(default_factory=dict)
    cli_arguments: list[str] = Field(default_factory=list)

    # Error tracking
    error_count: int = 0
    last_error: str | None = None

    # Performance tracking
    command_count: int = 0
    total_execution_time_ms: int = 0

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
