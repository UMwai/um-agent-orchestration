# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## NEW SIMPLIFIED SYSTEM (Current)

### Quick Start
```bash
# Install minimal dependencies
pip install click pyyaml

# Method 1: Submit individual tasks manually
./orchestrate submit "Fix authentication bug" --agent claude --priority high
./orchestrate submit "Update UI components" --agent codex --priority normal

# Method 2: Submit high-level task with automatic decomposition (RECOMMENDED)
./orchestrate submit "Build a todo app with authentication" --decompose

# Run the orchestrator (spawns multiple agents)
./orchestrate run --max-agents 3

# Check status
./orchestrate status

# View specific task
./orchestrate task <task-id>

# Run demo
./orchestrate demo
```

### Architecture Overview

**Simplified Agent Orchestrator** - A lightweight system for managing multiple CLI agents:

- **TaskQueue** (`src/core/task_queue.py`): SQLite-based task management
- **AgentSpawner** (`src/core/agent_spawner.py`): Direct subprocess spawning
- **ContextManager** (`src/core/context_manager.py`): File-based context sharing
- **TaskDecomposer** (`src/core/task_decomposer.py`): Intelligent task breakdown using Claude
- **CLI Interface** (`src/cli/orchestrate.py`): Simple command-line interface with `--decompose` flag

### Key Design Principles
- **Simplicity First**: ~500 lines of code total
- **No External Services**: SQLite only, no Redis/RQ/monitoring stack
- **Direct CLI Execution**: Spawns `claude` and `codex` as subprocesses
- **File-Based IPC**: Context sharing via `/tmp/agent_orchestrator/`
- **CLI-Only Interface**: No web UI by design

### How It Works
1. Submit tasks via `./orchestrate submit`
2. Tasks stored in SQLite database
3. Run orchestrator with `./orchestrate run`
4. Orchestrator spawns claude/codex CLI processes
5. Agents work on tasks in parallel
6. Results saved to filesystem
7. Context shared between agents via files

### Development Commands

```bash
# Core operations
./orchestrate submit "task description"  # Add task
./orchestrate run                       # Process tasks
./orchestrate status                    # View queue
./orchestrate agents                    # List active agents
./orchestrate kill <agent-id>          # Kill stuck agent
./orchestrate cleanup                   # Clean old data

# Testing
python src/core/task_queue.py          # Test task queue
python src/core/agent_spawner.py       # Test agent spawning
python src/core/context_manager.py     # Test context sharing
```

### Multi-Agent Patterns

```bash
# Parallel task execution
./orchestrate submit "Backend: Fix auth" --agent claude
./orchestrate submit "Frontend: Update UI" --agent codex
./orchestrate submit "Tests: Add coverage" --agent any
./orchestrate run --max-agents 3

# Monitor progress
watch -n 2 ./orchestrate status
```

### Full Access Mode Testing

```bash
# Test Claude capabilities
claude --dangerously-skip-permissions -p "Analyze this repository"

# Test Codex capabilities  
codex --ask-for-approval never --sandbox danger-full-access exec "Review code"
```

## ARCHIVED SYSTEM (Old - Reference Only)

The previous overcomplicated system has been moved to `archive/current_implementation_2025_01_28/`. It included:

- FastAPI server with Redis queues
- Complex provider routing (8 providers)
- Git worktrees and auto-rebase
- React web dashboard
- Prometheus/Grafana monitoring
- Systemd timers
- ~5000 lines of code

**DO NOT USE THE ARCHIVED SYSTEM** - it has been replaced with the simplified version above.

## File Structure

```
/home/umwai/um-agent-orchestration/
├── orchestrate              # Main CLI entry point
├── src/
│   ├── core/               # Core components (500 lines total)
│   │   ├── task_queue.py   # SQLite task queue
│   │   ├── agent_spawner.py # Subprocess management
│   │   └── context_manager.py # File-based context
│   └── cli/
│       └── orchestrate.py  # CLI commands
├── archive/                 # Old overcomplicated system
├── tasks.db                # SQLite database (auto-created)
└── README.md               # User documentation
```

## Important Notes

- **Simplicity is key**: Resist adding complexity
- **No external services**: SQLite only, no Redis/databases
- **Direct CLI execution**: No session management or PTY complexity
- **File-based IPC**: Simple and reliable
- **CLI-first**: No web UI needed

When working on this codebase:
1. Keep the implementation under 1000 lines total
2. Use only Python standard library + Click
3. Avoid adding new dependencies
4. Prefer simple solutions over clever ones
5. Test with real claude/codex CLI tools