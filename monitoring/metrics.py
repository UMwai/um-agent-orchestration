from __future__ import annotations
from prometheus_client import Counter, make_asgi_app  # standard way to expose metrics via HTTP

class METRICS:
    tasks_enqueued = Counter("autodev_tasks_enqueued_total", "Tasks enqueued")
    tasks_started  = Counter("autodev_tasks_started_total", "Tasks started")
    tasks_succeeded = Counter("autodev_tasks_succeeded_total", "Tasks succeeded")
    tasks_failed   = Counter("autodev_tasks_failed_total", "Tasks failed")
    commits_made   = Counter("autodev_commits_total", "WIP commits made by checkpointer")
    prs_opened     = Counter("autodev_prs_opened_total", "PRs opened by prizer")

def expose_metrics_asgi():
    return make_asgi_app()