#!/usr/bin/env python3
"""
Agent Helper Functions for Claude Code and Codex Integration

Usage:
    # In Claude Code or Codex session:
    exec(open('scripts/agent_helpers.py').read())
    
    # Then use the helper functions:
    submit_task("Fix authentication bug", "Login endpoint returns 500", "backend")
    check_status("my-task-id")
    list_tasks()
"""

import httpx
import json
import time
import uuid
from typing import Dict, List, Optional

# Configuration
API_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 10.0

def submit_task(title: str, description: str, role: str = "generic", full_access: bool = True) -> Optional[Dict]:
    """
    Submit a task to the AutoDev orchestration system
    
    Args:
        title: Brief task description
        description: Detailed requirements and acceptance criteria
        role: Agent role (backend, frontend, data, ml, generic)
        full_access: Enable full access mode (--dangerously-skip-permissions)
    
    Returns:
        Dict with task_id and job_id if successful, None otherwise
    """
    task_id = f"agent-task-{int(time.time())}-{str(uuid.uuid4())[:8]}"
    
    task_spec = {
        "id": task_id,
        "title": title,
        "description": description,
        "role": role,
        "full_access": full_access,
        "target_dir": "."
    }
    
    try:
        print(f"📤 Submitting task: {title}")
        response = httpx.post(
            f"{API_BASE_URL}/tasks",
            json=task_spec,
            timeout=DEFAULT_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Task submitted successfully!")
            print(f"   Task ID: {result['task_id']}")
            print(f"   Job ID: {result['job_id']}")
            print(f"   Role: {role}")
            print(f"   Full Access: {full_access}")
            return result
        else:
            print(f"❌ Task submission failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error submitting task: {e}")
        return None

def check_status(task_id: str) -> Optional[Dict]:
    """Check the status of a submitted task"""
    try:
        response = httpx.get(f"{API_BASE_URL}/tasks/{task_id}", timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            task = response.json()
            state_emoji = {
                "queued": "⏳", 
                "running": "🔄", 
                "passed": "✅", 
                "failed": "❌"
            }.get(task['state'], "❓")
            
            print(f"{state_emoji} Task {task_id}: {task['state']}")
            print(f"   Role: {task['role']}")
            print(f"   Branch: {task['branch']}")
            
            if task.get('last_error'):
                print(f"   ❌ Error: {task['last_error']}")
            
            return task
        else:
            print(f"❌ Failed to get task status: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error checking task: {e}")
        return None

def list_tasks() -> List[Dict]:
    """List all tasks in the system"""
    try:
        response = httpx.get(f"{API_BASE_URL}/tasks", timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            tasks = response.json()
            print(f"📋 Found {len(tasks)} tasks:")
            
            for task in tasks:
                state_emoji = {
                    "queued": "⏳", 
                    "running": "🔄", 
                    "passed": "✅", 
                    "failed": "❌"
                }.get(task['state'], "❓")
                
                print(f"  {state_emoji} {task['id']}")
                print(f"     State: {task['state']} | Role: {task['role']} | Branch: {task['branch']}")
            
            return tasks
        else:
            print(f"❌ Failed to list tasks: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error listing tasks: {e}")
        return []

def get_metrics() -> Optional[Dict]:
    """Get system metrics"""
    try:
        response = httpx.get(f"{API_BASE_URL}/api/metrics", timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            metrics = response.json()
            print("📊 System Metrics:")
            print(f"   Tasks Enqueued: {metrics['tasks_enqueued']}")
            print(f"   Tasks Succeeded: {metrics['tasks_succeeded']}")
            print(f"   Tasks Failed: {metrics['tasks_failed']}")
            print(f"   Commits Made: {metrics['commits_made']}")
            print(f"   PRs Opened: {metrics['prs_opened']}")
            return metrics
        else:
            print(f"❌ Failed to get metrics: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting metrics: {e}")
        return None

def wait_for_task(task_id: str, max_wait: int = 300, poll_interval: int = 10) -> Optional[Dict]:
    """
    Wait for a task to complete
    
    Args:
        task_id: Task ID to wait for
        max_wait: Maximum time to wait in seconds
        poll_interval: How often to check status in seconds
    """
    print(f"⏳ Waiting for task {task_id} to complete...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status = check_status(task_id)
        if status and status['state'] in ['passed', 'failed']:
            if status['state'] == 'passed':
                print(f"✅ Task {task_id} completed successfully!")
            else:
                print(f"❌ Task {task_id} failed!")
            return status
        
        print(f"   Still {status['state'] if status else 'unknown'}... checking again in {poll_interval}s")
        time.sleep(poll_interval)
    
    print(f"⏰ Timeout waiting for task {task_id}")
    return None

# Workflow helpers
def submit_analysis_workflow():
    """Submit a complete analysis workflow"""
    print("🔍 Starting repository analysis workflow...")
    
    tasks = [
        {
            "title": "Analyze codebase architecture",
            "description": "Review the current codebase structure, identify architectural patterns, and suggest improvements",
            "role": "generic"
        },
        {
            "title": "Security audit", 
            "description": "Scan for security vulnerabilities, hardcoded secrets, and insecure patterns",
            "role": "backend"
        },
        {
            "title": "Performance analysis",
            "description": "Identify performance bottlenecks in both frontend and backend code",
            "role": "generic"
        },
        {
            "title": "Test coverage analysis",
            "description": "Analyze current test coverage and identify areas needing more tests",
            "role": "backend"
        }
    ]
    
    results = []
    for task in tasks:
        result = submit_task(**task)
        if result:
            results.append(result['task_id'])
    
    print(f"📋 Submitted {len(results)} analysis tasks")
    return results

def submit_improvement_workflow():
    """Submit tasks for common code improvements"""
    print("🚀 Starting code improvement workflow...")
    
    tasks = [
        {
            "title": "Add comprehensive error handling",
            "description": "Review all endpoints and functions, add proper error handling and logging",
            "role": "backend"
        },
        {
            "title": "Optimize frontend performance",
            "description": "Implement code splitting, lazy loading, and bundle optimization",
            "role": "frontend"
        },
        {
            "title": "Update documentation",
            "description": "Update README, API docs, and inline code documentation",
            "role": "generic"
        },
        {
            "title": "Add monitoring and metrics",
            "description": "Implement application metrics, health checks, and monitoring endpoints",
            "role": "backend"
        }
    ]
    
    results = []
    for task in tasks:
        result = submit_task(**task)
        if result:
            results.append(result['task_id'])
    
    print(f"📋 Submitted {len(results)} improvement tasks")
    return results

# Convenience aliases
submit = submit_task
status = check_status
tasks = list_tasks
metrics = get_metrics
wait = wait_for_task

# Print help when loaded
print("🤖 Agent Helper Functions Loaded!")
print("Available functions:")
print("  submit_task(title, description, role='generic', full_access=True)")
print("  check_status(task_id)")
print("  list_tasks()")
print("  get_metrics()")
print("  wait_for_task(task_id)")
print("  submit_analysis_workflow()")
print("  submit_improvement_workflow()")
print()
print("Quick aliases: submit, status, tasks, metrics, wait")
print()
print("Example usage:")
print('  submit("Fix bug in auth", "Login endpoint returns 500 error", "backend")')
print('  status("task-id-here")')
print('  tasks()')
print()
print("Dashboard: http://localhost:8000")