"""Coverage for task queue recovery helpers."""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.task_queue import TaskQueue, TaskStatus


@pytest.fixture()
def temp_queue():
    """Provide a task queue backed by a temporary SQLite file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = handle.name
    try:
        queue = TaskQueue(db_path=db_path)
        yield queue
    finally:
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass


def test_update_assigned_agent_overwrites_placeholder(temp_queue):
    task_id = temp_queue.add_task("demo task", agent_type="claude")

    assert temp_queue.assign_task(task_id, "claude-agent")

    assert temp_queue.update_assigned_agent(task_id, "claude-1234")
    task = temp_queue.get_task(task_id)
    assert task.assigned_to == "claude-1234"


def test_force_requeue_returns_task_to_pending(temp_queue):
    task_id = temp_queue.add_task("long running", agent_type="claude")
    assert temp_queue.assign_task(task_id, "claude-agent")
    temp_queue.update_assigned_agent(task_id, "claude-ghost")
    temp_queue.update_status(task_id, TaskStatus.IN_PROGRESS)

    requeued = temp_queue.requeue_orphaned_tasks(force=True)
    assert requeued == 1

    task = temp_queue.get_task(task_id)
    assert task.status == TaskStatus.PENDING.value
    assert task.assigned_to is None


def test_requeue_only_stale_or_missing_agents(temp_queue):
    recent_id = temp_queue.add_task("active", agent_type="claude")
    stale_id = temp_queue.add_task("stale", agent_type="claude")

    temp_queue.assign_task(recent_id, "claude-agent")
    temp_queue.update_assigned_agent(recent_id, "claude-live")
    temp_queue.update_status(recent_id, TaskStatus.IN_PROGRESS)

    temp_queue.assign_task(stale_id, "claude-agent")
    temp_queue.update_assigned_agent(stale_id, "claude-old")
    temp_queue.update_status(stale_id, TaskStatus.IN_PROGRESS)

    # Age the stale task beyond the threshold
    old_timestamp = (datetime.now() - timedelta(minutes=30)).isoformat()
    temp_queue.db.execute_update(
        "UPDATE tasks SET assigned_at = ? WHERE id = ?",
        (old_timestamp, stale_id),
    )

    requeued = temp_queue.requeue_orphaned_tasks(
        active_agent_ids={"claude-live"}, max_age_minutes=5, force=False
    )

    assert requeued == 1
    assert temp_queue.get_task(recent_id).status == TaskStatus.IN_PROGRESS.value
    assert temp_queue.get_task(stale_id).status == TaskStatus.PENDING.value
