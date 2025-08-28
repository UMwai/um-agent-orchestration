from __future__ import annotations

from monitoring.metrics import METRICS
from orchestrator.models import TaskSpec
from orchestrator.persistence import get_persistence_manager
from orchestrator.persistence_models import TaskState
from orchestrator.queue import jobs_q


def update_task_status(task_id: str, state: str, error: str = None):
    """Update task status with dual-write to Redis and SQLite for persistence"""
    # Map string states to TaskState enum
    state_mapping = {
        "queued": TaskState.QUEUED,
        "starting": TaskState.STARTING,
        "running": TaskState.RUNNING,
        "passed": TaskState.PASSED,
        "failed": TaskState.FAILED,
        "error": TaskState.ERROR,
        "cancelled": TaskState.CANCELLED,
    }

    task_state = state_mapping.get(state, TaskState.ERROR)

    # Update in persistent storage
    persistence_manager = get_persistence_manager()
    persistence_manager.update_task_state(task_id, task_state, error_message=error)

    # Also update Redis for backward compatibility and real-time access
    from orchestrator.models import TaskStatus
    from orchestrator.queue import _redis

    key = f"task_status:{task_id}"
    existing = _redis.get(key)
    if existing:
        task_status = TaskStatus.parse_raw(existing)
        task_status.state = state
        if error:
            task_status.last_error = error
    else:
        # Create new task status (shouldn't happen in normal flow)
        task_status = TaskStatus(
            id=task_id,
            role="unknown",
            branch=f"auto/unknown/{task_id}",
            state=state,
            last_error=error,
        )

    # Save updated status with 24 hour expiry
    _redis.setex(key, 86400, task_status.json())


def update_task_status_with_metadata(
    task_id: str, state: str, error: str = None, provider: str = None, model: str = None
):
    """Update task status with provider and model metadata using dual-write persistence"""
    # Map string states to TaskState enum
    state_mapping = {
        "queued": TaskState.QUEUED,
        "starting": TaskState.STARTING,
        "running": TaskState.RUNNING,
        "passed": TaskState.PASSED,
        "failed": TaskState.FAILED,
        "error": TaskState.ERROR,
        "cancelled": TaskState.CANCELLED,
    }

    task_state = state_mapping.get(state, TaskState.ERROR)

    # Update in persistent storage with metadata
    persistence_manager = get_persistence_manager()
    persistence_manager.update_task_state(
        task_id, task_state, error_message=error, provider=provider, model=model
    )

    # Also update Redis for backward compatibility and real-time access
    from orchestrator.models import TaskStatus
    from orchestrator.queue import _redis

    key = f"task_status:{task_id}"
    existing = _redis.get(key)
    if existing:
        task_status = TaskStatus.parse_raw(existing)
        task_status.state = state
        if error:
            task_status.last_error = error
        if provider:
            task_status.provider = provider
        if model:
            task_status.model = model
    else:
        # Create new task status (shouldn't happen in normal flow)
        task_status = TaskStatus(
            id=task_id,
            role="unknown",
            branch=f"auto/unknown/{task_id}",
            state=state,
            last_error=error,
            provider=provider,
            model=model,
        )

    # Save updated status with 24 hour expiry
    _redis.setex(key, 86400, task_status.json())


def run_task(spec: TaskSpec) -> str:
    from agents import registry

    # Update task to running state
    update_task_status(spec.id, "running")
    METRICS.tasks_started.inc()

    try:
        agent = registry.get_agent_for_task(spec)
        execution_metadata = agent.plan_and_execute()

        # Mark as completed with provider/model info
        update_task_status_with_metadata(
            spec.id,
            "passed",
            provider=execution_metadata.get("provider"),
            model=execution_metadata.get("model"),
        )
        METRICS.tasks_succeeded.inc()
        return f"Task {spec.id} completed on {agent.feature_branch} using {execution_metadata.get('provider', 'unknown')}/{execution_metadata.get('model', 'unknown')}"

    except Exception as e:
        # Mark as failed with error details
        update_task_status(spec.id, "failed", str(e))
        METRICS.tasks_failed.inc()
        raise e


def enqueue_task(spec: TaskSpec):
    """Enqueue task with persistent storage creation"""
    # Create persistent task record first
    persistence_manager = get_persistence_manager()
    task_record = persistence_manager.create_task(spec)

    # Enqueue the job in Redis
    job = jobs_q.enqueue(run_task, spec)
    METRICS.tasks_enqueued.inc()

    print(f"📝 Task {spec.id} created in persistent storage and queued")
    return job.id
