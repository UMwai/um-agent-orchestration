from __future__ import annotations
from fastapi import FastAPI
from orchestrator.models import TaskSpec, TaskStatus
from orchestrator.dispatcher import enqueue_task
from monitoring.metrics import expose_metrics_asgi

app = FastAPI(title="AutoDev Orchestrator")
app.mount("/metrics", expose_metrics_asgi())
TASKS: dict[str, TaskStatus] = {}

@app.post("/tasks", response_model=dict)
def submit_task(spec: TaskSpec):
    job_id = enqueue_task(spec)
    TASKS[spec.id] = TaskStatus(
        id=spec.id, role=spec.role, branch=f"auto/{spec.role}/{spec.id}", state="queued"
    )
    return {"job_id": job_id, "task_id": spec.id}

@app.get("/tasks/{task_id}", response_model=TaskStatus)
def get_task(task_id: str):
    return TASKS[task_id]