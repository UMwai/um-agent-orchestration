# Quick Start Guide

Get up and running with the Simplified Agent Orchestrator in 2 minutes.

## Prerequisites

- Python 3.8+
- `claude` CLI tool installed
- `codex` CLI tool installed

## Installation

```bash
# Clone the repo (if needed)
git clone <your-repo-url>
cd um-agent-orchestration

# Install minimal dependencies
pip install click pyyaml

# Make the orchestrator executable
chmod +x orchestrate
```

## Basic Usage

### 1. Submit Tasks

#### Option A: Submit Individual Tasks
```bash
# Submit a high-priority task for Claude
./orchestrate submit "Fix the authentication bug in login.py" --agent claude --priority high

# Submit a task for Codex
./orchestrate submit "Update the React components to use hooks" --agent codex

# Submit a task for any available agent
./orchestrate submit "Write unit tests for the API endpoints" --agent any
```

#### Option B: Submit High-Level Task with Auto-Decomposition (NEW!)
```bash
# Let the system break down complex tasks automatically
./orchestrate submit "Build a REST API for user management" --decompose

# This will create subtasks like:
# - Design API endpoints and data structures (claude)
# - Implement API handlers (codex)
# - Add authentication/authorization (codex)
# - Write API tests (codex)
```

### 2. Process Tasks

```bash
# Run the orchestrator with up to 3 parallel agents
./orchestrate run --max-agents 3
```

The orchestrator will:
- Spawn claude/codex CLI processes
- Assign tasks to appropriate agents
- Run agents in parallel
- Save results to `/tmp/agent_orchestrator/`

### 3. Monitor Progress

```bash
# Check overall status
./orchestrate status

# View specific task details
./orchestrate task <task-id>

# List active agents
./orchestrate agents
```

## Example Workflows

### Workflow 1: Manual Task Management
```bash
# Submit individual subtasks
./orchestrate submit "Backend: Fix user authentication" --agent claude --priority high
./orchestrate submit "Frontend: Add dark mode toggle" --agent codex --priority normal
./orchestrate submit "Tests: Add integration tests" --agent any --priority low

# Check queue and run
./orchestrate status
./orchestrate run --max-agents 2
```

### Workflow 2: Automatic Decomposition (Recommended)
```bash
# Step 1: Submit high-level task
./orchestrate submit "Build a blog platform with comments and user accounts" --decompose

# Step 2: System automatically creates subtasks:
# ✅ Design the data model and architecture (claude)
# ✅ Implement the backend/API (codex)
# ✅ Create the frontend/UI (codex)
# ✅ Write tests (codex)
# ✅ Create documentation (claude)

# Step 3: Run orchestrator with multiple agents
./orchestrate run --max-agents 3

# Step 4: Monitor in another terminal
watch -n 2 ./orchestrate status
```

## Demo Mode

Try the system with built-in demo tasks:

```bash
./orchestrate demo
```

This will:
1. Submit 3 sample tasks
2. Process them with 2 agents
3. Show the results

## Troubleshooting

### Agent Not Found
If you get "claude: command not found":
```bash
# Make sure claude CLI is installed
which claude

# If not installed, install it:
# Follow instructions at https://claude.ai/code
```

### Task Stuck
If a task is stuck:
```bash
# List agents
./orchestrate agents

# Kill stuck agent
./orchestrate kill <agent-id>
```

### Clean Up
Remove old tasks and temporary files:
```bash
./orchestrate cleanup
```

## CLI Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `submit` | Add task to queue | `./orchestrate submit "Fix bug" --agent claude` |
| `run` | Process queued tasks | `./orchestrate run --max-agents 3` |
| `status` | Show queue status | `./orchestrate status` |
| `task` | View task details | `./orchestrate task abc123` |
| `agents` | List active agents | `./orchestrate agents` |
| `kill` | Terminate agent | `./orchestrate kill claude-abc123` |
| `cleanup` | Remove old data | `./orchestrate cleanup` |
| `demo` | Run demo tasks | `./orchestrate demo` |

## How It Works

1. **Task Queue**: Tasks stored in SQLite (`tasks.db`)
2. **Agent Spawning**: Direct subprocess execution of CLI tools
3. **Context Sharing**: Files in `/tmp/agent_orchestrator/`
4. **No External Services**: No Redis, no web server, just Python

## Next Steps

- Read the [README](README.md) for detailed documentation
- Check [CLAUDE.md](CLAUDE.md) for development guidelines
- Explore the source code in `src/core/`

## Support

For issues or questions:
1. Check the README
2. Run `./orchestrate --help`
3. Review the source code (it's only ~500 lines!)