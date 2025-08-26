from __future__ import annotations
from orchestrator.models import TaskSpec
from orchestrator.queue import jobs_q
from monitoring.metrics import METRICS

def run_task(spec: TaskSpec) -> str:
    from agents import registry
    METRICS.tasks_started.inc()
    agent = registry.get_agent_for_task(spec)
    try:
        agent.plan_and_execute()
        METRICS.tasks_succeeded.inc()
        return f"Task {spec.id} completed on {agent.feature_branch}"
    except Exception as e:
        METRICS.tasks_failed.inc()
        raise e

def enqueue_task(spec: TaskSpec):
    job = jobs_q.enqueue(run_task, spec)
    METRICS.tasks_enqueued.inc()
    return job.id