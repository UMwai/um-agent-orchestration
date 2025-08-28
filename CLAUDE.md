# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Core development workflow:**
```bash
# Installation and setup
make install               # Install dependencies and pre-commit hooks
cp .env.example .env      # Configure environment variables

# Development server
make dev                  # Start FastAPI server (localhost:8000)
make run                  # Start Redis server and RQ worker
make workers             # Start additional RQ workers

# Testing and linting
pytest                   # Run test suite
ruff                     # Lint and format code
mypy                     # Type checking  
make precommit          # Run all pre-commit hooks

# Development environment
make tmuxp              # Start tmux development session
make monitoring         # Start Prometheus/Grafana stack

# Git hygiene automation
make enable-timers      # Enable auto-commit (30min) and auto-PR (2h) timers

# Full access mode setup
./scripts/init-full-access.sh  # Interactive setup for full access mode
```

**Single test execution:**
```bash
pytest tests/acceptance/test_sample.py::test_specific_function
```

**Full access mode testing:**
```bash
# Test Claude full access capabilities
claude --dangerously-skip-permissions -p "Analyze this repository structure"

# Test Codex full access capabilities
codex --ask-for-approval never --sandbox danger-full-access exec "Review codebase architecture"
```

**Agent Integration for Task Orchestration:**
```bash
# Launch Claude Code as orchestrating agent in this repo
claude --dangerously-skip-permissions

# Launch Codex as orchestrating agent in this repo  
codex --ask-for-approval never --sandbox danger-full-access

# Alternative Codex commands for specific scenarios:
codex --ask-for-approval never --sandbox danger-full-access exec "Review and implement feature X"
codex --ask-for-approval never --sandbox danger-full-access chat  # Interactive mode
codex --ask-for-approval never --sandbox danger-full-access apply  # Apply changes mode

# In the agent session, load helper functions:
exec(open('scripts/agent_helpers.py').read())

# Submit tasks to the orchestration system:
submit("Fix authentication bug", "Login returns 500 error", "backend")
tasks()  # List all tasks
status("task-id")  # Check specific task
get_metrics()  # System metrics
```

Model Defaults
- OpenAI API default model is configured as `gpt-5`.
- To change it, edit `config/config.yaml` → `providers.openai_api.model`.
- Example:
```yaml
providers:
  openai_api:
    mode: "api"
    provider_type: "api"
    model: "gpt-5"   # ensure GPT-5 is active
```

**Multi-Agent Task Distribution:**
```bash
# Distribute tasks across multiple agents for parallel processing
# See AGENTS.md for comprehensive multi-agent coordination patterns

# Primary orchestrator (for task management and coordination)
claude --dangerously-skip-permissions

# Backend specialist (for API, database, services)
codex --ask-for-approval never --sandbox danger-full-access exec "Handle backend tasks"

# Frontend specialist (for UI, components, styling)  
codex --ask-for-approval never --sandbox danger-full-access exec "Handle frontend tasks"

# Infrastructure specialist (for DevOps, deployment, monitoring)
codex --ask-for-approval never --sandbox danger-full-access exec "Handle infrastructure tasks"

# Testing specialist (for QA, validation, security)
codex --ask-for-approval never --sandbox danger-full-access exec "Handle testing and QA"

# Each agent can load specialized helpers:
exec(open('scripts/agent_helpers.py').read())
load_agent_role('backend')  # Load role-specific configurations

# Multi-agent coordination patterns (see AGENTS.md):
coordinate_agents()  # Orchestrator manages task distribution
distribute_task("feature-name", ["backend", "frontend", "testing"])
monitor_agent_progress()  # Track parallel development
```

## Architecture Overview

**AutoDev** is a multi-agent orchestration system with these key components:

### Core Architecture
- **Orchestrator** (`orchestrator/`): FastAPI server with Redis queue for task management
- **Agents** (`agents/`): Role-based agents (backend, frontend, data, ml) with generic fallback
- **Providers** (`providers/`): CLI-first router supporting Claude, Codex, Gemini, Cursor CLIs + API fallback
- **GitOps** (`gitops/`): Git worktrees for parallel work, auto-rebase, feature branch management
- **Monitoring** (`monitoring/`): Prometheus metrics exposed at `/metrics`

### Key Design Patterns
- **CLI-first approach**: Prefers local CLI tools (`claude`, `codex`, `gemini`, `cursor-agent`) over APIs
- **Full access mode**: Supports `--dangerously-skip-permissions` (Claude) and `--sandbox danger-full-access` (Codex)
- **Git worktrees**: Each task runs in isolated worktree to prevent conflicts
- **Dynamic roles**: Add new roles via YAML files in `roles/` directory without code changes
- **Provider fallback**: Tries providers in order until one succeeds
- **Conventional commits**: All commits follow `feat(scope):`, `fix(scope):` format

### Data Flow
1. Task submitted via POST `/tasks` with role specification
2. Task queued in Redis, assigned to role-specific agent
3. Agent creates/switches to feature branch in dedicated worktree
4. Provider router calls appropriate CLI/API based on configuration
5. Auto-commit every 30min, auto-PR every 2h via systemd timers

### Configuration
- `config/config.yaml`: Provider order, role definitions, git hygiene settings
- `roles/*.yaml`: Custom role definitions with branch prefixes and prompts
- Environment variables in `.env` for API keys and paths

## Working with the Codebase

**Agent development**: Extend `agents/base.py` Agent class, implement `plan_and_execute()` method

**Provider integration**: Add new providers in `providers/` following CLI or API pattern. Full access providers use `mode: "interactive"` with appropriate CLI flags.

**Role customization**: Create YAML files in `roles/` with name, branch_prefix, reviewers, and prompt. Can specify `full_access: true` for unrestricted tasks.

**Git workflow**: Always work in feature branches with conventional commit messages. The system uses git worktrees - never modify the root checkout directly.

**Testing**: Use pytest with FastAPI + ruff + mypy conventions. Add tests for all new functionality.

## Multi-Agent Development

For complex features requiring parallel development across multiple specializations, use the multi-agent coordination patterns defined in **AGENTS.md**:

- **Task Distribution**: Break complex features into specialized components
- **Parallel Development**: Multiple agents working simultaneously in isolated git worktrees  
- **Role-Based Specialization**: Backend, frontend, infrastructure, and testing specialists
- **Coordination Patterns**: Orchestrator manages dependencies and integration

**Quick Multi-Agent Setup:**
```bash
# 1. Primary orchestrator for coordination
claude --dangerously-skip-permissions

# 2. Specialized agents for parallel work
codex --ask-for-approval never --sandbox danger-full-access exec "Backend development"
codex --ask-for-approval never --sandbox danger-full-access exec "Frontend development" 
codex --ask-for-approval never --sandbox danger-full-access exec "Testing and QA"

# 3. Load shared helpers in each agent session
exec(open('scripts/agent_helpers.py').read())
```

See **AGENTS.md** for comprehensive multi-agent workflows, role configurations, and coordination patterns.
