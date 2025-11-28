from __future__ import annotations

from prometheus_client import Counter, make_asgi_app  # standard way to expose metrics via HTTP


class METRICS:
    tasks_enqueued = Counter("autodev_tasks_enqueued_total", "Tasks enqueued")
    tasks_started = Counter("autodev_tasks_started_total", "Tasks started")
    tasks_succeeded = Counter("autodev_tasks_succeeded_total", "Tasks succeeded")
    tasks_failed = Counter("autodev_tasks_failed_total", "Tasks failed")
    commits_made = Counter("autodev_commits_total", "WIP commits made by checkpointer")
    prs_opened = Counter("autodev_prs_opened_total", "PRs opened by prizer")

    # Merge coordinator metrics
    merge_requests_queued = Counter(
        "autodev_merge_requests_queued_total", "PRs added to merge queue"
    )
    merge_conflicts_detected = Counter(
        "autodev_merge_conflicts_detected_total", "Merge conflicts detected"
    )
    auto_rebases_successful = Counter(
        "autodev_auto_rebases_successful_total", "Successful auto-rebases"
    )
    auto_rebases_failed = Counter("autodev_auto_rebases_failed_total", "Failed auto-rebases")
    prs_merged = Counter("autodev_prs_merged_total", "PRs successfully merged")


def expose_metrics_asgi():
    return make_asgi_app()
