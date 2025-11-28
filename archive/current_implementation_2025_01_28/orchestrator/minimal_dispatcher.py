"""
Minimal dispatcher for testing without Redis.
Just demonstrates the task submission and status tracking.
"""

from __future__ import annotations

import time
import uuid

from monitoring.metrics import METRICS
from orchestrator.models import TaskSpec, TaskStatus

# Simple in-memory task storage
TASKS: dict[str, TaskStatus] = {}


def enqueue_minimal_task(spec: TaskSpec) -> str:
    """Enqueue a task in minimal mode (just stores it, doesn't execute)"""

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Store task status
    task_status = TaskStatus(
        id=spec.id, role=spec.role, branch=f"auto/{spec.role}/{spec.id}", state="queued"
    )
    TASKS[spec.id] = task_status

    # Simulate some processing by updating status after a delay
    # In a real implementation, this would trigger actual agent execution
    import threading

    def simulate_processing():
        time.sleep(2)  # Simulate processing time
        if spec.id in TASKS:
            TASKS[spec.id].state = "running"
            print(f"📋 Simulating task execution: {spec.id} ({spec.role})")

        time.sleep(3)  # Simulate more processing
        if spec.id in TASKS:
            # 80% success rate
            import random

            success = random.random() > 0.2
            TASKS[spec.id].state = "passed" if success else "failed"
            if not success:
                TASKS[spec.id].last_error = "Simulated task failure for testing"

            # Update metrics
            if success:
                METRICS.tasks_succeeded.inc()
            else:
                METRICS.tasks_failed.inc()

            print(f"✅ Task {spec.id} {'completed' if success else 'failed'}")

    # Run simulation in background thread
    thread = threading.Thread(target=simulate_processing, daemon=True)
    thread.start()

    # Update metrics
    METRICS.tasks_enqueued.inc()

    print(f"📥 Task {spec.id} enqueued for {spec.role}")
    return job_id


def get_minimal_task(task_id: str) -> TaskStatus | None:
    """Get task status from minimal storage"""
    return TASKS.get(task_id)


def get_all_minimal_tasks() -> list[TaskStatus]:
    """Get all tasks from minimal storage"""
    return list(TASKS.values())
