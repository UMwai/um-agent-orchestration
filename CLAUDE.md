# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agent Orchestrator - A lightweight system for managing multiple specialized AI agents working in parallel. Submit high-level tasks that get automatically decomposed and distributed to appropriate specialists for 23x/7 autonomous development.

## Setup and Launch Commands

```bash
# One-command setup and launch (first time)
./quickstart.sh

# Quick launcher with interactive menu after setup
./run.sh

# Direct execution after setup
source venv_orchestrator/bin/activate  # Activate virtual environment
./orchestrate <command>                # Run orchestrator commands
```

## Core Commands

### Planning Commands (Interactive Mode - Recommended)
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

The system consists of ~500 lines of Python code organized around file-based IPC:

- **TaskQueue** (`src/core/task_queue.py`): SQLite-based task management with priority queuing
- **AgentSpawner** (`src/core/agent_spawner.py`): Manages Claude API calls or CLI subprocesses
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
USE_API_MODE=true                       # true for API (recommended), false for CLI
MAX_AGENTS=3                           # Default concurrent agents (can increase to 5-10)
ORCHESTRATOR_BASE_DIR=/tmp/agent_orchestrator  # Working directory for IPC
```

## Testing Components

```bash
# Test individual modules via their __main__ blocks
python src/core/task_queue.py          # Tests SQLite queue operations
python src/core/agent_spawner.py       # Tests agent spawning
python src/core/context_manager.py     # Tests file-based IPC
python src/core/task_decomposer.py     # Tests task decomposition
python src/core/interactive_planner.py # Tests planning session

# Integration tests
python scripts/test-full-access.py     # Full system test
python test_interactive_planning.py    # Planning workflow test

# No formal test framework - modules self-test via __main__
# No linting/type checking configured - focus on functionality
```

## Development Workflows

### Interactive Planning Mode (Recommended for Complex Tasks)
1. Start planning: `./orchestrate plan "Your goal"`
2. Interactive commands in session:
   - `d` - Discuss approach with Claude
   - `a` - Add new task
   - `m` - Modify existing task
   - `s` - Split task into subtasks
   - `r` - Remove task
   - `v` - View current plan
   - `p` - Proceed to approval
3. Review and approve plan
4. Execution starts automatically after approval

### Direct Submission Mode (Quick Tasks)
1. Submit with decomposition: `./orchestrate submit "Task" --decompose`
2. Run orchestrator: `./orchestrate run --max-agents 3`
3. Monitor progress: `./orchestrate status`

### Working Directory
Agents operate in the current directory where you run the orchestrator:
- Full read/write access to project files
- Results written directly to your codebase
- Context shared via `/tmp/agent_orchestrator/`

## Database Schema

Tasks table in `tasks.db`:
- `id`: Unique task identifier
- `description`: Task description
- `agent_type`: Target agent type
- `status`: pending/assigned/in_progress/completed/failed
- `priority`: high(1)/normal(2)/low(3)
- `context`: JSON metadata
- `created_at`, `assigned_at`, `completed_at`: Timestamps
- `assigned_to`: Agent ID
- `output`, `error`: Execution results

## Important Implementation Notes

- **Keep it simple**: Target ~500 lines total, currently well under 1000
- **SQLite only**: No Redis, PostgreSQL, or external databases
- **File-based IPC**: Communication via JSON files in `/tmp/agent_orchestrator/`
- **No complex dependencies**: Just Click, SQLite, and standard library
- **Archive directory**: `archive/current_implementation_2025_01_28/` contains old overcomplicated version - do not use
- **Testing approach**: Direct module execution via `__main__` blocks
- **API vs CLI mode**: API mode (USE_API_MODE=true) recommended for reliability