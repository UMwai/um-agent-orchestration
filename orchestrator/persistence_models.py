"""
Enhanced data models for task persistence and CLI session management.
These models extend the existing models with comprehensive persistence support.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """Enhanced task states for comprehensive lifecycle tracking."""

    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETING = "completing"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class OutputType(str, Enum):
    """Types of task outputs for storage and retrieval."""

    STDOUT = "stdout"
    STDERR = "stderr"
    LOG = "log"
    ARTIFACT = "artifact"
    COMMIT = "commit"
    DIAGNOSTIC = "diagnostic"


class CLISessionState(str, Enum):
    """CLI session states for process management."""

    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    TERMINATED = "terminated"


class TaskRecord(BaseModel):
    """Complete task record with all persistence fields."""

    id: str
    title: str
    description: str
    role: str
    state: TaskState = TaskState.QUEUED
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    started_at: datetime | None = None

    # Provider and model information
    provider: str | None = None
    model: str | None = None

    # Git and worktree information
    branch: str | None = None
    worktree_path: str | None = None
    base_branch: str | None = None
    commit_hash: str | None = None

    # Configuration
    target_dir: str = "."
    full_access: bool = False
    provider_override: str | None = None
    repository_url: str | None = None

    # Error tracking
    last_error: str | None = None
    error_count: int = 0

    # Metadata
    acceptance_criteria: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class TaskHistoryRecord(BaseModel):
    """Task state transition history."""

    id: int | None = None
    task_id: str
    state_from: TaskState | None = None
    state_to: TaskState
    timestamp: datetime
    provider: str | None = None
    model: str | None = None
    error_message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    user_id: str = "default"


class TaskOutput(BaseModel):
    """Task output record."""

    id: int | None = None
    task_id: str
    output_type: OutputType
    content: str
    timestamp: datetime

    # File information for artifacts
    file_path: str | None = None
    file_size: int | None = None
    mime_type: str | None = None

    # Commit information
    commit_hash: str | None = None
    branch: str | None = None


class TaskMetric(BaseModel):
    """Task performance and resource metric."""

    id: int | None = None
    task_id: str
    metric_name: str
    metric_value: float
    timestamp: datetime
    unit: str | None = None


class CLISessionRecord(BaseModel):
    """CLI session record for persistence."""

    session_id: str
    cli_tool: str  # 'claude', 'codex', 'gemini', 'cursor'
    mode: str  # 'cli', 'interactive', 'api'
    state: CLISessionState = CLISessionState.INITIALIZING
    pid: int | None = None
    created_at: datetime
    last_activity: datetime
    terminated_at: datetime | None = None

    # Session configuration
    current_directory: str
    authentication_required: bool = False
    auth_prompt: str | None = None

    # Associated task
    task_id: str | None = None


class CLISessionCommand(BaseModel):
    """CLI session command record."""

    id: int | None = None
    session_id: str
    command: str
    output: str | None = None
    timestamp: datetime
    execution_time_ms: int | None = None
    exit_code: int | None = None


class UserPreferences(BaseModel):
    """User preferences for models and providers."""

    user_id: str = "default"
    preferred_provider: str | None = None
    preferred_model: str | None = None
    full_access_preferred: bool = False
    role_preferences: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class TaskSummary(BaseModel):
    """Summary view of task with aggregated information."""

    id: str
    title: str
    role: str
    state: TaskState
    provider: str | None = None
    model: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    last_error: str | None = None
    state_changes: int = 0
    last_state_change: datetime | None = None


class TaskSearchFilter(BaseModel):
    """Filter criteria for task searches."""

    states: list[TaskState] | None = None
    roles: list[str] | None = None
    providers: list[str] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search_text: str | None = None
    limit: int | None = 100
    offset: int | None = 0


class PersistenceStats(BaseModel):
    """Statistics about stored data."""

    total_tasks: int
    tasks_by_state: dict[str, int]
    tasks_by_role: dict[str, int]
    active_cli_sessions: int
    database_size_mb: float
    oldest_task_date: datetime | None = None
    newest_task_date: datetime | None = None
