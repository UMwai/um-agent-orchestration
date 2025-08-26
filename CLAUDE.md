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