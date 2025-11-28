"""
Simplified Task Queue using SQLite
No Redis, no external dependencies, just SQLite
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Set
from enum import Enum
import threading

import os
from .database import DatabaseManager
from .exceptions import validate_not_empty, validate_positive_int
from .config import get_config


class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Priority(Enum):
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Task:
    id: Optional[str] = None
    description: str = ""
    agent_type: str = "any"  # 'claude', 'codex', or 'any'
    status: str = TaskStatus.PENDING.value
    priority: int = Priority.NORMAL.value
    created_at: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    context: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.context is None:
            self.context = {}


class TaskQueue:
    """Thread-safe SQLite-based task queue"""

    def __init__(self, db_path: str = None):
        self.db = DatabaseManager(db_path)
        self._task_lock = threading.RLock()  # Reentrant lock for nested calls
        self._assignment_lock = threading.Lock()  # Separate lock for task assignment
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        schema = """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                agent_type TEXT DEFAULT 'any',
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 2,
                created_at TEXT NOT NULL,
                assigned_to TEXT,
                assigned_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT,
                context TEXT
            )
        """
        self.db.init_schema(schema)

    def add_task(
        self,
        description: str,
        agent_type: str = "any",
        priority: Priority = Priority.NORMAL,
        context: Dict = None,
    ) -> str:
        """Add a new task to the queue"""
        import uuid

        # Validate inputs
        description = validate_not_empty(description, "description")

        task_id = str(uuid.uuid4())[:8]
        task = Task(
            id=task_id,
            description=description,
            agent_type=agent_type,
            priority=priority.value,
            context=context or {},
        )

        query = """
            INSERT INTO tasks (id, description, agent_type, status, priority,
                              created_at, context)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            task.id,
            task.description,
            task.agent_type,
            task.status,
            task.priority,
            task.created_at,
            self.db.serialize_json(task.context),
        )

        self.db.execute_update(query, params)
        return task_id

    def get_next_task(self, agent_type: str = None) -> Optional[Task]:
        """Get next available task for an agent (thread-safe)"""
        with self._task_lock:
            if agent_type:
                query = """
                    SELECT * FROM tasks
                    WHERE status = ? AND (agent_type = ? OR agent_type = 'any')
                    ORDER BY priority ASC, created_at ASC LIMIT 1
                """
                params = (TaskStatus.PENDING.value, agent_type)
            else:
                query = """
                    SELECT * FROM tasks WHERE status = ?
                    ORDER BY priority ASC, created_at ASC LIMIT 1
                """
                params = (TaskStatus.PENDING.value,)

            rows = self.db.execute_query(query, params)
            return self._row_to_task(rows[0]) if rows else None

    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Atomically assign a task to an agent (thread-safe)"""
        with self._assignment_lock:
            # Double-check task is still pending to prevent race conditions
            check_query = "SELECT status FROM tasks WHERE id = ?"
            rows = self.db.execute_query(check_query, (task_id,))

            if not rows or rows[0]["status"] != TaskStatus.PENDING.value:
                return False  # Task no longer available

            query = """
                UPDATE tasks SET status = ?, assigned_to = ?, assigned_at = ?
                WHERE id = ? AND status = ?
            """
            params = (
                TaskStatus.ASSIGNED.value,
                agent_id,
                datetime.now().isoformat(),
                task_id,
                TaskStatus.PENDING.value,
            )
            return self.db.execute_update(query, params) > 0

    def update_status(
        self, task_id: str, status: TaskStatus, result: str = None, error: str = None
    ) -> bool:
        """Update task status (thread-safe)"""
        with self._task_lock:
            updates = {"status": status.value}
            timestamp = datetime.now().isoformat()

            if status == TaskStatus.IN_PROGRESS:
                updates["assigned_at"] = timestamp
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                updates["completed_at"] = timestamp
                if result:
                    updates["result"] = result
                if error:
                    updates["error"] = error

            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            query = f"UPDATE tasks SET {set_clause} WHERE id = ?"
            params = list(updates.values()) + [task_id]

            return self.db.execute_update(query, params) > 0

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a specific task by ID (thread-safe)"""
        with self._task_lock:
            rows = self.db.execute_query("SELECT * FROM tasks WHERE id = ?", (task_id,))
            return self._row_to_task(rows[0]) if rows else None

    def get_all_tasks(self, status: TaskStatus = None) -> List[Task]:
        """Get all tasks, optionally filtered by status (thread-safe)"""
        with self._task_lock:
            if status:
                query = "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC"
                params = (status.value,)
            else:
                query = "SELECT * FROM tasks ORDER BY created_at DESC"
                params = ()

            rows = self.db.execute_query(query, params)
            return [self._row_to_task(row) for row in rows]

    def update_assigned_agent(self, task_id: str, agent_id: str) -> bool:
        """Update the agent assignment after spawn succeeds (thread-safe)."""
        with self._task_lock:
            query = "UPDATE tasks SET assigned_to = ? WHERE id = ?"
            return self.db.execute_update(query, (agent_id, task_id)) > 0

    def requeue_orphaned_tasks(
        self,
        active_agent_ids: Optional[Set[str]] = None,
        max_age_minutes: int = 5,
        force: bool = False,
    ) -> int:
        """Return orphaned tasks to the pending state.

        A task is considered orphaned when it's marked as assigned/in-progress but
        no corresponding agent is active. When `force` is True (e.g., on startup
        after a crash), we requeue any such tasks immediately; otherwise we only
        reclaim tasks whose assignments are older than `max_age_minutes` or whose
        assigned agent isn't running.
        """

        active_agent_ids = {aid for aid in (active_agent_ids or set()) if aid}
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)

        with self._task_lock:
            query = """
                SELECT id, assigned_to, assigned_at FROM tasks
                WHERE status IN (?, ?)
            """
            rows = self.db.execute_query(
                query,
                (TaskStatus.ASSIGNED.value, TaskStatus.IN_PROGRESS.value),
            )

            orphan_ids = []
            for row in rows:
                task_id = row["id"]
                assigned_to = row["assigned_to"] or ""
                assigned_at = row["assigned_at"]

                # If the agent is still active, skip unless we're forcing a reset
                if assigned_to and assigned_to in active_agent_ids and not force:
                    continue

                if force or not assigned_at:
                    orphan_ids.append(task_id)
                    continue

                try:
                    assigned_time = datetime.fromisoformat(assigned_at)
                except ValueError:
                    orphan_ids.append(task_id)
                    continue

                if assigned_time <= cutoff:
                    orphan_ids.append(task_id)

            if not orphan_ids:
                return 0

            query = """
                UPDATE tasks
                SET status = ?, assigned_to = NULL, assigned_at = NULL
                WHERE id = ?
            """
            requeued = 0
            for task_id in orphan_ids:
                requeued += self.db.execute_update(
                    query, (TaskStatus.PENDING.value, task_id)
                )

            return requeued

    def _row_to_task(self, row) -> Task:
        """Convert database row to Task object"""
        return Task(
            id=row["id"],
            description=row["description"],
            agent_type=row["agent_type"],
            status=row["status"],
            priority=row["priority"],
            created_at=row["created_at"],
            assigned_to=row["assigned_to"],
            assigned_at=row["assigned_at"],
            completed_at=row["completed_at"],
            result=row["result"],
            error=row["error"],
            context=self.db.deserialize_json(row["context"]),
        )

    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics (thread-safe)"""
        with self._task_lock:
            query = "SELECT status, COUNT(*) as count FROM tasks GROUP BY status"
            rows = self.db.execute_query(query)

            stats = {status.value: 0 for status in TaskStatus}
            for row in rows:
                stats[row["status"]] = row["count"]

            return stats

    def cleanup_old_tasks(self, days: int = None, max_tasks: int = None):
        """Remove completed/failed tasks older than specified days or limit total tasks (thread-safe)"""
        from datetime import datetime, timedelta

        with self._task_lock:
            days = days or get_config().cleanup_days
            validate_positive_int(days, "cleanup days")
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            # First, clean up by age
            query = """
                DELETE FROM tasks WHERE status IN (?, ?) AND completed_at < ?
            """
            params = (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, cutoff)
            age_cleaned = self.db.execute_update(query, params)

            # Then, limit total tasks if specified
            limit_cleaned = 0
            if max_tasks and max_tasks > 0:
                # Count current tasks
                count_query = "SELECT COUNT(*) as count FROM tasks"
                count_result = self.db.execute_query(count_query)
                total_tasks = count_result[0]["count"] if count_result else 0

                if total_tasks > max_tasks:
                    # Delete oldest completed/failed tasks to get under limit
                    excess = total_tasks - max_tasks
                    limit_query = """
                        DELETE FROM tasks WHERE id IN (
                            SELECT id FROM tasks
                            WHERE status IN (?, ?)
                            ORDER BY COALESCE(completed_at, created_at) ASC
                            LIMIT ?
                        )
                    """
                    limit_params = (
                        TaskStatus.COMPLETED.value,
                        TaskStatus.FAILED.value,
                        excess,
                    )
                    limit_cleaned = self.db.execute_update(limit_query, limit_params)

            return age_cleaned + limit_cleaned

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics (thread-safe)"""
        with self._task_lock:
            stats = self.get_stats()

            # Get database size
            try:
                db_size = (
                    os.path.getsize(self.db.db_path)
                    if os.path.exists(self.db.db_path)
                    else 0
                )
            except OSError:
                db_size = 0

            # Get connection pool stats
            pool_stats = self.db.get_pool_stats()

            return {
                "task_counts": stats,
                "db_size_bytes": db_size,
                "db_size_mb": db_size / (1024 * 1024),
                "connection_pool": pool_stats,
            }

    def get_and_assign_next_task(
        self, agent_type: str, agent_id: str
    ) -> Optional[Task]:
        """Atomically get and assign the next available task to an agent"""
        # Use a single critical section to avoid lock ordering issues
        with self._assignment_lock:
            # Find and assign task in one database operation to avoid race conditions
            if agent_type:
                query = """
                    UPDATE tasks SET status = ?, assigned_to = ?, assigned_at = ?
                    WHERE id = (
                        SELECT id FROM tasks
                        WHERE status = ? AND (agent_type = ? OR agent_type = 'any')
                        ORDER BY priority ASC, created_at ASC LIMIT 1
                    ) AND status = ?
                """
                params = (
                    TaskStatus.ASSIGNED.value,
                    agent_id,
                    datetime.now().isoformat(),
                    TaskStatus.PENDING.value,
                    agent_type,
                    TaskStatus.PENDING.value,
                )
            else:
                query = """
                    UPDATE tasks SET status = ?, assigned_to = ?, assigned_at = ?
                    WHERE id = (
                        SELECT id FROM tasks WHERE status = ?
                        ORDER BY priority ASC, created_at ASC LIMIT 1
                    ) AND status = ?
                """
                params = (
                    TaskStatus.ASSIGNED.value,
                    agent_id,
                    datetime.now().isoformat(),
                    TaskStatus.PENDING.value,
                    TaskStatus.PENDING.value,
                )

            rows_affected = self.db.execute_update(query, params)

            if rows_affected > 0:
                # Find the task that was just assigned
                assigned_query = """
                    SELECT * FROM tasks
                    WHERE assigned_to = ? AND status = ?
                    ORDER BY assigned_at DESC LIMIT 1
                """
                rows = self.db.execute_query(
                    assigned_query, (agent_id, TaskStatus.ASSIGNED.value)
                )
                if rows:
                    return self._row_to_task(rows[0])

            return None

    def close(self):
        """Close database connection - handled by context manager"""
        pass  # DatabaseManager handles connection cleanup


if __name__ == "__main__":
    # Simple test
    queue = TaskQueue(":memory:")

    # Add some tasks
    task1 = queue.add_task("Fix authentication bug", "claude", Priority.HIGH)
    task2 = queue.add_task("Update UI components", "codex", Priority.NORMAL)
    task3 = queue.add_task("Write tests", "any", Priority.LOW)

    print(f"Added tasks: {task1}, {task2}, {task3}")

    # Get next task
    next_task = queue.get_next_task("claude")
    if next_task:
        print(f"Next task for claude: {next_task.description}")
        queue.assign_task(next_task.id, "claude-agent-1")
        queue.update_status(next_task.id, TaskStatus.IN_PROGRESS)

    # Check stats
    print(f"Queue stats: {queue.get_stats()}")

    queue.close()
