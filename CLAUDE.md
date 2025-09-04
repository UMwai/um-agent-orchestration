# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agent Orchestrator - A lightweight system for managing multiple specialized AI agents working in parallel. Submit high-level tasks that get automatically decomposed and distributed to appropriate specialists for 23x/7 autonomous development.

## Launch Commands

```bash
# One-command setup and launch (first time)
./quickstart.sh

# Quick launcher with interactive menu
./run.sh

# Direct commands after setup
./orchestrate plan "Build a REST API"              # Interactive planning
./orchestrate submit "Task description" --decompose # Submit with decomposition  
./orchestrate run --max-agents 3                   # Process tasks
./orchestrate status                                # Check progress
```

## Core Commands

### Planning Commands (Interactive Mode)
```bash
./orchestrate plan <goal>                  # Start interactive planning session
./orchestrate plan-list                    # View all planning sessions
./orchestrate plan-continue <session-id>   # Resume a planning session
./orchestrate execute-plan <session-id>    # Execute approved plan
```

### Task Management Commands
```bash
./orchestrate submit <task> [options]      # Submit task
  --decompose/-d                           # Auto-decompose into subtasks
  --agent <type>                           # Specify agent type
  --priority high/normal/low               # Set priority
  
./orchestrate run [options]                # Process tasks
  --max-agents N                           # Concurrent agents (default 3)
  
./orchestrate status                       # View queue and agents
./orchestrate task <task-id>              # View specific task
./orchestrate agents                       # List active agents
./orchestrate kill <agent-id>             # Kill stuck agent
./orchestrate cleanup                      # Clean old data
./orchestrate demo                         # Run demo tasks
```

## Core Architecture

The system consists of ~500 lines of Python code:

- **TaskQueue** (`src/core/task_queue.py`): SQLite-based task management with priority queuing
- **AgentSpawner** (`src/core/agent_spawner.py`): Manages Claude CLI subprocesses or API calls
- **TaskDecomposer** (`src/core/task_decomposer.py`): Breaks high-level tasks into specialized subtasks
- **InteractivePlanner** (`src/core/interactive_planner.py`): Head node for interactive planning sessions
- **ContextManager** (`src/core/context_manager.py`): File-based IPC in `/tmp/agent_orchestrator/`
- **CLI Interface** (`src/cli/orchestrate.py`): Click-based commands

## Available Specialized Agents

- `backend-systems-engineer`: APIs, microservices, databases
- `frontend-ui-engineer`: React/Vue/Svelte, UI/UX
- `data-pipeline-engineer`: ETL/ELT, Spark, Airflow
- `aws-cloud-architect`: AWS infrastructure, IaC
- `ml-systems-architect`: ML pipelines, MLOps
- `data-science-analyst`: Data analysis, ML models
- `data-architect-governance`: Data models, governance
- `project-delivery-manager`: Sprint planning, coordination
- `llm-architect`: LLM systems, RAG, prompting
- `specifications-engineer`: Requirements analysis

## Configuration (.env)

```bash
ANTHROPIC_API_KEY=your-api-key          # Required for API mode
USE_API_MODE=true                       # true for API, false for CLI
MAX_AGENTS=3                           # Default concurrent agents
ORCHESTRATOR_BASE_DIR=/tmp/agent_orchestrator  # Working directory
```

## Testing Components

```bash
# Test individual modules
python src/core/task_queue.py
python src/core/agent_spawner.py
python src/core/context_manager.py
python src/core/task_decomposer.py
python src/core/interactive_planner.py

# Integration tests
python scripts/test-full-access.py
python test_interactive_planning.py
```

## Development Workflows

### Interactive Planning Mode (Recommended)
1. Start planning: `./orchestrate plan "Your goal"`
2. In session: discuss (d), add tasks (a), modify (m), split (s)
3. Approve plan (p) when ready
4. Execute: automatically starts after approval

### Direct Submission Mode
1. Submit with decomposition: `./orchestrate submit "Task" --decompose`
2. Run orchestrator: `./orchestrate run`
3. Monitor: `./orchestrate status`

### Working Directory
Agents operate in the current directory where you run the orchestrator with full read/write access.

## Important Notes

- Keep implementation under 1000 lines total
- SQLite only, no external databases
- File-based IPC via `/tmp/agent_orchestrator/`
- Archive at `archive/current_implementation_2025_01_28/` contains old complex system - do not use