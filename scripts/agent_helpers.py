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

import time
import uuid

import httpx

# Configuration
API_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 10.0


def submit_task(
    title: str,
    description: str,
    role: str = "generic",
    full_access: bool = True,
    provider: str | None = None,
    model: str | None = None,
) -> dict | None:
    """
    Submit a task to the AutoDev orchestration system

    Args:
        title: Brief task description
        description: Detailed requirements and acceptance criteria
        role: Agent role (backend, frontend, data, ml, generic)
        full_access: Enable full access mode (--dangerously-skip-permissions)
        provider: Specific provider to use (claude_cli, anthropic_api, etc.)
        model: Specific model to use (claude-3-5-sonnet-latest, gpt-4o, etc.)

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
        "target_dir": ".",
    }

    # Add optional provider and model specification
    if provider:
        task_spec["provider_override"] = provider
    if model:
        task_spec["model"] = model

    try:
        print(f"📤 Submitting task: {title}")
        response = httpx.post(f"{API_BASE_URL}/tasks", json=task_spec, timeout=DEFAULT_TIMEOUT)

        if response.status_code == 200:
            result = response.json()
            print("✅ Task submitted successfully!")
            print(f"   Task ID: {result['task_id']}")
            print(f"   Job ID: {result['job_id']}")
            print(f"   Role: {role}")
            print(f"   Selected Provider: {result.get('selected_provider', 'default')}")
            print(f"   Selected Model: {result.get('selected_model', 'default')}")
            print(f"   Full Access: {result.get('full_access', full_access)}")
            return result
        else:
            print(f"❌ Task submission failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error submitting task: {e}")
        return None


def get_providers() -> list[dict] | None:
    """Get list of available providers and their capabilities"""
    try:
        response = httpx.get(f"{API_BASE_URL}/api/providers", timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            providers = response.json()
            print(f"🔧 Available Providers ({len(providers)}):")
            for provider in providers:
                status_icon = "✅" if provider["available"] else "❌"
                print(f"  {status_icon} {provider['display_name']} ({provider['name']})")
                print(f"     Mode: {provider['mode']} | Model: {provider.get('model', 'N/A')}")
                print(f"     Capabilities: {', '.join(provider['capabilities'])}")
            return providers
        else:
            print(f"❌ Failed to get providers: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting providers: {e}")
        return None


def get_preferences() -> dict | None:
    """Get current model preferences"""
    try:
        response = httpx.get(f"{API_BASE_URL}/api/preferences", timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            preferences = response.json()
            print("🎛️ Current Preferences:")
            print(f"   Preferred Provider: {preferences.get('preferred_provider', 'None')}")
            print(f"   Preferred Model: {preferences.get('preferred_model', 'None')}")
            print(f"   Full Access Preferred: {preferences.get('full_access_preferred', False)}")

            role_prefs = preferences.get("role_preferences", {})
            if role_prefs:
                print("   Role-specific preferences:")
                for role, provider in role_prefs.items():
                    print(f"     {role}: {provider}")
            else:
                print("   No role-specific preferences set")

            return preferences
        else:
            print(f"❌ Failed to get preferences: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting preferences: {e}")
        return None


def set_preferences(
    preferred_provider: str | None = None,
    preferred_model: str | None = None,
    full_access_preferred: bool | None = None,
    role_preferences: dict[str, str] | None = None,
) -> dict | None:
    """
    Set model preferences

    Args:
        preferred_provider: Default provider to use
        preferred_model: Default model to use
        full_access_preferred: Prefer full access mode
        role_preferences: Dict mapping roles to preferred providers
    """
    try:
        # Get current preferences first
        current_response = httpx.get(f"{API_BASE_URL}/api/preferences", timeout=DEFAULT_TIMEOUT)
        if current_response.status_code == 200:
            current = current_response.json()
        else:
            current = {}

        # Update only provided values
        updated_preferences = {
            "preferred_provider": preferred_provider
            if preferred_provider is not None
            else current.get("preferred_provider"),
            "preferred_model": preferred_model
            if preferred_model is not None
            else current.get("preferred_model"),
            "full_access_preferred": full_access_preferred
            if full_access_preferred is not None
            else current.get("full_access_preferred", False),
            "role_preferences": role_preferences
            if role_preferences is not None
            else current.get("role_preferences", {}),
        }

        response = httpx.post(
            f"{API_BASE_URL}/api/preferences", json=updated_preferences, timeout=DEFAULT_TIMEOUT
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Preferences updated successfully!")
            get_preferences()  # Show updated preferences
            return result
        else:
            print(f"❌ Failed to set preferences: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error setting preferences: {e}")
        return None


def check_status(task_id: str) -> dict | None:
    """Check the status of a submitted task"""
    try:
        response = httpx.get(f"{API_BASE_URL}/tasks/{task_id}", timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            task = response.json()
            state_emoji = {"queued": "⏳", "running": "🔄", "passed": "✅", "failed": "❌"}.get(
                task["state"], "❓"
            )

            print(f"{state_emoji} Task {task_id}: {task['state']}")
            print(f"   Role: {task['role']}")
            print(f"   Branch: {task['branch']}")

            if task.get("provider"):
                print(f"   🔧 Provider: {task['provider']}")
            if task.get("model"):
                print(f"   🤖 Model: {task['model']}")

            if task.get("last_error"):
                print(f"   ❌ Error: {task['last_error']}")

            return task
        else:
            print(f"❌ Failed to get task status: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error checking task: {e}")
        return None


def list_tasks() -> list[dict]:
    """List all tasks in the system"""
    try:
        response = httpx.get(f"{API_BASE_URL}/tasks", timeout=DEFAULT_TIMEOUT)
        if response.status_code == 200:
            tasks = response.json()
            print(f"📋 Found {len(tasks)} tasks:")

            for task in tasks:
                state_emoji = {"queued": "⏳", "running": "🔄", "passed": "✅", "failed": "❌"}.get(
                    task["state"], "❓"
                )

                provider_info = f" | Provider: {task['provider']}" if task.get("provider") else ""
                model_info = f" | Model: {task['model']}" if task.get("model") else ""

                print(f"  {state_emoji} {task['id']}")
                print(
                    f"     State: {task['state']} | Role: {task['role']}{provider_info}{model_info}"
                )
                print(f"     Branch: {task['branch']}")

            return tasks
        else:
            print(f"❌ Failed to list tasks: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error listing tasks: {e}")
        return []


def get_metrics() -> dict | None:
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


def wait_for_task(task_id: str, max_wait: int = 300, poll_interval: int = 10) -> dict | None:
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
        if status and status["state"] in ["passed", "failed"]:
            if status["state"] == "passed":
                print(f"✅ Task {task_id} completed successfully!")
            else:
                print(f"❌ Task {task_id} failed!")
            return status

        print(
            f"   Still {status['state'] if status else 'unknown'}... checking again in {poll_interval}s"
        )
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
            "role": "generic",
        },
        {
            "title": "Security audit",
            "description": "Scan for security vulnerabilities, hardcoded secrets, and insecure patterns",
            "role": "backend",
        },
        {
            "title": "Performance analysis",
            "description": "Identify performance bottlenecks in both frontend and backend code",
            "role": "generic",
        },
        {
            "title": "Test coverage analysis",
            "description": "Analyze current test coverage and identify areas needing more tests",
            "role": "backend",
        },
    ]

    results = []
    for task in tasks:
        result = submit_task(**task)
        if result:
            results.append(result["task_id"])

    print(f"📋 Submitted {len(results)} analysis tasks")
    return results


def submit_improvement_workflow():
    """Submit tasks for common code improvements"""
    print("🚀 Starting code improvement workflow...")

    tasks = [
        {
            "title": "Add comprehensive error handling",
            "description": "Review all endpoints and functions, add proper error handling and logging",
            "role": "backend",
        },
        {
            "title": "Optimize frontend performance",
            "description": "Implement code splitting, lazy loading, and bundle optimization",
            "role": "frontend",
        },
        {
            "title": "Update documentation",
            "description": "Update README, API docs, and inline code documentation",
            "role": "generic",
        },
        {
            "title": "Add monitoring and metrics",
            "description": "Implement application metrics, health checks, and monitoring endpoints",
            "role": "backend",
        },
    ]

    results = []
    for task in tasks:
        result = submit_task(**task)
        if result:
            results.append(result["task_id"])

    print(f"📋 Submitted {len(results)} improvement tasks")
    return results


# Convenience aliases
submit = submit_task
status = check_status
tasks = list_tasks
metrics = get_metrics
wait = wait_for_task
providers = get_providers
preferences = get_preferences
set_prefs = set_preferences

# Print help when loaded
print("🤖 Agent Helper Functions Loaded!")
print("Available functions:")
print(
    "  submit_task(title, description, role='generic', full_access=True, provider=None, model=None)"
)
print("  check_status(task_id)")
print("  list_tasks()")
print("  get_metrics()")
print("  wait_for_task(task_id)")
print("  get_providers()")
print("  get_preferences()")
print("  set_preferences(preferred_provider=None, preferred_model=None, ...)")
print("  submit_analysis_workflow()")
print("  submit_improvement_workflow()")
print()
print("Quick aliases: submit, status, tasks, metrics, wait, providers, preferences, set_prefs")
print()
print("Example usage:")
print('  submit("Fix bug in auth", "Login endpoint returns 500 error", "backend")')
print('  submit("Add feature", "Description", "backend", provider="claude_cli", model="sonnet")')
print("  providers()  # List available providers and models")
print('  set_prefs(preferred_provider="anthropic_api", full_access_preferred=True)')
print('  status("task-id-here")')
print("  tasks()")
print()
print("Dashboard: http://localhost:8001")
