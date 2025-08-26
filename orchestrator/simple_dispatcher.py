"""
Simple dispatcher that works without Redis for development and testing.
This allows the system to run without external dependencies.
"""

from __future__ import annotations
import asyncio
import threading
import uuid
from typing import Dict, Optional
from orchestrator.models import TaskSpec, TaskStatus
from monitoring.metrics import METRICS

# In-memory task storage for development
SIMPLE_TASKS: Dict[str, TaskStatus] = {}
task_queue: asyncio.Queue = None
worker_running = False

def init_simple_queue():
    """Initialize the simple in-memory queue"""
    global task_queue
    if task_queue is None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        task_queue = asyncio.Queue()

async def simple_worker():
    """Simple worker that processes tasks without Redis"""
    global worker_running
    worker_running = True
    
    print("🔄 Simple worker started (no Redis mode)")
    
    while worker_running:
        try:
            spec = await task_queue.get()
            if spec is None:  # Shutdown signal
                break
                
            task_id = spec.id
            print(f"📋 Processing task: {task_id} ({spec.role})")
            
            # Update task status
            if task_id in SIMPLE_TASKS:
                SIMPLE_TASKS[task_id].state = "running"
            
            # Simulate task execution
            success = await execute_simple_task(spec)
            
            # Update final status
            if task_id in SIMPLE_TASKS:
                SIMPLE_TASKS[task_id].state = "passed" if success else "failed"
                if not success:
                    SIMPLE_TASKS[task_id].last_error = "Simulated task failure"
            
            # Update metrics
            if success:
                METRICS.tasks_succeeded.inc()
            else:
                METRICS.tasks_failed.inc()
                
            print(f"✅ Task {task_id} {'completed' if success else 'failed'}")
            
        except Exception as e:
            print(f"❌ Worker error: {e}")
            METRICS.tasks_failed.inc()

async def execute_simple_task(spec: TaskSpec) -> bool:
    """
    Execute a task using the configured providers.
    This is a simplified version that focuses on CLI integration.
    """
    from providers.router import ProviderRouter
    from agents import registry
    
    try:
        # Get appropriate agent for the task
        agent = registry.get_agent_for_task(spec)
        print(f"🤖 Using agent: {agent.__class__.__name__}")
        
        # Create provider router with full access if requested
        router = ProviderRouter(full_access=spec.full_access)
        
        # Set up the prompt based on the task
        prompt = f"""
Task: {spec.title}

Description: {spec.description}

Role: {spec.role}
Full Access: {spec.full_access}
Target Directory: {spec.target_dir}

Requirements:
{spec.acceptance}

Please implement this task following best practices and the role-specific guidelines.
"""
        
        # Execute via provider
        print(f"🚀 Executing task with {'full access' if spec.full_access else 'standard'} permissions")
        
        # Simulate execution time
        await asyncio.sleep(2)
        
        # For now, simulate success most of the time
        import random
        return random.random() > 0.2  # 80% success rate
        
    except Exception as e:
        print(f"❌ Task execution failed: {e}")
        return False

def enqueue_simple_task(spec: TaskSpec) -> str:
    """Enqueue a task in the simple in-memory queue"""
    init_simple_queue()
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Store task status
    SIMPLE_TASKS[spec.id] = TaskStatus(
        id=spec.id, 
        role=spec.role, 
        branch=f"auto/{spec.role}/{spec.id}", 
        state="queued"
    )
    
    # Add to queue
    asyncio.create_task(task_queue.put(spec))
    
    # Update metrics
    METRICS.tasks_enqueued.inc()
    
    return job_id

def start_simple_worker():
    """Start the simple worker in a background thread"""
    def run_worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(simple_worker())
        loop.close()
    
    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()
    return thread

def get_simple_task(task_id: str) -> Optional[TaskStatus]:
    """Get task status from simple storage"""
    return SIMPLE_TASKS.get(task_id)

def get_all_simple_tasks() -> list[TaskStatus]:
    """Get all tasks from simple storage"""
    return list(SIMPLE_TASKS.values())