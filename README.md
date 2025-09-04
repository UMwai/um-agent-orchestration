# Agent Orchestrator - 23x/7 Autonomous Development System

A lightweight orchestration system that enables continuous development by managing multiple specialized AI agents working in parallel. Submit high-level requirements and let AI agents handle implementation while you sleep.

## 🚀 What Is This?

This system orchestrates multiple Claude agents with specialized roles (backend engineer, frontend developer, data architect, etc.) to work on your projects autonomously. Think of it as having a virtual development team that works 23x/7.

### How It Enables Continuous Development

1. **Submit high-level goals** before leaving work
2. **AI decomposes** them into specialized subtasks  
3. **Multiple agents work in parallel** overnight
4. **Review completed work** the next day
5. **Iterate and refine** based on results

## ⚡ One-Command Launch

```bash
# Complete setup and launch in one command
./quickstart.sh
```

**What this does:**
- ✅ Checks Python 3.8+ requirement
- ✅ Creates virtual environment (if needed)
- ✅ Installs all dependencies
- ✅ Creates/configures .env file
- ✅ Offers to collect your API key
- ✅ Shows launch options with color-coded guidance
- ✅ Optionally starts with a demo

**After setup, you'll see launch options:**

```bash
🚀 Launch Options:
==================

1. Interactive Planning (Recommended)
   ./orchestrate plan "Build a REST API with authentication"

2. Quick Demo
   ./orchestrate demo

3. Direct Task Submission  
   ./orchestrate submit "Create a blog platform" --decompose
   ./orchestrate run

4. View Examples
   cat examples/simple_workflow.sh
```

## 🎯 Key Features

### Specialized Agent Types
The system automatically assigns the right specialist for each task:
- **backend-systems-engineer**: APIs, services, databases
- **frontend-ui-engineer**: UI components, user interfaces
- **data-pipeline-engineer**: ETL, data processing
- **aws-cloud-architect**: Infrastructure, deployment
- **ml-systems-architect**: Machine learning systems
- **data-science-analyst**: Data analysis, visualization
- **specifications-engineer**: Requirements, documentation
- And more...

### Interactive Planning Mode (NEW!)
- **Head node planning** - Discuss and refine plans before execution
- **Interactive refinement** - Add, remove, modify tasks in real-time
- **Dependency visualization** - See execution phases and parallelization
- **Approval workflow** - Review and approve plans before agents start
- **Session persistence** - Save and resume planning sessions

### Intelligent Task Assignment
- Tasks are **automatically routed** to the right specialist based on content
- Agents work in **parallel** (default 3, configurable up to 10+)
- **Context sharing** between agents for coordinated development
- **Priority-based** execution (high/normal/low)

### Working Directory
Agents work in the **current directory** where you run the orchestrator:
- They can read and modify files in your project
- Full access to your codebase (with --dangerously-skip-permissions)
- Results are written directly to your project files

## 📋 Configuration

### Max Agents (Why It Matters)
The `--max-agents` parameter controls parallel execution:
- **Default: 3** - balanced for most systems
- **Can increase to 5-10** for powerful machines
- **Trade-offs**:
  - More agents = faster completion but higher API costs
  - Each agent consumes memory and API rate limits
  - Too many can cause context conflicts

```bash
# Conservative (laptop)
./orchestrate run --max-agents 2

# Standard (default)
./orchestrate run

# Aggressive (powerful workstation)
./orchestrate run --max-agents 8
```

## API vs CLI Mode

The system supports two modes:

1. **API Mode** (Recommended): Uses Claude API directly for agent execution
   - Set `USE_API_MODE=true` in `.env`
   - Requires `ANTHROPIC_API_KEY` in `.env`
   - Supports specialized Claude agents (backend, frontend, data-pipeline, etc.)

2. **CLI Mode**: Spawns local CLI processes (requires claude/codex CLI tools)
   - Set `USE_API_MODE=false` in `.env`
   - Falls back to demo mode if CLIs not installed

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

### 4. TaskDecomposer (`src/core/task_decomposer.py`)
- Breaks high-level tasks into subtasks
- Uses Claude for intelligent decomposition
- Falls back to heuristic patterns
- Creates execution phases

### 5. InteractivePlanner (`src/core/interactive_planner.py`) - **NEW!**
- Head node for interactive planning sessions
- Discuss and refine plans with Claude
- Visualize dependencies and execution phases
- Save/resume planning sessions
- Approval workflow before execution

### 6. CLI Interface (`src/cli/orchestrate.py`)
- Simple Click-based CLI
- Commands: submit, run, status, task, agents, kill, cleanup
- **NEW Planning Commands**: plan, plan-list, plan-continue, execute-plan
- `--decompose` flag for automatic task breakdown

## Usage Examples

### Method 1: Interactive Planning Mode (RECOMMENDED)
```bash
# Start interactive planning session with head node
./orchestrate plan "Build a blog platform with comments"

# In the interactive session you can:
# [d] Discuss approach with Claude
# [a] Add new tasks
# [r] Remove tasks
# [m] Modify tasks
# [s] Split complex tasks
# [p] Proceed to approval

# List and manage planning sessions
./orchestrate plan-list                    # View all sessions
./orchestrate plan-continue <session-id>   # Resume planning
./orchestrate execute-plan <session-id>    # Execute approved plan
```

### Method 2: Automatic Task Decomposition
```bash
# Submit high-level task with automatic breakdown
./orchestrate submit "Build a blog platform with comments" --decompose

# This automatically creates subtasks like:
# 1. [specifications-engineer] Design the data model and architecture
# 2. [backend-systems-engineer] Implement the backend/API
# 3. [frontend-ui-engineer] Create the frontend/UI
# 4. [backend-systems-engineer] Write tests
# 5. [claude] Create documentation

# Then run the orchestrator
./orchestrate run --max-agents 3
```

### Method 3: Manual Task Submission
```bash
# Submit individual subtasks manually
./orchestrate submit "Design database schema" --agent specifications-engineer
./orchestrate submit "Implement API endpoints" --agent backend-systems-engineer
./orchestrate submit "Create frontend UI" --agent frontend-ui-engineer

# Run orchestrator to process all tasks
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