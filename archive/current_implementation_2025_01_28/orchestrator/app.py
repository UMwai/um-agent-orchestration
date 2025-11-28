from __future__ import annotations

# Load environment variables first
from dotenv import load_dotenv

load_dotenv()

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from monitoring.metrics import METRICS, expose_metrics_asgi
from orchestrator.models import ModelPreference, ProviderInfo, TaskSpec, TaskStatus

# Try to use Redis-based dispatcher, fall back to simple dispatcher
USE_REDIS = False
enqueue_task = None


def setup_dispatcher():
    global USE_REDIS, enqueue_task
    try:
        # Test Redis connection first
        import os

        from redis import Redis

        redis_client = Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
        )
        redis_client.ping()  # This will fail if Redis is not available

        from orchestrator.dispatcher import enqueue_task as _enqueue_task

        enqueue_task = _enqueue_task
        USE_REDIS = True
        print("📊 Using Redis-based task queue")
    except Exception as e:
        print(
            f"⚠️  Redis not available ({e.__class__.__name__}: {e}), using minimal task simulation"
        )
        from orchestrator.minimal_dispatcher import TASKS as MINIMAL_TASKS
        from orchestrator.minimal_dispatcher import (
            enqueue_minimal_task,
            get_all_minimal_tasks,
            get_minimal_task,
        )

        globals().update(
            {
                "get_simple_task": get_minimal_task,
                "get_all_simple_tasks": get_all_minimal_tasks,
                "SIMPLE_TASKS": MINIMAL_TASKS,
            }
        )
        enqueue_task = enqueue_minimal_task
        USE_REDIS = False


import json
import os
from pathlib import Path

# Initialize dispatcher on startup
setup_dispatcher()

# Initialize task recovery if Redis is available
if USE_REDIS:
    try:
        from orchestrator.recovery import run_startup_recovery

        recovery_stats = run_startup_recovery()
        print(
            f"🔄 Task recovery completed: {recovery_stats.get('total_recovered', 0)} tasks restored"
        )
    except Exception as e:
        print(f"⚠️  Task recovery failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan management."""
    # Startup
    from orchestrator.cli_session_manager import get_cli_session_manager

    # Set the main event loop reference for thread-safe async operations
    cli_session_manager = get_cli_session_manager()
    cli_session_manager.set_main_loop(asyncio.get_event_loop())
    print("🔧 CLI Session Manager initialized with main event loop")

    yield  # App runs here

    # Shutdown
    print("📤 Shutting down CLI Session Manager")


app = FastAPI(title="Agent UM-7", lifespan=lifespan)
app.mount("/metrics", expose_metrics_asgi())

# Add CORS middleware for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve dashboard static files (legacy and Vite build)
dashboard_path = Path(__file__).parent.parent / "dashboard"
dist_path = dashboard_path / "dist"
if dashboard_path.exists():
    # Legacy static (if referenced via /static)
    app.mount("/static", StaticFiles(directory=str(dashboard_path)), name="static")
    # Vite build assets (if present)
    if dist_path.exists():
        # Serve Vite's /assets from built folder
        assets_path = dist_path / "assets"
        if assets_path.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

TASKS: dict[str, TaskStatus] = {}
connected_clients: list[WebSocket] = []

# Model preferences storage (in-memory for now, could be moved to Redis/DB later)
MODEL_PREFERENCES: dict[str, ModelPreference] = {"default": ModelPreference()}


@app.get("/api/providers")
def get_available_providers():
    """Get list of available providers categorized by CLI vs API with their capabilities and models"""
    import subprocess

    from orchestrator.settings import load_settings
    from providers.models import get_models_for_provider, get_provider_type

    settings = load_settings()
    cli_providers = []
    api_providers = []

    # Helper function to check if CLI binary is available
    def is_binary_available(binary_name: str) -> bool:
        if not binary_name:
            return False
        try:
            subprocess.run([binary_name, "--version"], capture_output=True, timeout=5)
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            return False

    # Helper function to get detailed status information
    def get_status_details(name: str, cfg) -> dict:
        details = {}
        if cfg.mode in ["cli", "interactive"] and cfg.binary:
            details["binary"] = cfg.binary
            details["binary_found"] = is_binary_available(cfg.binary)
            if cfg.args:
                details["args"] = cfg.args
        elif cfg.mode == "api":
            if name == "anthropic_api":
                details["api_key_configured"] = bool(os.environ.get("ANTHROPIC_API_KEY"))
            elif name == "openai_api":
                details["api_key_configured"] = bool(os.environ.get("OPENAI_API_KEY"))
            elif name == "gemini_api":
                details["api_key_configured"] = bool(os.environ.get("GOOGLE_API_KEY"))
        return details

    # Process each configured provider
    for name, cfg in settings.providers.items():
        # Determine display name and capabilities
        display_name = name.replace("_", " ").title()
        capabilities = []

        # Determine provider type
        provider_type = cfg.provider_type or get_provider_type(name, cfg.mode)

        # Add capabilities based on provider type and mode
        if provider_type == "cli":
            capabilities.extend(["CLI", "Local Execution"])
            if cfg.mode == "interactive":
                capabilities.extend(["Interactive", "Full Access", "File Operations"])

            if "claude" in name:
                capabilities.extend(["Code Generation", "Analysis", "File Operations"])
            elif "codex" in name:
                capabilities.extend(["Code Generation", "Testing", "Debugging"])
            elif "gemini" in name:
                capabilities.extend(["Code Generation", "Analysis", "Multimodal"])
            elif "cursor" in name:
                capabilities.extend(["Code Generation", "Editing", "Refactoring"])

        elif provider_type == "api":
            capabilities.extend(["API", "Reliable", "Remote"])
            if name == "anthropic_api":
                capabilities.extend(["Code Generation", "Analysis", "Long Context"])
            elif name == "openai_api":
                capabilities.extend(["Code Generation", "Analysis", "General Purpose"])
            elif name == "gemini_api":
                capabilities.extend(["Code Generation", "Analysis", "Multimodal"])

        # Get available models
        available_models = cfg.available_models or get_models_for_provider(name)

        # Check availability
        available = True
        if provider_type == "cli" and cfg.binary:
            available = is_binary_available(cfg.binary)
        elif provider_type == "api":
            # For API providers, check if required env vars are set
            if name == "anthropic_api":
                available = bool(os.environ.get("ANTHROPIC_API_KEY"))
            elif name == "openai_api":
                available = bool(os.environ.get("OPENAI_API_KEY"))
            elif name == "gemini_api":
                available = bool(os.environ.get("GOOGLE_API_KEY"))

        # Get detailed status
        status_details = get_status_details(name, cfg)

        provider_info = ProviderInfo(
            name=name,
            display_name=display_name,
            mode=cfg.mode,
            provider_type=provider_type,
            model=cfg.model,
            available_models=available_models,
            description=cfg.description or f"{display_name} - {cfg.mode.upper()} mode",
            available=available,
            capabilities=capabilities,
            status_details=status_details,
        )

        # Categorize by provider type
        if provider_type == "cli":
            cli_providers.append(provider_info)
        else:
            api_providers.append(provider_info)

    return {
        "cli_providers": cli_providers,
        "api_providers": api_providers,
        "summary": {
            "total_providers": len(cli_providers) + len(api_providers),
            "cli_count": len(cli_providers),
            "api_count": len(api_providers),
            "available_cli": len([p for p in cli_providers if p.available]),
            "available_api": len([p for p in api_providers if p.available]),
        },
    }


@app.get("/api/preferences", response_model=ModelPreference)
def get_model_preferences(user_id: str = "default"):
    """Get current model preferences for a user"""
    return MODEL_PREFERENCES.get(user_id, ModelPreference(user_id=user_id))


@app.post("/api/preferences", response_model=ModelPreference)
def set_model_preferences(preferences: ModelPreference, user_id: str = "default"):
    """Set model preferences for a user"""
    preferences.user_id = user_id
    MODEL_PREFERENCES[user_id] = preferences
    return preferences


@app.get("/api/providers/{provider_name}/status")
def get_provider_status(provider_name: str):
    """Get detailed status information for a specific provider"""
    import subprocess

    from orchestrator.settings import load_settings
    from providers.models import get_models_for_provider, get_provider_type

    settings = load_settings()

    if provider_name not in settings.providers:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Provider not found")

    cfg = settings.providers[provider_name]
    provider_type = cfg.provider_type or get_provider_type(provider_name, cfg.mode)

    # Check detailed status
    status = {
        "name": provider_name,
        "display_name": provider_name.replace("_", " ").title(),
        "mode": cfg.mode,
        "provider_type": provider_type,
        "model": cfg.model,
        "available_models": cfg.available_models or get_models_for_provider(provider_name),
        "description": cfg.description,
        "available": True,
        "details": {},
    }

    if provider_type == "cli" and cfg.binary:
        try:
            result = subprocess.run(
                [cfg.binary, "--version"], capture_output=True, text=True, timeout=10
            )
            status["details"]["binary"] = cfg.binary
            status["details"]["binary_found"] = True
            status["details"]["version_info"] = (
                result.stdout.strip() if result.returncode == 0 else "Version check failed"
            )
            if cfg.args:
                status["details"]["args"] = cfg.args
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError) as e:
            status["available"] = False
            status["details"]["binary"] = cfg.binary
            status["details"]["binary_found"] = False
            status["details"]["error"] = str(e)
    elif provider_type == "api":
        # Check API key availability and connectivity
        if provider_name == "anthropic_api":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            status["details"]["api_key_configured"] = bool(api_key)
            status["details"]["api_key_partial"] = (
                (api_key[:8] + "..." + api_key[-4:]) if api_key and len(api_key) > 12 else None
            )
            status["available"] = bool(api_key)
        elif provider_name == "openai_api":
            api_key = os.environ.get("OPENAI_API_KEY")
            status["details"]["api_key_configured"] = bool(api_key)
            status["details"]["api_key_partial"] = (
                (api_key[:8] + "..." + api_key[-4:]) if api_key and len(api_key) > 12 else None
            )
            status["available"] = bool(api_key)
        elif provider_name == "gemini_api":
            api_key = os.environ.get("GOOGLE_API_KEY")
            status["details"]["api_key_configured"] = bool(api_key)
            status["details"]["api_key_partial"] = (
                (api_key[:8] + "..." + api_key[-4:]) if api_key and len(api_key) > 12 else None
            )
            status["available"] = bool(api_key)

        # Add API-specific details
        if cfg.max_tokens:
            status["details"]["max_tokens"] = cfg.max_tokens

    # Add configuration details
    status["details"]["configuration"] = {
        "default_model": cfg.model,
        "total_models": len(status["available_models"]),
        "mode": cfg.mode,
    }

    return status


@app.post("/tasks", response_model=dict)
async def submit_task(spec: TaskSpec):
    # Apply model preferences if not explicitly set in the task
    preferences = MODEL_PREFERENCES.get("default", ModelPreference())

    # If no provider override specified, check user preferences
    if not spec.provider_override:
        # Check role-specific preferences first
        if spec.role in preferences.role_preferences:
            spec.provider_override = preferences.role_preferences[spec.role]
        # Fall back to general preferred provider
        elif preferences.preferred_provider:
            spec.provider_override = preferences.preferred_provider

    # If no model specified, use user's preferred model
    if not spec.model and preferences.preferred_model:
        spec.model = preferences.preferred_model

    # Apply full access preference if not explicitly set
    if not spec.full_access and preferences.full_access_preferred:
        spec.full_access = True

    job_id = enqueue_task(spec)
    task_status = TaskStatus(
        id=spec.id,
        role=spec.role,
        branch=f"auto/{spec.role}/{spec.id}",
        state="queued",
        provider=spec.provider_override,
        model=spec.model,
    )

    if USE_REDIS:
        # Store task status in Redis for cross-process communication
        from orchestrator.queue import _redis

        key = f"task_status:{spec.id}"
        _redis.setex(key, 86400, task_status.json())  # 24 hour expiry
    else:
        TASKS[spec.id] = task_status

    # Broadcast update to connected dashboard clients
    await broadcast_update({"type": "task_submitted", "task": task_status.dict()})

    return {
        "job_id": job_id,
        "task_id": spec.id,
        "selected_provider": spec.provider_override,
        "selected_model": spec.model,
        "full_access": spec.full_access,
    }


@app.get("/tasks/{task_id}", response_model=TaskStatus)
def get_task(task_id: str):
    if USE_REDIS:
        # Get task status from Redis
        from orchestrator.queue import _redis

        key = f"task_status:{task_id}"
        task_data = _redis.get(key)
        if task_data:
            return TaskStatus.parse_raw(task_data)
        else:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Task not found")
    else:
        task = get_simple_task(task_id)
        if task is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Task not found")
        return task


@app.get("/tasks", response_model=list[TaskStatus])
def get_all_tasks():
    """Get all tasks with their current status"""
    if USE_REDIS:
        # Get all task statuses from Redis
        from orchestrator.queue import _redis

        tasks = []
        for key in _redis.keys("task_status:*"):
            task_data = _redis.get(key)
            if task_data:
                tasks.append(TaskStatus.parse_raw(task_data))
        return tasks
    else:
        return get_all_simple_tasks()


@app.get("/api/metrics")
def get_metrics_summary():
    """Get current metrics for dashboard"""
    import os
    import subprocess

    # Get repository information
    try:
        repo_path = os.getcwd()
        repo_name = (
            subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=repo_path)
            .decode()
            .strip()
            .split("/")[-1]
            .replace(".git", "")
        )
        current_branch = (
            subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
            .decode()
            .strip()
        )
    except:
        repo_name = "unknown"
        current_branch = "unknown"

    return {
        "repository": {"name": repo_name, "path": repo_path, "branch": current_branch},
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
            "current_task": None,
        },
        {
            "name": "Codex CLI",
            "provider": "codex_cli",
            "status": "online",
            "capabilities": ["Code Generation", "Testing", "Debugging"],
            "current_task": None,
        },
        {
            "name": "Backend Agent",
            "provider": "anthropic_api",
            "status": "online",
            "capabilities": ["FastAPI", "Database", "Testing"],
            "current_task": None,
        },
    ]


@app.get("/api/repositories")
def get_available_repositories():
    """Discover available repositories in parent directory"""
    import os
    import subprocess

    repos = []
    parent_dir = "/home/umwai"

    # Scan for git repositories
    for item in os.listdir(parent_dir):
        item_path = os.path.join(parent_dir, item)
        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, ".git")):
            try:
                # Get repository URL
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=item_path,
                    capture_output=True,
                    text=True,
                )
                remote_url = result.stdout.strip() if result.returncode == 0 else None

                # Get current branch
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=item_path,
                    capture_output=True,
                    text=True,
                )
                current_branch = (
                    branch_result.stdout.strip() if branch_result.returncode == 0 else "main"
                )

                # Check for specs directory
                specs_dir = os.path.join(item_path, "specs")
                has_specs = os.path.isdir(specs_dir)

                # Get spec files if they exist
                spec_files = []
                if has_specs:
                    spec_files = [f for f in os.listdir(specs_dir) if f.endswith(".md")]

                repos.append(
                    {
                        "name": item,
                        "path": item_path,
                        "url": f"file://{item_path}",
                        "remote_url": remote_url,
                        "current_branch": current_branch,
                        "has_specs": has_specs,
                        "spec_files": spec_files,
                    }
                )
            except Exception:
                # Skip repositories that can't be accessed
                continue

    # Sort by name for consistent ordering
    repos.sort(key=lambda x: x["name"])

    return {
        "repositories": repos,
        "parent_directory": parent_dir,
        "current_repo": {
            "name": "um-agent-orchestration",
            "path": os.getcwd(),
            "url": f"file://{os.getcwd()}",
        },
    }


@app.get("/api/repositories/{repo_name}/branches")
def get_repository_branches(repo_name: str):
    """Get available branches for a specific repository"""
    import os
    import subprocess

    # Find repository path
    parent_dir = "/home/umwai"
    if repo_name == "um-agent-orchestration":
        repo_path = os.getcwd()
    else:
        repo_path = os.path.join(parent_dir, repo_name)

    if not os.path.exists(repo_path) or not os.path.exists(os.path.join(repo_path, ".git")):
        return {"error": "Repository not found or not a git repository"}

    try:
        # Fetch latest changes
        subprocess.run(["git", "fetch"], cwd=repo_path, capture_output=True)

        # Get all remote branches
        result = subprocess.run(
            ["git", "branch", "-r", "--format=%(refname:short)"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        branches = []
        for line in result.stdout.strip().split("\n"):
            if line and not line.endswith("/HEAD"):
                branch_name = line.replace("origin/", "")
                branches.append(branch_name)

        # Get current branch
        current_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        current_branch = current_result.stdout.strip() if current_result.returncode == 0 else "main"

        return {
            "repository": repo_name,
            "branches": sorted(branches),
            "current_branch": current_branch,
            "default_suggestions": ["main", "master", "develop", "staging", "dev"],
        }
    except Exception as e:
        return {"error": f"Failed to get branches: {e!s}"}


@app.get("/api/repositories/{repo_name}/specs")
def get_repository_specs(repo_name: str):
    """Get engineering specs for a specific repository"""
    import os

    # Find repository path
    parent_dir = "/home/umwai"
    if repo_name == "um-agent-orchestration":
        repo_path = os.getcwd()
    else:
        repo_path = os.path.join(parent_dir, repo_name)

    specs_dir = os.path.join(repo_path, "specs")

    if not os.path.exists(specs_dir):
        return {"specs": [], "has_specs": False}

    try:
        specs = []
        for file_name in sorted(os.listdir(specs_dir)):
            if file_name.endswith(".md"):
                file_path = os.path.join(specs_dir, file_name)
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # Extract title from first heading
                title = file_name.replace(".md", "").replace("-", " ").title()
                for line in content.split("\n"):
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break

                # Extract structured information
                def extract_spec_info(content):
                    lines = content.split("\n")
                    summary = ""
                    phases = []
                    team_goals = []
                    responsibilities = []

                    current_section = ""
                    for i, line in enumerate(lines):
                        line = line.strip()

                        # Extract summary (first meaningful paragraph)
                        if not summary and line and not line.startswith("#") and len(line) > 20:
                            summary = line[:200] + "..." if len(line) > 200 else line

                        # Extract phases
                        if "phase" in line.lower() and line.startswith("#"):
                            phase_text = line.replace("#", "").strip()
                            # Get next few lines for phase details
                            phase_details = []
                            for j in range(i + 1, min(i + 4, len(lines))):
                                if lines[j].strip() and not lines[j].startswith("#"):
                                    phase_details.append(lines[j].strip())
                            phases.append(
                                {
                                    "title": phase_text,
                                    "details": " ".join(phase_details)[:150] + "..."
                                    if len(" ".join(phase_details)) > 150
                                    else " ".join(phase_details),
                                }
                            )

                        # Extract team responsibilities
                        if any(
                            keyword in line.lower()
                            for keyword in ["responsibilities", "goals", "deliverables"]
                        ) and line.startswith("#"):
                            current_section = "responsibilities"
                        elif current_section == "responsibilities" and line.startswith("-"):
                            resp = line.replace("-", "").replace("*", "").strip()
                            if len(resp) > 10:  # Filter out short items
                                responsibilities.append(
                                    resp[:100] + "..." if len(resp) > 100 else resp
                                )

                    return {
                        "summary": summary,
                        "phases": phases[:5],  # Limit to 5 phases
                        "responsibilities": responsibilities[:8],  # Limit to 8 items
                        "key_sections": len([l for l in lines if l.startswith("#")]),
                    }

                spec_info = extract_spec_info(content)

                specs.append(
                    {
                        "filename": file_name,
                        "title": title,
                        "summary": spec_info["summary"],
                        "content": content,  # Full content, not truncated
                        "size": len(content),
                        "phases": spec_info["phases"],
                        "responsibilities": spec_info["responsibilities"],
                        "key_sections": spec_info["key_sections"],
                    }
                )

        return {
            "repository": repo_name,
            "specs": specs,
            "has_specs": True,
            "specs_count": len(specs),
        }
    except Exception as e:
        return {"error": f"Failed to read specs: {e!s}", "has_specs": False}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the main dashboard (prefer Vite build if available)."""
    base = Path(__file__).parent.parent / "dashboard"
    vite_index = base / "dist" / "index.html"
    legacy_file = base / "dashboard.html"
    if vite_index.exists():
        # Serve built Vite app
        return HTMLResponse(vite_index.read_text())
    if legacy_file.exists():
        # Fallback to legacy inline-Babel dashboard
        return HTMLResponse(legacy_file.read_text())
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


@app.websocket("/ws/cli/{session_id}")
async def cli_websocket_endpoint(websocket: WebSocket, session_id: str, token: str = None):
    """WebSocket endpoint for real-time CLI session communication"""
    from orchestrator.cli_websocket import get_cli_websocket_handler

    handler = get_cli_websocket_handler()
    await handler.handle_connection(websocket, session_id, token)


@app.post("/api/cli/sessions")
async def create_cli_session(request: dict):
    """Create a new CLI session"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    cli_tool = request.get("cli_tool", "claude")
    mode = request.get("mode", "cli")
    full_access = request.get("full_access", False)
    cwd = request.get("cwd")

    manager = get_cli_session_manager()

    # Validate CLI tool
    valid_tools = ["claude", "codex", "gemini", "cursor", "bash", "mock"]
    if cli_tool not in valid_tools:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400, detail=f"Invalid CLI tool. Must be one of: {valid_tools}"
        )

    try:
        session_id = await manager.create_session(cli_tool, mode, cwd)

        # Start the CLI process
        success = await manager.start_cli_process(session_id, full_access)

        if not success:
            await manager.terminate_session(session_id)
            from fastapi import HTTPException

            raise HTTPException(status_code=500, detail="Failed to start CLI process")

        session_info = manager.get_session_info(session_id)

        return {
            "session_id": session_id,
            "cli_tool": cli_tool,
            "mode": mode,
            "state": session_info.state.value,
            "websocket_url": f"/ws/cli/{session_id}",
            "full_access": full_access,
        }

    except Exception as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=f"Failed to create CLI session: {e!s}")


@app.get("/api/cli/providers")
async def get_available_cli_providers():
    """Check which CLI tools are available on the system"""
    import shutil

    providers = {
        "claude": {
            "name": "Claude",
            "binary": "claude",
            "available": shutil.which("claude") is not None,
            "path": shutil.which("claude"),
            "full_access_flag": "--dangerously-skip-permissions",
            "models": ["claude-3-sonnet", "claude-3-opus", "claude-3.5-sonnet"],
        },
        "codex": {
            "name": "Codex",
            "binary": "codex",
            "available": shutil.which("codex") is not None,
            "path": shutil.which("codex"),
            "full_access_flag": "--sandbox danger-full-access",
            "models": ["gpt-4", "gpt-5"],
        },
        "gemini": {
            "name": "Gemini",
            "binary": "gemini",
            "available": shutil.which("gemini") is not None,
            "path": shutil.which("gemini"),
            "full_access_flag": "--full-access",
            "models": ["gemini-pro", "gemini-ultra"],
        },
        "cursor": {
            "name": "Cursor",
            "binary": "cursor-agent",
            "available": shutil.which("cursor-agent") is not None,
            "path": shutil.which("cursor-agent"),
            "full_access_flag": "--full-access",
            "models": ["cursor-fast", "cursor-slow"],
        },
    }

    # Count available providers
    available_count = sum(1 for p in providers.values() if p["available"])

    return {
        "providers": providers,
        "available_count": available_count,
        "total_count": len(providers),
    }


@app.get("/api/cli/providers/{provider}/health")
async def get_cli_provider_health(provider: str):
    """Health check for a specific CLI provider binary.

    Returns basic checks: binary existence, executability, and optional version output.
    """
    import os
    import shutil
    import subprocess

    name_map = {
        "claude": "claude",
        "codex": "codex",
        "gemini": "gemini",
        "cursor": "cursor-agent",
    }

    binary = name_map.get(provider, provider)
    path = shutil.which(binary)

    checks = {
        "binaryExists": bool(path),
        "binaryExecutable": bool(path and os.access(path, os.X_OK)),
        "environmentVariables": True,  # Placeholder; provider-specific env validation can be added
        "testExecution": False,
    }

    version = None
    if path:
        # Try a quick version check; ignore failures
        try:
            proc = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=2)
            if proc.returncode == 0:
                checks["testExecution"] = True
                version = (proc.stdout or proc.stderr).strip() or None
        except Exception:
            pass

    return {
        "provider": provider,
        "healthy": all([checks["binaryExists"], checks["binaryExecutable"]]),
        "checks": checks,
        "details": {
            "binaryPath": path,
            "version": version,
        },
    }


@app.get("/api/cli/sessions")
async def list_cli_sessions():
    """List all active CLI sessions"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    sessions = manager.list_sessions()

    return {
        "sessions": [
            {
                "session_id": session.session_id,
                "cli_tool": session.cli_tool,
                "mode": session.mode,
                "state": session.state.value,
                "pid": session.pid,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "authentication_required": session.authentication_required,
                "current_directory": session.current_directory,
                "websocket_url": f"/ws/cli/{session.session_id}",
            }
            for session in sessions
        ]
    }


@app.get("/api/cli/sessions/{session_id}")
async def get_cli_session_info(session_id: str):
    """Get information about a specific CLI session"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    session = manager.get_session_info(session_id)

    if not session:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="CLI session not found")

    return {
        "session_id": session.session_id,
        "cli_tool": session.cli_tool,
        "mode": session.mode,
        "state": session.state.value,
        "pid": session.pid,
        "created_at": session.created_at,
        "last_activity": session.last_activity,
        "authentication_required": session.authentication_required,
        "auth_prompt": session.auth_prompt,
        "current_directory": session.current_directory,
        "command_history": session.command_history[-10:],  # Last 10 commands
        "websocket_url": f"/ws/cli/{session.session_id}",
    }


@app.post("/api/cli/sessions/{session_id}/terminate")
async def terminate_cli_session(session_id: str):
    """Terminate a CLI session"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    success = await manager.terminate_session(session_id)

    if not success:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="CLI session not found or already terminated")

    return {"message": "CLI session terminated successfully"}


@app.delete("/api/cli/sessions/{session_id}")
async def terminate_cli_session(session_id: str):
    """Terminate a CLI session"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    success = await manager.terminate_session(session_id)

    if success:
        return {"message": "Session terminated successfully", "session_id": session_id}
    else:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Session not found")


@app.post("/api/cli/sessions/{session_id}/input")
async def send_cli_input(session_id: str, request: dict):
    """Send input to a CLI session (alternative to WebSocket)"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    input_text = request.get("input", "")
    manager = get_cli_session_manager()

    success = await manager.send_input_to_session(session_id, input_text)

    if not success:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="CLI session not found or not running")

    return {"message": "Input sent successfully"}


@app.post("/api/cli/sessions/{session_id}/interrupt")
async def interrupt_cli_session(session_id: str):
    """Send interrupt (Ctrl+C) to a CLI session"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    success = await manager.interrupt_session(session_id)

    if not success:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="CLI session not found or not running")

    return {"success": True, "message": "Interrupt signal sent"}


@app.get("/api/cli/sessions/{session_id}/history")
async def get_cli_session_history(session_id: str, limit: int = 100, message_type: str = None):
    """Get session message history from persistence"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    messages = manager.get_session_history(session_id, limit, message_type)

    return {
        "session_id": session_id,
        "messages": [
            {
                "type": msg.type,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "direction": msg.direction,
                "metadata": msg.metadata,
            }
            for msg in messages
        ],
    }


@app.get("/api/cli/sessions/{session_id}/persistent")
async def get_cli_session_persistent_data(session_id: str):
    """Get persistent session data from Redis"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    session = manager.get_persistent_session(session_id)

    if not session:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Session not found in persistence")

    return {
        "id": session.id,
        "provider": session.provider,
        "user_id": session.user_id,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat(),
        "status": session.status.value,
        "working_directory": session.working_directory,
        "error_count": session.error_count,
        "command_count": session.command_count,
        "metadata": session.metadata,
    }


@app.get("/api/cli/sessions/metrics")
async def get_cli_session_metrics():
    """Get comprehensive CLI session metrics"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    metrics = manager.get_session_metrics()

    return metrics


@app.post("/api/cli/sessions/recover")
async def recover_cli_sessions():
    """Recover interrupted CLI sessions from persistence"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    recovered_session_ids = await manager.recover_sessions()

    return {
        "message": f"Recovered {len(recovered_session_ids)} sessions",
        "recovered_sessions": recovered_session_ids,
    }


@app.get("/api/cli/auth/health")
async def check_claude_auth_health():
    """Check Claude authentication health and status"""
    import json
    import os
    import time
    from pathlib import Path

    health_status = {
        "claude": {
            "authenticated": False,
            "credentials_exist": False,
            "token_valid": False,
            "credentials_path": None,
            "token_expires_at": None,
            "details": {},
        }
    }

    # Check Claude credentials
    claude_creds_path = Path.home() / ".claude" / ".credentials.json"
    health_status["claude"]["credentials_path"] = str(claude_creds_path)

    if claude_creds_path.exists():
        health_status["claude"]["credentials_exist"] = True
        try:
            with open(claude_creds_path) as f:
                credentials = json.load(f)

            # Check OAuth token
            oauth_data = credentials.get("claudeAiOauth", {})
            access_token = oauth_data.get("accessToken")
            expires_at = oauth_data.get("expiresAt", 0)

            if access_token:
                # Check if token is valid (not expired)
                current_time_ms = time.time() * 1000
                if expires_at > current_time_ms:
                    health_status["claude"]["authenticated"] = True
                    health_status["claude"]["token_valid"] = True
                    health_status["claude"]["token_expires_at"] = expires_at

                    # Calculate time until expiration
                    time_until_expiry = (expires_at - current_time_ms) / 1000 / 60  # minutes
                    health_status["claude"]["details"]["time_until_expiry_minutes"] = round(
                        time_until_expiry, 2
                    )
                else:
                    health_status["claude"]["details"]["error"] = "Token expired"
            else:
                health_status["claude"]["details"]["error"] = "No access token found"

        except Exception as e:
            health_status["claude"]["details"]["error"] = f"Failed to read credentials: {e!s}"
    else:
        health_status["claude"]["details"]["error"] = "Credentials file not found"

    # Check if Claude binary exists
    claude_path = os.popen("which claude").read().strip()
    health_status["claude"]["binary_exists"] = bool(claude_path)
    health_status["claude"]["binary_path"] = claude_path if claude_path else None

    # Overall health status
    health_status["healthy"] = (
        health_status["claude"]["authenticated"] and health_status["claude"]["binary_exists"]
    )

    # Recommendations
    recommendations = []
    if not health_status["claude"]["credentials_exist"]:
        recommendations.append("Run 'claude auth login' to authenticate")
    elif not health_status["claude"]["token_valid"]:
        recommendations.append("Token expired. Run 'claude auth login' to refresh")
    elif not health_status["claude"]["binary_exists"]:
        recommendations.append("Claude CLI not found. Install it first")

    health_status["recommendations"] = recommendations

    return health_status


@app.post("/api/cli/sessions/cleanup")
async def cleanup_cli_sessions():
    """Cleanup expired and inactive CLI sessions"""
    from orchestrator.cli_session_manager import get_cli_session_manager

    manager = get_cli_session_manager()
    await manager.cleanup_inactive_sessions()

    return {"message": "Session cleanup completed"}


async def broadcast_update(message: dict):
    """Broadcast updates to all connected dashboard clients"""
    if connected_clients:
        disconnected = []
        for client in connected_clients:
            try:
                await client.send_text(json.dumps(message))
            except Exception:
                disconnected.append(client)

        # Clean up disconnected clients
        for client in disconnected:
            connected_clients.remove(client)


# Authentication endpoints for CLI WebSocket integration
@app.post("/api/auth/login")
async def login_for_cli_access(credentials: dict):
    """Login endpoint for CLI WebSocket authentication"""
    from fastapi import HTTPException

    from orchestrator.auth import authenticate_user, create_access_token

    username = credentials.get("username", "")
    password = credentials.get("password", "")
    session_id = credentials.get("session_id")

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username and password required"
        )

    user_info = authenticate_user(username, password)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
        )

    # Generate access token
    token = create_access_token(user_info, session_id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_info": {
            "username": user_info["username"],
            "full_access": user_info["full_access"],
            "roles": user_info["roles"],
        },
        "expires_hours": 24,
    }


@app.post("/api/auth/verify")
async def verify_token_endpoint(token_data: dict):
    """Verify a JWT token"""
    from fastapi import HTTPException

    from orchestrator.auth import verify_token

    token = token_data.get("token", "")
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token required")

    user_info = verify_token(token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    return {
        "valid": True,
        "user_info": {
            "username": user_info["username"],
            "full_access": user_info["full_access"],
            "roles": user_info["roles"],
            "session_id": user_info.get("session_id"),
        },
    }


@app.post("/api/auth/revoke")
async def revoke_token_endpoint(token_data: dict):
    """Revoke a JWT token"""
    from fastapi import HTTPException

    from orchestrator.auth import get_auth_manager

    token = token_data.get("token", "")
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token required")

    auth_manager = get_auth_manager()
    success = auth_manager.revoke_token(token)

    return {
        "revoked": success,
        "message": "Token revoked successfully"
        if success
        else "Token not found or already revoked",
    }


@app.get("/api/auth/sessions")
async def get_active_auth_sessions():
    """Get active authentication sessions"""
    from orchestrator.auth import get_auth_manager

    auth_manager = get_auth_manager()
    sessions = auth_manager.get_active_sessions()

    # Also get WebSocket connection info
    from orchestrator.cli_websocket import get_cli_websocket_handler

    ws_handler = get_cli_websocket_handler()
    active_connections = ws_handler.get_active_connections()

    return {
        "auth_sessions": sessions,
        "websocket_connections": active_connections,
        "summary": {
            "total_users": len(sessions),
            "total_tokens": sum(len(tokens) for tokens in sessions.values()),
            "active_websocket_connections": len(active_connections),
        },
    }


@app.get("/api/websocket/metrics")
async def get_websocket_metrics():
    """Get WebSocket handler metrics and statistics"""
    from orchestrator.cli_websocket import get_cli_websocket_handler

    ws_handler = get_cli_websocket_handler()
    return ws_handler.get_handler_metrics()


@app.get("/api/websocket/connections")
async def get_websocket_connections():
    """Get detailed information about active WebSocket connections"""
    from orchestrator.cli_websocket import get_cli_websocket_handler

    ws_handler = get_cli_websocket_handler()
    connections = ws_handler.get_active_connections()

    return {
        "connections": connections,
        "total_active": len(connections),
        "by_session": {
            session_id: [
                conn_id for conn_id, conn in connections.items() if conn["session_id"] == session_id
            ]
            for session_id in set(conn["session_id"] for conn in connections.values())
        },
    }


# Task Persistence and History API Endpoints
@app.get("/api/tasks/history/{task_id}")
async def get_task_history(task_id: str):
    """Get complete history for a specific task"""
    from fastapi import HTTPException

    from orchestrator.persistence import get_persistence_manager

    try:
        persistence_manager = get_persistence_manager()
        history = persistence_manager.get_task_history(task_id)

        if not history:
            raise HTTPException(status_code=404, detail="Task history not found")

        return {
            "task_id": task_id,
            "history": [
                {
                    "id": record.id,
                    "state_from": record.state_from.value if record.state_from else None,
                    "state_to": record.state_to.value,
                    "timestamp": record.timestamp.isoformat(),
                    "provider": record.provider,
                    "model": record.model,
                    "error_message": record.error_message,
                    "details": record.details,
                    "user_id": record.user_id,
                }
                for record in history
            ],
            "total_entries": len(history),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task history: {e!s}")


@app.get("/api/tasks/persistent")
async def get_persistent_tasks():
    """Get all tasks from persistent storage with filtering"""

    from fastapi import Query

    from orchestrator.persistence import get_persistence_manager
    from orchestrator.persistence_models import TaskSearchFilter, TaskState

    # Parse query parameters
    states = Query(None)
    roles = Query(None)
    providers = Query(None)
    search = Query(None)
    limit = Query(100)
    offset = Query(0)

    try:
        persistence_manager = get_persistence_manager()

        # Build filter criteria
        filter_criteria = TaskSearchFilter(
            states=[TaskState(s) for s in states] if states else None,
            roles=roles.split(",") if roles else None,
            providers=providers.split(",") if providers else None,
            search_text=search,
            limit=limit,
            offset=offset,
        )

        tasks = persistence_manager.get_all_tasks(filter_criteria)

        return {
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "role": task.role,
                    "state": task.state.value,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat(),
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "provider": task.provider,
                    "model": task.model,
                    "branch": task.branch,
                    "commit_hash": task.commit_hash,
                    "last_error": task.last_error,
                    "error_count": task.error_count,
                    "full_access": task.full_access,
                    "target_dir": task.target_dir,
                }
                for task in tasks
            ],
            "total_results": len(tasks),
            "filter_applied": {
                "states": states,
                "roles": roles,
                "providers": providers,
                "search": search,
                "limit": limit,
                "offset": offset,
            },
        }
    except Exception as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=f"Failed to get persistent tasks: {e!s}")


@app.get("/api/tasks/outputs/{task_id}")
async def get_task_outputs(task_id: str):
    """Get all outputs and artifacts for a specific task"""
    from fastapi import HTTPException

    from orchestrator.persistence import get_persistence_manager

    try:
        persistence_manager = get_persistence_manager()
        outputs = persistence_manager.get_task_outputs(task_id)

        return {
            "task_id": task_id,
            "outputs": [
                {
                    "id": output.id,
                    "output_type": output.output_type.value,
                    "content": output.content,
                    "timestamp": output.timestamp.isoformat(),
                    "file_path": output.file_path,
                    "file_size": output.file_size,
                    "mime_type": output.mime_type,
                    "commit_hash": output.commit_hash,
                    "branch": output.branch,
                }
                for output in outputs
            ],
            "total_outputs": len(outputs),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task outputs: {e!s}")


@app.post("/api/tasks/outputs/{task_id}")
async def add_task_output(task_id: str, output_data: dict):
    """Add output/artifact for a specific task"""
    from fastapi import HTTPException

    from orchestrator.persistence import get_persistence_manager
    from orchestrator.persistence_models import OutputType

    try:
        persistence_manager = get_persistence_manager()

        # Validate output type
        output_type_str = output_data.get("output_type", "log")
        try:
            output_type = OutputType(output_type_str)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid output type: {output_type_str}")

        content = output_data.get("content", "")
        file_path = output_data.get("file_path")
        commit_hash = output_data.get("commit_hash")
        branch = output_data.get("branch")

        persistence_manager.add_task_output(
            task_id, output_type, content, file_path, commit_hash, branch
        )

        return {"message": "Task output added successfully", "task_id": task_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add task output: {e!s}")


@app.get("/api/persistence/stats")
async def get_persistence_stats():
    """Get database and persistence statistics"""
    from fastapi import HTTPException

    from orchestrator.persistence import get_persistence_manager

    try:
        persistence_manager = get_persistence_manager()
        stats = persistence_manager.get_persistence_stats()

        return {
            "total_tasks": stats.total_tasks,
            "tasks_by_state": stats.tasks_by_state,
            "tasks_by_role": stats.tasks_by_role,
            "active_cli_sessions": stats.active_cli_sessions,
            "database_size_mb": round(stats.database_size_mb, 2),
            "oldest_task_date": stats.oldest_task_date.isoformat()
            if stats.oldest_task_date
            else None,
            "newest_task_date": stats.newest_task_date.isoformat()
            if stats.newest_task_date
            else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get persistence stats: {e!s}")


@app.post("/api/tasks/{task_id}/recover")
async def recover_task(task_id: str):
    """Recover task from persistent storage to Redis"""
    from fastapi import HTTPException

    from orchestrator.models import TaskStatus
    from orchestrator.persistence import get_persistence_manager
    from orchestrator.queue import _redis

    try:
        persistence_manager = get_persistence_manager()
        task_record = persistence_manager.get_task(task_id)

        if not task_record:
            raise HTTPException(status_code=404, detail="Task not found in persistent storage")

        # Create TaskStatus for Redis
        task_status = TaskStatus(
            id=task_record.id,
            role=task_record.role,
            branch=task_record.branch or f"auto/{task_record.role}/{task_record.id}",
            state=task_record.state.value.replace("passed", "passed").replace("failed", "failed"),
            last_error=task_record.last_error,
            provider=task_record.provider,
            model=task_record.model,
        )

        # Store in Redis
        key = f"task_status:{task_id}"
        _redis.setex(key, 86400, task_status.json())

        return {
            "message": "Task recovered successfully",
            "task_id": task_id,
            "restored_state": task_record.state.value,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recover task: {e!s}")


# Merge coordinator endpoints (lazy loaded to avoid circular imports)
@app.post("/merge/queue")
async def add_to_merge_queue(pr_id: str, branch: str, priority: str = "feature"):
    """Add PR to merge queue"""
    from gitops.merge_coordinator import MergePriority, get_merge_coordinator

    merge_coordinator = get_merge_coordinator()

    priority_map = {
        "security": MergePriority.SECURITY,
        "bug": MergePriority.BUG,
        "feature": MergePriority.FEATURE,
        "docs": MergePriority.DOCS,
    }
    priority_enum = priority_map.get(priority.lower(), MergePriority.FEATURE)
    result = await merge_coordinator.add_to_queue(pr_id, branch, priority_enum)
    return {"message": result}


@app.post("/merge/process")
async def process_merge_queue():
    """Process next item in merge queue"""
    from gitops.merge_coordinator import get_merge_coordinator

    merge_coordinator = get_merge_coordinator()

    result = await merge_coordinator.process_merge_queue()
    await broadcast_update({"type": "merge_queue_update", "data": result})
    return result


@app.get("/merge/status")
async def get_merge_status():
    """Get current merge queue status"""
    from gitops.merge_coordinator import get_merge_coordinator

    merge_coordinator = get_merge_coordinator()

    return merge_coordinator.get_queue_status()


@app.post("/merge/rebase-all")
async def rebase_all_branches():
    """Trigger rebase of all pending PRs"""
    from gitops.merge_coordinator import get_merge_coordinator

    merge_coordinator = get_merge_coordinator()

    await merge_coordinator.rebase_pending_prs()
    return {"message": "Rebase triggered for all pending PRs"}
