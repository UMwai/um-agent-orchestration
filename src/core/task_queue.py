"""
Simplified Task Queue using SQLite
No Redis, no external dependencies, just SQLite
"""

import sqlite3
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum


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
    """Simple SQLite-based task queue"""

    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        self.conn.execute("""
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
        """)
        self.conn.commit()

    def add_task(
        self,
        description: str,
        agent_type: str = "any",
        priority: Priority = Priority.NORMAL,
        context: Dict = None,
    ) -> str:
        """Add a new task to the queue"""
        import uuid

        task_id = str(uuid.uuid4())[:8]

        task = Task(
            id=task_id,
            description=description,
            agent_type=agent_type,
            priority=priority.value,
            context=context or {},
        )

        self.conn.execute(
            """
            INSERT INTO tasks (id, description, agent_type, status, priority, 
                              created_at, context)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task.id,
                task.description,
                task.agent_type,
                task.status,
                task.priority,
                task.created_at,
                json.dumps(task.context),
            ),
        )
        self.conn.commit()

        return task_id

    def get_next_task(self, agent_type: str = None) -> Optional[Task]:
        """Get next available task for an agent"""
        query = """
            SELECT * FROM tasks 
            WHERE status = ? 
            AND (agent_type = ? OR agent_type = 'any')
            ORDER BY priority ASC, created_at ASC
            LIMIT 1
        """

        if agent_type:
            cursor = self.conn.execute(query, (TaskStatus.PENDING.value, agent_type))
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM tasks 
                WHERE status = ?
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
            """,
                (TaskStatus.PENDING.value,),
            )

        row = cursor.fetchone()
        if row:
            return self._row_to_task(row)
        return None

    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to an agent"""
        self.conn.execute(
            """
            UPDATE tasks 
            SET status = ?, assigned_to = ?, assigned_at = ?
            WHERE id = ? AND status = ?
        """,
            (
                TaskStatus.ASSIGNED.value,
                agent_id,
                datetime.now().isoformat(),
                task_id,
                TaskStatus.PENDING.value,
            ),
        )
        self.conn.commit()
        return self.conn.total_changes > 0

    def update_status(
        self, task_id: str, status: TaskStatus, result: str = None, error: str = None
    ) -> bool:
        """Update task status"""
        updates = {"status": status.value}

        if status == TaskStatus.IN_PROGRESS:
            updates["assigned_at"] = datetime.now().isoformat()
        elif status == TaskStatus.COMPLETED:
            updates["completed_at"] = datetime.now().isoformat()
            if result:
                updates["result"] = result
        elif status == TaskStatus.FAILED:
            updates["completed_at"] = datetime.now().isoformat()
            if error:
                updates["error"] = error

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [task_id]

        self.conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        return self.conn.total_changes > 0

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a specific task by ID"""
        cursor = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return self._row_to_task(row) if row else None

    def get_all_tasks(self, status: TaskStatus = None) -> List[Task]:
        """Get all tasks, optionally filtered by status"""
        if status:
            cursor = self.conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                (status.value,),
            )
        else:
            cursor = self.conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")

        return [self._row_to_task(row) for row in cursor.fetchall()]

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
            context=json.loads(row["context"]) if row["context"] else {},
        )

    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        cursor = self.conn.execute("""
            SELECT status, COUNT(*) as count 
            FROM tasks 
            GROUP BY status
        """)

        stats = {status.value: 0 for status in TaskStatus}
        for row in cursor.fetchall():
            stats[row["status"]] = row["count"]

        return stats

    def cleanup_old_tasks(self, days: int = 7):
        """Remove completed/failed tasks older than specified days"""
        from datetime import datetime, timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        self.conn.execute(
            """
            DELETE FROM tasks 
            WHERE status IN (?, ?) 
            AND completed_at < ?
        """,
            (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, cutoff),
        )
        self.conn.commit()
        return self.conn.total_changes

    def close(self):
        """Close database connection"""
        self.conn.close()


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
