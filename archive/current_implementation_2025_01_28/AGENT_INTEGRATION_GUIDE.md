# 🤖 Agent Integration Guide: Claude Code & Codex

This guide shows how to integrate Claude Code and Codex directly into your repository so they can submit tasks to the AutoDev orchestration system.

## 🎯 Goal

Enable Claude Code or Codex running in this repository to:
1. Analyze code and identify tasks needed
2. Submit those tasks to the orchestration API
3. Monitor task progress and results
4. Continue with follow-up tasks as needed

## 🚀 Quick Start

### For Claude Code

```bash
# 1. Start the orchestrator (if not running)
make dev

# 2. Launch Claude Code in this repo with full access
claude --dangerously-skip-permissions

# 3. Use the helper commands below to submit tasks
```

### For Codex

```bash
# 1. Start the orchestrator (if not running)
make dev

# 2. Launch Codex in this repo with full access
codex --ask-for-approval never --sandbox danger-full-access

# 3. Use the helper commands below to submit tasks
```

## 📋 Task Submission Helpers

### Python Helper Function

Add this to your working session:

```python
import httpx
import json
import time
import uuid

def submit_orchestration_task(title: str, description: str, role: str = "generic", full_access: bool = True):
    """Submit a task to the AutoDev orchestration system"""
    
    task_spec = {
        "id": f"agent-task-{int(time.time())}-{str(uuid.uuid4())[:8]}",
        "title": title,
        "description": description,
        "role": role,  # Options: backend, frontend, data, ml, generic
        "full_access": full_access,
        "target_dir": "."
    }
    
    try:
        response = httpx.post(
            "http://localhost:8001/tasks",
            json=task_spec,
            timeout=10.0
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Task submitted: {result['task_id']}")
            print(f"🔗 Job ID: {result['job_id']}")
            return result
        else:
            print(f"❌ Task submission failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error submitting task: {e}")
        return None

def check_task_status(task_id: str):
    """Check the status of a submitted task"""
    try:
        response = httpx.get(f"http://localhost:8001/tasks/{task_id}")
        if response.status_code == 200:
            task = response.json()
            print(f"📊 Task {task_id}: {task['state']}")
            if task.get('last_error'):
                print(f"❌ Error: {task['last_error']}")
            return task
        else:
            print(f"❌ Failed to get task status: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error checking task: {e}")
        return None

def list_all_tasks():
    """List all tasks in the system"""
    try:
        response = httpx.get("http://localhost:8001/tasks")
        if response.status_code == 200:
            tasks = response.json()
            print(f"📋 Found {len(tasks)} tasks:")
            for task in tasks:
                status_emoji = {"queued": "⏳", "running": "🔄", "passed": "✅", "failed": "❌"}.get(task['state'], "❓")
                print(f"  {status_emoji} {task['id']}: {task['state']} ({task['role']})")
            return tasks
        else:
            print(f"❌ Failed to list tasks: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error listing tasks: {e}")
        return []

# Example usage:
# submit_orchestration_task("Fix authentication bug", "The login endpoint returns 500 errors", "backend")
# check_task_status("agent-task-123456")
# list_all_tasks()
```

### Bash Helper Commands

Add these to your shell session:

```bash
# Function to submit tasks via curl
submit_task() {
    local title="$1"
    local description="$2" 
    local role="${3:-generic}"
    local full_access="${4:-true}"
    local task_id="agent-task-$(date +%s)-$(head -c 4 /dev/urandom | xxd -p)"
    
    curl -X POST http://localhost:8001/tasks \
        -H "Content-Type: application/json" \
        -d "{
            \"id\": \"$task_id\",
            \"title\": \"$title\",
            \"description\": \"$description\", 
            \"role\": \"$role\",
            \"full_access\": $full_access
        }" | jq .
}

# Function to check task status
check_task() {
    curl -s "http://localhost:8001/tasks/$1" | jq .
}

# Function to list all tasks
list_tasks() {
    curl -s http://localhost:8001/tasks | jq '.[] | {id, state, role, title: .branch}'
}

# Examples:
# submit_task "Fix CSS styling" "The header is misaligned on mobile" "frontend"
# check_task "agent-task-123456"
# list_tasks
```

## 🎯 Common Integration Patterns

### 1. Code Analysis → Task Generation

When Claude Code or Codex analyzes your repository:

```python
# After analyzing code, submit specific tasks
def analyze_and_submit_tasks():
    # Example: After finding issues in the codebase
    
    submit_orchestration_task(
        title="Optimize database queries in user service",
        description="The user profile endpoint has N+1 query issues. Add proper joins and caching.",
        role="backend",
        full_access=True
    )
    
    submit_orchestration_task(
        title="Add TypeScript types to React components", 
        description="Components in src/components/ are missing proper TypeScript interfaces.",
        role="frontend",
        full_access=False
    )
    
    submit_orchestration_task(
        title="Create data pipeline for analytics",
        description="Build ETL pipeline to process user engagement metrics from logs.",
        role="data", 
        full_access=True
    )
```

### 2. Progressive Task Chains

Submit follow-up tasks based on results:

```python
def submit_with_followup(base_task_title, base_description, followup_tasks):
    # Submit initial task
    result = submit_orchestration_task(base_task_title, base_description)
    
    if result:
        task_id = result['task_id']
        
        # Wait for completion then submit followups
        import time
        while True:
            status = check_task_status(task_id)
            if status and status['state'] in ['passed', 'failed']:
                break
            time.sleep(10)
        
        if status['state'] == 'passed':
            for followup in followup_tasks:
                submit_orchestration_task(**followup)
```

### 3. Repository Workflow Integration

```python
def full_repository_workflow():
    """Complete workflow for repository improvements"""
    
    # 1. Analysis phase
    submit_orchestration_task(
        "Analyze codebase architecture",
        "Review current architecture and identify improvement opportunities",
        "generic"
    )
    
    # 2. Testing phase  
    submit_orchestration_task(
        "Add missing unit tests",
        "Identify and create unit tests for components with <80% coverage",
        "backend"
    )
    
    # 3. Documentation phase
    submit_orchestration_task(
        "Update API documentation", 
        "Generate OpenAPI docs and update README with current endpoints",
        "generic"
    )
    
    # 4. Performance phase
    submit_orchestration_task(
        "Optimize frontend bundle size",
        "Analyze webpack bundle and implement code splitting",
        "frontend"
    )
```

## 📊 Monitoring and Dashboard

### Access the Dashboard

Open http://localhost:8001 to see:
- Real-time task status
- Agent activity
- System metrics  
- Task submission interface

### API Endpoints for Integration

```python
# Get system metrics
def get_system_metrics():
    response = httpx.get("http://localhost:8001/api/metrics")
    return response.json()

# Get agent status
def get_agent_status():
    response = httpx.get("http://localhost:8001/agents/status") 
    return response.json()
```

## 🔧 Advanced Configuration

### Custom Role Creation

Create custom roles in `roles/` directory:

```yaml
# roles/ai_assistant.yaml
name: ai_assistant
branch_prefix: "feat/ai"
reviewers: ["@your-team"]
full_access: true
prompt: |
  You are an AI assistant specializing in code analysis and task delegation.
  Break down complex requirements into smaller, actionable tasks.
  Focus on maintainability and best practices.
```

### Environment Setup

```bash
# Add to your shell profile for persistent access
echo 'export AUTODEV_API_URL="http://localhost:8001"' >> ~/.bashrc

# Create aliases for common operations
echo 'alias submit-task="python -c \"from task_helpers import submit_orchestration_task; submit_orchestration_task\""' >> ~/.bashrc
```

## 🚀 Getting Started Checklist

- [ ] Orchestrator is running (`make dev`)
- [ ] Claude Code/Codex launched with full access
- [ ] Helper functions loaded in your session  
- [ ] Dashboard accessible at http://localhost:8001
- [ ] Test task submitted successfully

## 💡 Pro Tips

1. **Use descriptive task IDs** that include your agent name
2. **Set appropriate roles** for better agent specialization
3. **Monitor the dashboard** for real-time feedback
4. **Chain related tasks** for complex workflows  
5. **Use full_access: true** for file system operations
6. **Check task status** before submitting dependents

---

**Ready to orchestrate your 24/7 development workflow!** 🚀

The system is designed to work seamlessly with Claude Code and Codex as the primary task submitters and coordinators.