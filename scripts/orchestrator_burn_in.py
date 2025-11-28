#!/usr/bin/env python3
"""Burn-in harness for the simplified agent orchestrator."""

import argparse
import os
import random
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli.orchestrate import Orchestrator
from src.core.task_queue import TaskStatus

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

TASK_CATALOG = [
    {
        "description": "Implement a FastAPI endpoint that echoes JSON payloads",
        "agent": "claude",
        "priority": "normal",
    },
    {
        "description": "Add Jest tests for a React component that renders a todo list",
        "agent": "codex",
        "priority": "normal",
    },
    {
        "description": "Document the SQLite queue schema and cleanup strategy",
        "agent": "claude",
        "priority": "low",
    },
    {
        "description": "Create a Makefile that wraps pytest and lint commands",
        "agent": "codex",
        "priority": "low",
    },
    {
        "description": "Refactor task requeue logic to support crash recovery",
        "agent": "claude",
        "priority": "high",
    },
    {
        "description": "Write integration test cases for orchestrator run command",
        "agent": "codex",
        "priority": "normal",
    },
]


def submit_batch(orchestrator: Orchestrator, batch_size: int, run_id: str) -> list[str]:
    """Submit a batch of tasks sampled from the catalog."""
    submitted = []
    for _ in range(batch_size):
        task_spec = random.choice(TASK_CATALOG)
        context = {
            "burn_in_run": run_id,
            "sample_index": random.randint(0, 10_000),
            "submitted_at": datetime.utcnow().isoformat(),
        }
        task_id = orchestrator.submit_task(
            description=task_spec["description"],
            agent_type=task_spec["agent"],
            priority=task_spec["priority"],
            context=context,
        )
        submitted.append(task_id)
    return submitted


def update_counters(
    orchestrator: Orchestrator, tracked_tasks: dict[str, str]
) -> tuple[int, int]:
    """Update counters for tasks that reached a terminal state."""
    completed = failed = 0
    for task_id in list(tracked_tasks.keys()):
        task = orchestrator.queue.get_task(task_id)
        if not task:
            tracked_tasks.pop(task_id, None)
            continue

        if task.status == TaskStatus.COMPLETED.value:
            completed += 1
            tracked_tasks.pop(task_id, None)
        elif task.status == TaskStatus.FAILED.value:
            failed += 1
            tracked_tasks.pop(task_id, None)
    return completed, failed


def collect_resource_metrics(
    orchestrator: Orchestrator, process_handle
) -> dict[str, float]:
    """Gather system and orchestrator resource metrics."""

    metrics: dict[str, float] = {}

    if psutil:
        metrics["cpu_percent"] = psutil.cpu_percent(interval=None)
        metrics["memory_percent"] = psutil.virtual_memory().percent
        if process_handle:
            metrics["proc_cpu_percent"] = process_handle.cpu_percent(interval=None)
            metrics["proc_memory_mb"] = process_handle.memory_info().rss / (1024 * 1024)
    else:
        try:
            load1, _, _ = os.getloadavg()
            metrics["load_avg_1m"] = load1
        except OSError:  # pragma: no cover - platform specific
            metrics["load_avg_1m"] = -1.0

    disk_usage = shutil.disk_usage(orchestrator.spawner.base_dir)
    metrics["disk_used_mb"] = disk_usage.used / (1024 * 1024)
    metrics["disk_free_mb"] = disk_usage.free / (1024 * 1024)

    agent_stats = orchestrator.spawner.get_resource_stats()
    metrics["agents_active"] = agent_stats["active_agents"]
    metrics["agents_total"] = agent_stats["total_agents"]
    metrics["queue_buffer"] = agent_stats["output_queue_size"]

    queue_stats = orchestrator.queue.get_stats()
    metrics["tasks_pending"] = queue_stats.get("pending", 0)
    metrics["tasks_in_progress"] = queue_stats.get("in_progress", 0)
    metrics["tasks_completed"] = queue_stats.get("completed", 0)
    metrics["tasks_failed"] = queue_stats.get("failed", 0)

    return metrics


def format_metrics(metrics: dict[str, float]) -> str:
    """Format metrics dictionary into a compact string for logging."""
    ordered_keys = [
        "cpu_percent",
        "memory_percent",
        "proc_cpu_percent",
        "proc_memory_mb",
        "disk_used_mb",
        "disk_free_mb",
        "agents_active",
        "agents_total",
        "queue_buffer",
        "tasks_pending",
        "tasks_in_progress",
        "tasks_completed",
        "tasks_failed",
        "completed_total",
        "failed_total",
        "load_avg_1m",
    ]

    parts = []
    for key in ordered_keys:
        if key in metrics:
            value = metrics[key]
            parts.append(
                f"{key}={value:.2f}" if isinstance(value, float) else f"{key}={value}"
            )
    return " | ".join(parts)


def burn_in(
    duration_minutes: int, batch_size: int, max_agents: int, cooldown: int
) -> None:
    orchestrator = Orchestrator()
    run_id = datetime.utcnow().strftime("burnin-%Y%m%d-%H%M%S")

    orchestrator.queue.requeue_orphaned_tasks(force=True)

    tracked_tasks: dict[str, str] = {}
    total_completed = total_failed = 0
    deadline = time.time() + duration_minutes * 60
    iteration = 0

    process_handle = psutil.Process() if psutil else None
    if process_handle:
        # Prime CPU percent counters
        psutil.cpu_percent(interval=None)
        process_handle.cpu_percent(interval=None)

    print(f"Starting burn-in run {run_id} for {duration_minutes} minutes...")

    try:
        while time.time() < deadline:
            iteration += 1
            pending_stats = orchestrator.queue.get_stats()
            backlog = pending_stats.get("pending", 0) + pending_stats.get(
                "in_progress", 0
            )

            if backlog < batch_size:
                new_tasks = submit_batch(orchestrator, batch_size - backlog, run_id)
                for tid in new_tasks:
                    tracked_tasks[tid] = "submitted"

            orchestrator.process_tasks(max_agents=max_agents)

            completed, failed = update_counters(orchestrator, tracked_tasks)
            total_completed += completed
            total_failed += failed

            metrics = collect_resource_metrics(orchestrator, process_handle)
            metrics.update(
                {
                    "completed_total": float(total_completed),
                    "failed_total": float(total_failed),
                }
            )

            print(f"[{iteration:03d}] {format_metrics(metrics)}")

            if cooldown:
                time.sleep(cooldown)
    except KeyboardInterrupt:
        print("Interrupted; collecting final stats...")

    final_stats = orchestrator.queue.get_stats()
    print(
        "Final stats: "
        f"completed={final_stats.get('completed', 0)} "
        f"failed={final_stats.get('failed', 0)} "
        f"pending={final_stats.get('pending', 0)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a burn-in workload against the orchestrator queue."
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=30,
        help="Total runtime in minutes (default: 30)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Target number of concurrent tasks to keep queued",
    )
    parser.add_argument(
        "--max-agents",
        type=int,
        default=3,
        help="Maximum agents for orchestrator processing",
    )
    parser.add_argument(
        "--cooldown", type=int, default=5, help="Seconds to sleep between iterations"
    )

    args = parser.parse_args()
    burn_in(
        duration_minutes=args.duration_minutes,
        batch_size=args.batch_size,
        max_agents=args.max_agents,
        cooldown=args.cooldown,
    )


if __name__ == "__main__":
    main()
