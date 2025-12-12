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

## 📦 Install As CLI (for use in any repo)

If you want to call the orchestrator from other projects, install it once in editable mode:

```bash
cd /path/to/um-agent-orchestration
python3 -m pip install -e .
```

Then in any repo:

```bash
cd /path/to/other/repo
orchestrate plan "Your high-level goal"
orchestrate run --max-agents 3
```

### Tool-Friendly (Non-interactive) Usage
For automation/tool-calling flows, prefer non-interactive commands:

```bash
# Decompose into subtasks without interactive planning
orchestrate submit "Implement xyz..." --decompose
orchestrate run --max-agents 3
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

## 📚 Real-World Usage Examples

### Example 1: Building a Complete Web Application
```bash
# Monday morning: Plan the project interactively
./orchestrate plan "Build a task management app with React frontend and FastAPI backend"

# Interactive session:
> Discussing approach...
> Claude: I'll help you build this. Let me break it down into phases:
>   Phase 1: Database design and API structure
>   Phase 2: Backend implementation
>   Phase 3: Frontend development
>   Phase 4: Integration and testing
>
> [a] Add task: "Set up PostgreSQL database with user and task tables"
> [a] Add task: "Create FastAPI CRUD endpoints for tasks"
> [a] Add task: "Build React components for task list and forms"
> [s] Split task: Breaking down frontend into smaller components...
> [p] Proceed to approval

# Monday afternoon: Start execution with 3 parallel agents
./orchestrate run --max-agents 3

# Tuesday morning: Check progress
./orchestrate status
# Output:
# ✅ Completed: Database schema design (specifications-engineer)
# ✅ Completed: FastAPI backend setup (backend-systems-engineer)
# 🔄 In Progress: React frontend components (frontend-ui-engineer)
# ⏳ Pending: Integration tests
# ⏳ Pending: Documentation
```

### Example 2: Data Pipeline Development
```bash
# Submit a complex ETL pipeline task
./orchestrate submit "Create an ETL pipeline to process daily sales data from S3 to Snowflake" --decompose

# Automatically creates specialized subtasks:
# - [data-architect-governance]: Design data model and governance policies
# - [data-pipeline-engineer]: Build Apache Spark job for transformation
# - [aws-cloud-architect]: Set up S3 events and Lambda triggers
# - [data-pipeline-engineer]: Create Airflow DAG for orchestration
# - [data-science-analyst]: Build data quality validation checks

# Run overnight with higher parallelism
./orchestrate run --max-agents 5

# Next morning: Review completed work
./orchestrate status
ls -la pipelines/     # See generated code
cat pipelines/sales_etl.py
```

### Example 3: Machine Learning System
```bash
# Interactive planning for ML project
./orchestrate plan "Build a customer churn prediction system"

# Let agents work on different aspects simultaneously
./orchestrate execute-plan ml-project-001

# While agents work, monitor specific tasks
./orchestrate task churn-model-training
./orchestrate agents  # See which specialists are active

# Output shows parallel execution:
# 🤖 Active Agents:
# - ml-systems-architect: Designing feature engineering pipeline
# - data-science-analyst: Performing EDA and statistical analysis
# - backend-systems-engineer: Building model serving API
```

### Example 4: Microservices Architecture
```bash
# Submit comprehensive microservices project
./orchestrate submit "Convert monolithic app to microservices with user, order, and payment services" -d

# Monitor phase-based execution
watch -n 10 './orchestrate status'

# Agents work in coordinated phases:
# Phase 1: All architecture design tasks (parallel)
# Phase 2: Service implementation (parallel)
# Phase 3: Integration and API gateway (sequential)
# Phase 4: Testing and documentation (parallel)
```

### Example 5: Quick Feature Addition
```bash
# For smaller tasks, direct submission works great
./orchestrate submit "Add OAuth2 authentication to existing Flask app" --agent backend-systems-engineer --priority high

# Run single agent for focused task
./orchestrate run --max-agents 1
```

### Example 6: Overnight Development Session
```bash
# Before leaving work on Friday
./orchestrate plan "Implement complete admin dashboard with user management, analytics, and reporting"

# Approve plan and let it run over weekend
./orchestrate execute-plan dashboard-project

# Set up aggressive parallelism for weekend run
./orchestrate run --max-agents 8

# Monday morning: Review all completed work
./orchestrate status
git diff  # See all changes made
```

## 🎯 Common Workflows

### Daily Development Workflow
```bash
# Morning: Check overnight progress
./orchestrate status
./orchestrate agents

# Review completed tasks
git diff HEAD~1

# Submit new tasks based on progress
./orchestrate submit "Fix bugs found in overnight testing" --priority high

# Continue processing
./orchestrate run
```

### Sprint Planning Workflow
```bash
# Start planning session with team requirements
./orchestrate plan "Sprint 23 goals: API v2, mobile responsive UI, performance optimization"

# Add all sprint tasks interactively
# Agents will work on them throughout the sprint

# Daily standup: Check progress
./orchestrate status | grep "In Progress"
```

### Emergency Hotfix Workflow
```bash
# High-priority production fix
./orchestrate submit "URGENT: Fix memory leak in payment processing service" \
  --agent backend-systems-engineer \
  --priority high

# Run with dedicated agent
./orchestrate run --max-agents 1

# Monitor until complete
watch './orchestrate task payment-leak-fix'
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
