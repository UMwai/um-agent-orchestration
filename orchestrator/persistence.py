"""
Task Persistence Manager for comprehensive task lifecycle and history storage.
Provides dual-write to Redis (real-time) and SQLite (persistence) with recovery capabilities.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from orchestrator.models import TaskSpec, TaskStatus
from orchestrator.persistence_models import (
    CLISessionRecord,
    CLISessionState,
    OutputType,
    PersistenceStats,
    TaskHistoryRecord,
    TaskOutput,
    TaskRecord,
    TaskSearchFilter,
    TaskState,
)


class TaskPersistenceManager:
    """
    Comprehensive task persistence manager with SQLite storage and Redis integration.
    Provides full lifecycle tracking, history, and recovery capabilities.
    """

    def __init__(self, db_path: str = "database/tasks.db", redis_client=None):
        self.db_path = db_path
        self.redis_client = redis_client
        self._local = threading.local()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None,  # Autocommit mode
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent access
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
            self._local.connection.execute("PRAGMA cache_size=10000")

        return self._local.connection

    def _init_database(self):
        """Initialize database with schema."""
        # Ensure database directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Load and execute schema
        schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
        if schema_path.exists():
            with open(schema_path) as f:
                schema_sql = f.read()

            conn = self._get_connection()
            conn.executescript(schema_sql)
            print(f"📄 Database initialized at {self.db_path}")
        else:
            print(f"⚠️  Schema file not found at {schema_path}")

    # Task Management Methods

    def create_task(self, spec: TaskSpec) -> TaskRecord:
        """Create a new task record from TaskSpec."""
        now = datetime.utcnow()

        task_record = TaskRecord(
            id=spec.id,
            title=spec.title,
            description=spec.description,
            role=spec.role,
            state=TaskState.QUEUED,
            created_at=now,
            updated_at=now,
            target_dir=spec.target_dir,
            full_access=spec.full_access,
            provider_override=spec.provider_override,
            model=spec.model,
            repository_url=spec.repository_url,
            base_branch=spec.base_branch,
            acceptance_criteria=spec.acceptance,
        )

        # Insert into database
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO tasks (
                id, title, description, role, state, created_at, updated_at,
                target_dir, full_access, provider_override, model,
                repository_url, base_branch, acceptance_criteria
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_record.id,
                task_record.title,
                task_record.description,
                task_record.role,
                task_record.state.value,
                task_record.created_at,
                task_record.updated_at,
                task_record.target_dir,
                task_record.full_access,
                task_record.provider_override,
                task_record.model,
                task_record.repository_url,
                task_record.base_branch,
                json.dumps(task_record.acceptance_criteria),
            ),
        )

        # Create initial history entry
        self.add_task_history(task_record.id, None, TaskState.QUEUED)

        # Also store in Redis for real-time access
        if self.redis_client:
            task_status = TaskStatus(
                id=task_record.id,
                role=task_record.role,
                branch=task_record.branch or f"auto/{task_record.role}/{task_record.id}",
                state="queued",
            )
            self.redis_client.setex(
                f"task_status:{task_record.id}",
                86400,  # 24 hour expiry
                task_status.json(),
            )

        return task_record

    def update_task_state(
        self,
        task_id: str,
        new_state: TaskState,
        error_message: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> bool:
        """Update task state with full history tracking."""
        conn = self._get_connection()

        # Get current state
        current_task = conn.execute(
            "SELECT state, provider, model FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()

        if not current_task:
            return False

        old_state = TaskState(current_task["state"])
        now = datetime.utcnow()

        # Update task record
        update_fields = ["state = ?", "updated_at = ?"]
        update_values = [new_state.value, now]

        if error_message:
            update_fields.append("last_error = ?")
            update_fields.append("error_count = error_count + 1")
            update_values.append(error_message)

        if provider:
            update_fields.append("provider = ?")
            update_values.append(provider)

        if model:
            update_fields.append("model = ?")
            update_values.append(model)

        # Set completion timestamp for terminal states
        if new_state in [TaskState.PASSED, TaskState.FAILED, TaskState.ERROR, TaskState.CANCELLED]:
            update_fields.append("completed_at = ?")
            update_values.append(now)
        elif new_state == TaskState.RUNNING and not current_task:
            update_fields.append("started_at = ?")
            update_values.append(now)

        update_values.append(task_id)  # for WHERE clause

        conn.execute(
            f"""
            UPDATE tasks SET {', '.join(update_fields)}
            WHERE id = ?
        """,
            update_values,
        )

        # Add history entry
        self.add_task_history(task_id, old_state, new_state, provider, model, error_message)

        # Update Redis
        if self.redis_client:
            try:
                existing = self.redis_client.get(f"task_status:{task_id}")
                if existing:
                    task_status = TaskStatus.parse_raw(existing)
                    task_status.state = new_state.value.replace("passed", "passed").replace(
                        "failed", "failed"
                    )
                    if error_message:
                        task_status.last_error = error_message
                    if provider:
                        task_status.provider = provider
                    if model:
                        task_status.model = model

                    self.redis_client.setex(f"task_status:{task_id}", 86400, task_status.json())
            except Exception as e:
                print(f"⚠️  Failed to update Redis: {e}")

        return True

    def get_task(self, task_id: str) -> TaskRecord | None:
        """Get task by ID."""
        conn = self._get_connection()
        row = conn.execute(
            """
            SELECT * FROM tasks WHERE id = ?
        """,
            (task_id,),
        ).fetchone()

        if not row:
            return None

        return self._row_to_task_record(row)

    def get_all_tasks(self, filter_criteria: TaskSearchFilter | None = None) -> list[TaskRecord]:
        """Get all tasks with optional filtering."""
        conn = self._get_connection()

        query = "SELECT * FROM tasks"
        params = []
        conditions = []

        if filter_criteria:
            if filter_criteria.states:
                placeholders = ",".join(["?" for _ in filter_criteria.states])
                conditions.append(f"state IN ({placeholders})")
                params.extend([state.value for state in filter_criteria.states])

            if filter_criteria.roles:
                placeholders = ",".join(["?" for _ in filter_criteria.roles])
                conditions.append(f"role IN ({placeholders})")
                params.extend(filter_criteria.roles)

            if filter_criteria.providers:
                placeholders = ",".join(["?" for _ in filter_criteria.providers])
                conditions.append(f"provider IN ({placeholders})")
                params.extend(filter_criteria.providers)

            if filter_criteria.date_from:
                conditions.append("created_at >= ?")
                params.append(filter_criteria.date_from)

            if filter_criteria.date_to:
                conditions.append("created_at <= ?")
                params.append(filter_criteria.date_to)

            if filter_criteria.search_text:
                conditions.append("(title LIKE ? OR description LIKE ?)")
                search_term = f"%{filter_criteria.search_text}%"
                params.extend([search_term, search_term])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC"

        if filter_criteria and filter_criteria.limit:
            query += f" LIMIT {filter_criteria.limit}"
            if filter_criteria.offset:
                query += f" OFFSET {filter_criteria.offset}"

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_task_record(row) for row in rows]

    def add_task_history(
        self,
        task_id: str,
        state_from: TaskState | None,
        state_to: TaskState,
        provider: str | None = None,
        model: str | None = None,
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Add task history entry."""
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO task_history (
                task_id, state_from, state_to, provider, model, 
                error_message, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_id,
                state_from.value if state_from else None,
                state_to.value,
                provider,
                model,
                error_message,
                json.dumps(details) if details else None,
            ),
        )

    def get_task_history(self, task_id: str) -> list[TaskHistoryRecord]:
        """Get complete history for a task."""
        conn = self._get_connection()
        rows = conn.execute(
            """
            SELECT * FROM task_history 
            WHERE task_id = ? 
            ORDER BY timestamp ASC
        """,
            (task_id,),
        ).fetchall()

        return [self._row_to_task_history(row) for row in rows]

    def add_task_output(
        self,
        task_id: str,
        output_type: OutputType,
        content: str,
        file_path: str | None = None,
        commit_hash: str | None = None,
        branch: str | None = None,
    ):
        """Add task output/artifact."""
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO task_outputs (
                task_id, output_type, content, file_path, commit_hash, branch
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (task_id, output_type.value, content, file_path, commit_hash, branch),
        )

    def get_task_outputs(
        self, task_id: str, output_types: list[OutputType] | None = None
    ) -> list[TaskOutput]:
        """Get task outputs by type."""
        conn = self._get_connection()

        query = "SELECT * FROM task_outputs WHERE task_id = ?"
        params = [task_id]

        if output_types:
            placeholders = ",".join(["?" for _ in output_types])
            query += f" AND output_type IN ({placeholders})"
            params.extend([ot.value for ot in output_types])

        query += " ORDER BY timestamp ASC"

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_task_output(row) for row in rows]

    def get_persistence_stats(self) -> PersistenceStats:
        """Get database statistics."""
        conn = self._get_connection()

        # Total tasks
        total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

        # Tasks by state
        state_rows = conn.execute("""
            SELECT state, COUNT(*) as count 
            FROM tasks 
            GROUP BY state
        """).fetchall()
        tasks_by_state = {row["state"]: row["count"] for row in state_rows}

        # Tasks by role
        role_rows = conn.execute("""
            SELECT role, COUNT(*) as count 
            FROM tasks 
            GROUP BY role
        """).fetchall()
        tasks_by_role = {row["role"]: row["count"] for row in role_rows}

        # Active CLI sessions
        active_sessions = conn.execute("""
            SELECT COUNT(*) FROM cli_sessions 
            WHERE state NOT IN ('terminated', 'error')
        """).fetchone()[0]

        # Database size
        db_size = (
            os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0
        )

        # Date range
        date_row = conn.execute("""
            SELECT MIN(created_at) as oldest, MAX(created_at) as newest 
            FROM tasks
        """).fetchone()

        return PersistenceStats(
            total_tasks=total_tasks,
            tasks_by_state=tasks_by_state,
            tasks_by_role=tasks_by_role,
            active_cli_sessions=active_sessions,
            database_size_mb=db_size,
            oldest_task_date=datetime.fromisoformat(date_row["oldest"])
            if date_row["oldest"]
            else None,
            newest_task_date=datetime.fromisoformat(date_row["newest"])
            if date_row["newest"]
            else None,
        )

    # CLI Session Management

    def create_cli_session(self, session_record: CLISessionRecord) -> bool:
        """Create new CLI session record."""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO cli_sessions (
                    session_id, cli_tool, mode, state, pid, created_at, 
                    last_activity, current_directory, authentication_required,
                    auth_prompt, task_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_record.session_id,
                    session_record.cli_tool,
                    session_record.mode,
                    session_record.state.value,
                    session_record.pid,
                    session_record.created_at,
                    session_record.last_activity,
                    session_record.current_directory,
                    session_record.authentication_required,
                    session_record.auth_prompt,
                    session_record.task_id,
                ),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def update_cli_session(self, session_id: str, **kwargs) -> bool:
        """Update CLI session record."""
        if not kwargs:
            return True

        conn = self._get_connection()

        # Build dynamic update query
        update_fields = []
        update_values = []

        for field, value in kwargs.items():
            if field == "state" and isinstance(value, CLISessionState):
                update_fields.append("state = ?")
                update_values.append(value.value)
            else:
                update_fields.append(f"{field} = ?")
                update_values.append(value)

        update_values.append(session_id)

        conn.execute(
            f"""
            UPDATE cli_sessions SET {', '.join(update_fields)}
            WHERE session_id = ?
        """,
            update_values,
        )

        return True

    # Helper methods

    def _row_to_task_record(self, row) -> TaskRecord:
        """Convert database row to TaskRecord."""
        return TaskRecord(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            role=row["role"],
            state=TaskState(row["state"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None,
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            provider=row["provider"],
            model=row["model"],
            branch=row["branch"],
            worktree_path=row["worktree_path"],
            base_branch=row["base_branch"],
            commit_hash=row["commit_hash"],
            target_dir=row["target_dir"],
            full_access=bool(row["full_access"]),
            provider_override=row["provider_override"],
            repository_url=row["repository_url"],
            last_error=row["last_error"],
            error_count=row["error_count"],
            acceptance_criteria=json.loads(row["acceptance_criteria"])
            if row["acceptance_criteria"]
            else {},
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def _row_to_task_history(self, row) -> TaskHistoryRecord:
        """Convert database row to TaskHistoryRecord."""
        return TaskHistoryRecord(
            id=row["id"],
            task_id=row["task_id"],
            state_from=TaskState(row["state_from"]) if row["state_from"] else None,
            state_to=TaskState(row["state_to"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            provider=row["provider"],
            model=row["model"],
            error_message=row["error_message"],
            details=json.loads(row["details"]) if row["details"] else {},
            user_id=row["user_id"],
        )

    def _row_to_task_output(self, row) -> TaskOutput:
        """Convert database row to TaskOutput."""
        return TaskOutput(
            id=row["id"],
            task_id=row["task_id"],
            output_type=OutputType(row["output_type"]),
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            file_path=row["file_path"],
            file_size=row["file_size"],
            mime_type=row["mime_type"],
            commit_hash=row["commit_hash"],
            branch=row["branch"],
        )


# Global persistence manager instance
_persistence_manager: TaskPersistenceManager | None = None


def get_persistence_manager() -> TaskPersistenceManager:
    """Get global persistence manager instance."""
    global _persistence_manager
    if _persistence_manager is None:
        # Try to get Redis client for dual-write
        redis_client = None
        try:
            from orchestrator.queue import _redis

            redis_client = _redis
        except ImportError:
            pass

        _persistence_manager = TaskPersistenceManager(redis_client=redis_client)
    return _persistence_manager
