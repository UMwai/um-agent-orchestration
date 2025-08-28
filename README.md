# Simplified Agent Orchestrator

A lightweight, local orchestration system for managing multiple CLI agents (claude-code and codex-cli).

## Overview

This is a **dramatically simplified** rewrite of the original overcomplicated system. The entire implementation is now **~500 lines** instead of ~5000 lines.

### Key Features
- 🎯 **Simple task queue** using SQLite (no Redis required)
- 🤖 **Direct CLI spawning** of codex and claude agents
- 📁 **File-based IPC** for context sharing (no WebSockets)
- 🖥️ **CLI-first interface** (no complex web UI)
- 🚀 **Parallel execution** with configurable agent limits

## Quick Start

```bash
# Install minimal dependencies
pip install click pyyaml

# Method 1: Submit individual tasks
./orchestrate submit "Fix the authentication bug" --agent claude --priority high

# Method 2: Submit high-level task with automatic decomposition
./orchestrate submit "Build a todo app with authentication" --decompose

# Run the orchestrator (processes all queued tasks)
./orchestrate run --max-agents 3

# Check status
./orchestrate status

# View specific task
./orchestrate task <task-id>
```

## Architecture

```
orchestrate (CLI)
    ↓
TaskQueue (SQLite)
    ↓
AgentSpawner → spawns → claude/codex CLI processes
    ↓
ContextManager (file-based sharing in /tmp/)
```

## Core Components

### 1. TaskQueue (`src/core/task_queue.py`)
- Simple SQLite database for task management
- FIFO with priority levels (HIGH, NORMAL, LOW)
- No external dependencies

### 2. AgentSpawner (`src/core/agent_spawner.py`)
- Direct `subprocess.Popen()` for CLI processes
- Supports claude with `--dangerously-skip-permissions`
- Supports codex with `--sandbox danger-full-access`

### 3. ContextManager (`src/core/context_manager.py`)
- File-based context sharing in `/tmp/agent_orchestrator/`
- JSON files for inter-agent communication
- No complex IPC or WebSockets

### 4. TaskDecomposer (`src/core/task_decomposer.py`) - **NEW!**
- Breaks high-level tasks into subtasks
- Uses Claude for intelligent decomposition
- Falls back to heuristic patterns
- Creates execution phases

### 5. CLI Interface (`src/cli/orchestrate.py`)
- Simple Click-based CLI
- Commands: submit, run, status, task, agents, kill, cleanup
- **NEW**: `--decompose` flag for automatic task breakdown

## Usage Examples

### Method 1: Manual Task Breakdown
```bash
# Submit individual subtasks manually
./orchestrate submit "Design database schema" --agent claude
./orchestrate submit "Implement API endpoints" --agent codex
./orchestrate submit "Create frontend UI" --agent codex

# Run orchestrator to process all tasks
./orchestrate run --max-agents 3
```

### Method 2: Automatic Task Decomposition (NEW!)
```bash
# Submit high-level task with automatic breakdown
./orchestrate submit "Build a blog platform with comments" --decompose

# This automatically creates subtasks like:
# 1. [claude] Design the data model and architecture
# 2. [codex] Implement the backend/API
# 3. [codex] Create the frontend/UI
# 4. [codex] Write tests
# 5. [claude] Create documentation

# Then run the orchestrator
./orchestrate run --max-agents 3
```

### Monitor Progress
```bash
# Check overall status
./orchestrate status

# View specific task details
./orchestrate task abc123

# List active agents
./orchestrate agents

# Kill a stuck agent
./orchestrate kill claude-abc123
```

### Demo Mode
```bash
# Run a demo with sample tasks
./orchestrate demo
```

## File Structure
```
/home/umwai/um-agent-orchestration/
├── orchestrate              # Main CLI entry point
├── src/
│   ├── core/
│   │   ├── task_queue.py   # SQLite task queue
│   │   ├── agent_spawner.py # Subprocess management
│   │   └── context_manager.py # File-based context
│   └── cli/
│       └── orchestrate.py  # CLI commands
├── archive/                 # Old overcomplicated system
└── tasks.db                # SQLite database (auto-created)
```

## Why Simplified?

The original implementation had:
- ❌ Redis + RQ workers
- ❌ Complex provider routing (8 providers)
- ❌ Git worktrees and auto-rebase
- ❌ Full React dashboard
- ❌ Systemd timers
- ❌ Monitoring stack
- ❌ ~5000 lines of code

This simplified version has:
- ✅ SQLite only
- ✅ Direct CLI execution
- ✅ File-based IPC
- ✅ CLI-only interface
- ✅ ~500 lines of code
- ✅ Zero external services

## Requirements

- Python 3.8+
- `claude` CLI installed
- `codex` CLI installed
- Click library (`pip install click`)

## Limitations

- No web UI (by design)
- No persistent agent sessions
- No complex task dependencies
- No git integration
- Basic round-robin task distribution

## Future Enhancements (if needed)

- Terminal UI (TUI) for better visualization
- Task dependencies and DAGs
- Agent specialization and routing
- Performance metrics
- WebSocket monitoring (optional)

## License

MIT