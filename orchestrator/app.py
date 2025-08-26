from __future__ import annotations
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from orchestrator.models import TaskSpec, TaskStatus
from monitoring.metrics import expose_metrics_asgi, METRICS

# Try to use Redis-based dispatcher, fall back to simple dispatcher
USE_REDIS = False
enqueue_task = None

def setup_dispatcher():
    global USE_REDIS, enqueue_task
    try:
        # Test Redis connection first
        from redis import Redis
        import os
        redis_client = Redis(host=os.environ.get("REDIS_HOST", "localhost"), 
                           port=int(os.environ.get("REDIS_PORT", 6379)))
        redis_client.ping()  # This will fail if Redis is not available
        
        from orchestrator.dispatcher import enqueue_task as _enqueue_task
        from orchestrator.queue import jobs_q
        enqueue_task = _enqueue_task
        USE_REDIS = True
        print("📊 Using Redis-based task queue")
    except Exception as e:
        print(f"⚠️  Redis not available ({e.__class__.__name__}: {e}), using minimal task simulation")
        from orchestrator.minimal_dispatcher import (
            enqueue_minimal_task,
            get_minimal_task, get_all_minimal_tasks, 
            TASKS as MINIMAL_TASKS
        )
        globals().update({
            'get_simple_task': get_minimal_task,
            'get_all_simple_tasks': get_all_minimal_tasks,
            'SIMPLE_TASKS': MINIMAL_TASKS
        })
        enqueue_task = enqueue_minimal_task
        USE_REDIS = False

# Initialize dispatcher on startup
setup_dispatcher()
from typing import List
import json
import asyncio
from pathlib import Path

app = FastAPI(title="AutoDev Orchestrator")
app.mount("/metrics", expose_metrics_asgi())

# Add CORS middleware for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve dashboard static files
dashboard_path = Path(__file__).parent.parent / "dashboard"
if dashboard_path.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_path)), name="static")

TASKS: dict[str, TaskStatus] = {}
connected_clients: List[WebSocket] = []

@app.post("/tasks", response_model=dict)
async def submit_task(spec: TaskSpec):
    job_id = enqueue_task(spec)
    task_status = TaskStatus(
        id=spec.id, role=spec.role, branch=f"auto/{spec.role}/{spec.id}", state="queued"
    )
    TASKS[spec.id] = task_status
    
    # Broadcast update to connected dashboard clients
    await broadcast_update({
        "type": "task_submitted",
        "task": task_status.dict()
    })
    
    return {"job_id": job_id, "task_id": spec.id}

@app.get("/tasks/{task_id}", response_model=TaskStatus)
def get_task(task_id: str):
    if USE_REDIS:
        return TASKS[task_id]
    else:
        task = get_simple_task(task_id)
        if task is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Task not found")
        return task

@app.get("/tasks", response_model=List[TaskStatus])
def get_all_tasks():
    """Get all tasks with their current status"""
    if USE_REDIS:
        return list(TASKS.values())
    else:
        return get_all_simple_tasks()

@app.get("/api/metrics")
def get_metrics_summary():
    """Get current metrics for dashboard"""
    return {
        "tasks_enqueued": METRICS.tasks_enqueued._value._value,
        "tasks_started": METRICS.tasks_started._value._value,
        "tasks_succeeded": METRICS.tasks_succeeded._value._value,
        "tasks_failed": METRICS.tasks_failed._value._value,
        "commits_made": METRICS.commits_made._value._value,
        "prs_opened": METRICS.prs_opened._value._value,
    }

@app.get("/agents/status")
def get_agent_status():
    """Get status of all available agents and providers"""
    # This would normally query actual agent status
    # For now, returning mock data based on config
    return [
        {
            "name": "Claude Interactive",
            "provider": "claude_interactive",
            "status": "online",
            "capabilities": ["Full Access", "Code Generation", "File Operations"],
            "current_task": None
        },
        {
            "name": "Codex CLI", 
            "provider": "codex_cli",
            "status": "online",
            "capabilities": ["Code Generation", "Testing", "Debugging"],
            "current_task": None
        },
        {
            "name": "Backend Agent",
            "provider": "anthropic_api", 
            "status": "online",
            "capabilities": ["FastAPI", "Database", "Testing"],
            "current_task": None
        }
    ]

@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the main dashboard"""
    dashboard_file = Path(__file__).parent.parent / "dashboard" / "dashboard.html"
    if dashboard_file.exists():
        return HTMLResponse(dashboard_file.read_text())
    return HTMLResponse("<h1>Dashboard not found</h1>")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates"""
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Echo back for now - could handle commands here
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

async def broadcast_update(message: dict):
    """Broadcast updates to all connected dashboard clients"""
    if connected_clients:
        disconnected = []
        for client in connected_clients:
            try:
                await client.send_text(json.dumps(message))
            except:
                disconnected.append(client)
        
        # Clean up disconnected clients
        for client in disconnected:
            connected_clients.remove(client)