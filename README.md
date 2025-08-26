# AutoDev - Multi-Agent Orchestration System

A complete, production-grade autonomous multi-agent coding system that orchestrates AI agents to work collaboratively on software development tasks using git worktrees for parallel execution.

## 🚀 Key Features

- **🔧 Local-first CLI support** - Uses your pre-configured `claude`, `codex`, `gemini`, `cursor-agent` commands
- **👥 Dynamic role system** - Add unlimited roles via YAML files (data_analyst, computational_biologist, fund_manager, etc.)
- **🔄 Git hygiene** - Auto-commits every 30min, auto-PRs every 2h, git worktrees for parallel work
- **📊 Monitoring** - Prometheus metrics, optional Grafana/Loki logging
- **🚀 CI/CD** - GitHub Actions, CODEOWNERS, branch protection
- **⚡ Queue-based architecture** - Redis-backed task queue with RQ workers
- **🔀 Provider fallback** - Tries multiple AI providers until one succeeds

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [How AutoDev Works](#how-autodev-works)
- [Architecture](#architecture)
- [Task Submission & Management](#task-submission--management)
- [Role System](#role-system)
- [Provider Configuration](#provider-configuration)
- [Git Workflow & Hygiene](#git-workflow--hygiene)
- [Monitoring & Observability](#monitoring--observability)
- [Development Workflow](#development-workflow)
- [Deployment Options](#deployment-options)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

## 🏃‍♂️ Quick Start

### Prerequisites

- Python 3.11+
- Redis server
- Git with clean working directory
- One or more AI CLI tools configured (`claude`, `codex`, `gemini`, `cursor-agent`) OR API keys

### 1. Initial Setup

```bash
# Clone and setup
git clone <repo-url>
cd um-agent-orchestration

# Configure environment
cp .env.example .env  # Edit with your paths and API keys
make install          # Install dependencies and pre-commit hooks
```

### 2. Start the System

```bash
# Terminal 1: API server (localhost:8000)
make dev

# Terminal 2: Redis server + RQ worker
make run

# Optional: Monitoring stack (Prometheus/Grafana)
make monitoring
```

### 3. Submit Your First Task

```bash
# Submit a task using example spec
curl -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d @specs/fm_example.yaml

# Or create your own task spec (see examples in specs/)
```

### 4. Enable Automated Git Hygiene

```bash
make enable-timers  # Auto-commit every 30min, auto-PR every 2h
```

## 🔍 How AutoDev Works

### Core Workflow

1. **Task Submission**: Submit tasks via HTTP POST to `/tasks` endpoint with role specification
2. **Queue Processing**: Task queued in Redis, picked up by RQ worker
3. **Role Assignment**: Task assigned to role-specific agent (backend, frontend, data, ml, custom roles)
4. **Git Isolation**: Agent creates dedicated git worktree for parallel work
5. **Provider Routing**: System tries AI providers in configured order until one succeeds
6. **Code Generation**: Agent executes task using role-specific prompts and tools
7. **Quality Assurance**: Runs lint, typecheck, tests as specified in acceptance criteria
8. **Git Hygiene**: Auto-commits progress, creates PRs with conventional commit messages

### Repository-Centric Design

AutoDev operates on **the current repository** where it's running. It doesn't clone external repos - instead it:
- Creates isolated git worktrees in `./worktrees/` for each task
- Works in feature branches with naming convention `auto/{role}/{task_id}`
- Maintains clean separation between concurrent tasks
- Auto-rebases and manages branch lifecycle

## 🏗️ Architecture

### Component Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   Redis Queue   │    │   RQ Workers    │
│  (Orchestrator) │───▶│   (Task Queue)  │───▶│   (Execution)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                                              │
         ▼                                              ▼
┌─────────────────┐                            ┌─────────────────┐
│   Task Status   │                            │  Agent Registry │
│   Management    │                            │ (Role-specific) │
└─────────────────┘                            └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │ Provider Router │
                                               │ (CLI-first +    │
                                               │  API fallback)  │
                                               └─────────────────┘
                                                        │
                           ┌────────────────────────────┼────────────────────────────┐
                           ▼                           ▼                           ▼
                  ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
                  │   Claude CLI    │        │   Codex CLI     │        │  Gemini CLI     │
                  │   Cursor CLI    │        │  Anthropic API  │        │  OpenAI API     │
                  └─────────────────┘        └─────────────────┘        └─────────────────┘
                           │                           │                           │
                           └────────────────────────────┼────────────────────────────┘
                                                        ▼
                                               ┌─────────────────┐
                                               │   Git Worktrees │
                                               │ (Parallel Work) │
                                               │                 │
                                               │ feat/backend/   │
                                               │ feat/data/      │
                                               │ feat/ml/        │
                                               └─────────────────┘
```

### Core Components

#### 🎯 Orchestrator (`orchestrator/`)
- **FastAPI application** serving HTTP API
- **Task management** via `/tasks` endpoints
- **Redis integration** for queue management
- **Metrics exposure** at `/metrics` endpoint

#### 🤖 Agents (`agents/`)
- **Role-based agents**: Backend, Frontend, Data, ML, Generic
- **Dynamic role loading** from YAML configuration
- **Generic agent** handles custom roles via prompts
- **Agent registry** for role-to-agent mapping

#### 🔄 Providers (`providers/`)
- **CLI-first approach**: Prefers local CLI tools over APIs
- **Provider router** with configurable fallback order
- **Multi-provider support**: Claude, Codex, Gemini, Cursor, APIs
- **Error handling** and provider switching

#### 📁 GitOps (`gitops/`)
- **Worktree management** for parallel task execution
- **Branch lifecycle** management with auto-cleanup
- **Checkpointer** for auto-commits every 30 minutes
- **Prizer** for auto-PRs every 2 hours
- **Rebase automation** to keep branches current

#### 📊 Monitoring (`monitoring/`)
- **Prometheus metrics** for observability
- **Structured logging** with configurable levels
- **Optional Grafana** dashboard for visualization
- **Performance tracking** across components

## 📋 Task Submission & Management

### Task Specification Format

Tasks are defined in YAML format with the following structure:

```yaml
# Required fields
id: TSK-UNIQUE-ID           # Unique task identifier
title: "Task title"         # Human-readable title
description: |              # Detailed task description
  Multi-line description of what needs to be accomplished.
  Include context, requirements, and expected outcomes.
role: data_analyst          # Target role (built-in or custom)

# Optional fields
target_dir: "src/analytics" # Working directory (default: ".")
acceptance:                 # Quality gates
  lint: true               # Run linting (ruff)
  typecheck: true          # Run type checking (mypy)
  tests:                   # Test commands to run
    - "pytest tests/unit/"
    - "pytest tests/integration/test_specific.py::test_function"

# Custom fields for role-specific needs
data_source: "s3://bucket/data/"
output_format: "parquet"
```

### Example Task Specifications

See the `specs/` directory for complete examples:

- **`specs/fm_example.yaml`** - Financial modeling task
- **`specs/da_example.yaml`** - Data analysis task  
- **`specs/compbio_example.yaml`** - Computational biology task
- **`specs/sample_task.yaml`** - Basic template

### Task Lifecycle

1. **Queued** - Task submitted and waiting for worker
2. **Running** - Worker processing task in dedicated worktree
3. **Passed** - All acceptance criteria met
4. **Failed** - Acceptance criteria failed (tests, lint, etc.)
5. **Error** - System error during execution

### Monitoring Tasks

```bash
# Get task status
curl http://localhost:8000/tasks/TSK-UNIQUE-ID

# List all tasks (via metrics endpoint)
curl http://localhost:8000/metrics | grep autodev_task
```

## 👥 Role System

### Built-in Roles

AutoDev includes several pre-configured roles:

#### Backend Engineer (`backend`)
- **Focus**: FastAPI, pytest, ruff, mypy conventions
- **Branch prefix**: `feat/backend`
- **Specialties**: API development, database integration, testing

#### Frontend Engineer (`frontend`)  
- **Focus**: Modern React, Vite, TypeScript
- **Branch prefix**: `feat/frontend`
- **Specialties**: UI/UX, component development, performance

#### Data Engineer (`data`)
- **Focus**: Polars over pandas, modular ETL, unit tests
- **Branch prefix**: `feat/data`
- **Specialties**: Data pipelines, transformation, validation

#### ML Engineer (`ml`)
- **Focus**: Reproducible models, testing, metrics logging
- **Branch prefix**: `feat/ml`  
- **Specialties**: Model training, evaluation, deployment

### Creating Custom Roles

Create a YAML file in the `roles/` directory:

```yaml
# roles/sre.yaml
name: sre
branch_prefix: "feat/sre"
reviewers: ["@org/devops", "@org/platform"]
prompt: |
  You are a Site Reliability Engineer focused on:
  - System reliability and uptime
  - Infrastructure automation  
  - Monitoring and alerting
  - Performance optimization
  - Incident response procedures
  
  Always include:
  - Proper error handling and logging
  - Health checks and metrics
  - Documentation for runbooks
  - Terraform/CloudFormation for IaC
```

### Role Configuration Options

- **`name`** - Role identifier (must match filename)
- **`branch_prefix`** - Git branch naming convention
- **`reviewers`** - GitHub users/teams for PR reviews
- **`prompt`** - Role-specific instructions and context

### Dynamic Role Loading

Roles are loaded automatically at startup from:
1. Built-in roles in `config/config.yaml` 
2. Custom roles from `roles/*.yaml` files
3. No code changes required - just add YAML files

## 🔧 Provider Configuration

### CLI-First Philosophy

AutoDev prioritizes local CLI tools over APIs to:
- Leverage your existing configurations
- Reduce API costs and rate limits
- Maintain faster response times
- Honor your preferred models and settings

### Provider Order Configuration

Edit `config/config.yaml` to set provider priority:

```yaml
providers:
  order:
    - "claude_cli"      # Try Claude CLI first
    - "codex_cli"       # Fallback to Codex CLI
    - "gemini_cli"      # Then Gemini CLI  
    - "cursor_cli"      # Then Cursor CLI
    - "anthropic_api"   # API fallback
    - "openai_api"      # Final fallback
```

### CLI Provider Setup

Ensure CLI tools are installed and configured:

```bash
# Claude Code CLI
claude --version
claude -p "test prompt"

# OpenAI Codex CLI  
codex --version
codex exec "test prompt"

# Gemini CLI
gemini --version
gemini -p "test prompt"

# Cursor CLI
cursor-agent --version
cursor-agent -p "test prompt"
```

### API Provider Setup

For API fallback, configure `.env`:

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI API  
OPENAI_API_KEY=sk-...

# Repository path for git operations
REPO_PATH=/path/to/your/repo
DEV_BRANCH=main
```

### Provider-Specific Configuration

```yaml
# CLI providers
claude_cli:
  mode: "cli"
  binary: "claude"
  args: ["-p", "--output-format", "text"]
  model: "sonnet"  # optional model hint

# API providers  
anthropic_api:
  mode: "api"
  model: "claude-3-5-sonnet-latest"
  max_tokens: 4096
```

## 🔄 Git Workflow & Hygiene

### Worktree-Based Isolation

Each task runs in an isolated git worktree:

```
repo/
├── main branch (protected)
├── worktrees/
│   ├── TSK-001/          # Task 1 worktree
│   │   └── feat/backend/TSK-001/
│   ├── TSK-002/          # Task 2 worktree  
│   │   └── feat/data/TSK-002/
│   └── TSK-003/          # Task 3 worktree
│       └── feat/ml/TSK-003/
```

### Automated Git Hygiene

#### Checkpointer (Every 30 minutes)
- Auto-commits work in progress
- Uses conventional commit format
- Preserves granular history
- Handles merge conflicts automatically

#### Prizer (Every 2 hours)  
- Creates pull requests for completed features
- Includes task context and acceptance criteria
- Assigns reviewers based on role configuration
- Auto-rebases against main branch

### Branch Naming Convention

- **Format**: `auto/{role}/{task_id}`
- **Examples**: 
  - `auto/backend/TSK-API-001`
  - `auto/data/TSK-ETL-002`
  - `auto/ml/TSK-MODEL-003`

### Conventional Commits

All commits follow conventional commit format:

```
feat(scope): add new feature
fix(scope): resolve bug
docs(scope): update documentation  
test(scope): add test coverage
refactor(scope): improve code structure
```

### Manual Git Commands

```bash
# Enable automated timers
make enable-timers

# Manual checkpoint
python -m gitops.checkpointer

# Manual PR creation
python -m gitops.prizer

# List active worktrees
git worktree list
```

## 📊 Monitoring & Observability

### Prometheus Metrics

AutoDev exposes metrics at `http://localhost:8000/metrics`:

```
# Task metrics
autodev_tasks_total{role="backend",status="completed"} 5
autodev_task_duration_seconds{role="data"} 120.5
autodev_provider_requests_total{provider="claude_cli",status="success"} 15

# System metrics  
autodev_active_worktrees 3
autodev_queue_size 2
autodev_git_operations_total{operation="commit"} 25
```

### Logging Configuration

Configure logging in `monitoring/logging.yaml`:

```yaml
version: 1
formatters:
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
handlers:
  file:
    class: logging.FileHandler
    filename: 'logs/autodev.log'
    formatter: detailed
loggers:
  autodev:
    level: INFO
    handlers: [file]
```

### Grafana Dashboard

Optional monitoring stack with Docker:

```bash
# Start Prometheus + Grafana + Loki
make monitoring

# Access dashboards
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

Pre-configured dashboards include:
- Task throughput and success rates
- Provider performance and fallback patterns
- Git operation metrics
- System resource usage

## 🛠️ Development Workflow

### Development Commands

```bash
# Core workflow
make install           # Dependencies + pre-commit hooks
make dev              # FastAPI server (localhost:8000)
make run              # Redis + RQ worker
make workers          # Additional RQ workers

# Testing and quality
pytest                # Run test suite
pytest tests/acceptance/test_sample.py::test_function  # Single test
ruff                  # Lint and format
mypy                  # Type checking
make precommit        # All pre-commit hooks

# Development environment
make tmuxp            # tmux session with all components
make monitoring       # Prometheus/Grafana stack
```

### Project Structure

```
um-agent-orchestration/
├── agents/           # Role-based agents
├── config/           # Configuration files
├── docker/           # Docker compositions
├── gitops/           # Git automation
├── monitoring/       # Observability
├── orchestrator/     # FastAPI application
├── providers/        # AI provider integrations
├── roles/            # Custom role definitions
├── scripts/          # Utility scripts
├── specs/            # Task specification examples
├── systemd/          # System service definitions  
├── tests/            # Test suite
└── tmuxp/            # Development session config
```

### Adding New Components

#### New Agent Type

```python
# agents/custom_agent.py
from agents.base import Agent

class CustomAgent(Agent):
    def plan_and_execute(self, task_spec, worktree_path):
        # Custom implementation
        pass
```

#### New Provider

```python  
# providers/custom_provider.py
from providers.base import Provider

class CustomProvider(Provider):
    def execute(self, prompt: str) -> str:
        # Custom provider logic
        pass
```

#### New Role

```yaml
# roles/custom_role.yaml
name: custom_role
branch_prefix: "feat/custom"
reviewers: ["@org/team"]
prompt: |
  Custom role instructions
```

### Testing Strategy

```bash
# Unit tests
pytest tests/unit/

# Integration tests  
pytest tests/integration/

# Acceptance tests
pytest tests/acceptance/

# End-to-end workflow
curl -X POST localhost:8000/tasks -d @specs/test_task.yaml
```

## 🚀 Deployment Options

### Local Development (tmux)

```bash
make tmuxp  # Starts coordinated tmux session
```

Creates windows for:
- FastAPI server
- Redis + RQ worker
- Additional workers
- Log monitoring
- Git operations

### System Services (systemd)

```bash
# Install user services
cp systemd/* ~/.config/systemd/user/
systemctl --user daemon-reload

# Enable automated git hygiene
systemctl --user enable git-checkpointer.timer
systemctl --user enable git-prizer.timer
systemctl --user start git-checkpointer.timer
systemctl --user start git-prizer.timer
```

### Container Deployment

```bash
# Monitoring stack only (Prometheus + Grafana)
make monitoring

# Full containerization (TODO)
# docker-compose -f docker/app/docker-compose.yml up
```

### Cloud Deployment Considerations

- **Redis**: Use managed Redis (AWS ElastiCache, GCP Memorystore)
- **Storage**: Ensure worktrees directory is on persistent storage
- **Git**: Configure SSH keys for private repository access
- **Monitoring**: Export metrics to cloud monitoring systems
- **Secrets**: Use cloud secret management for API keys

## 📚 API Reference

### Submit Task

```http
POST /tasks
Content-Type: application/json

{
  "id": "TSK-001",
  "title": "Task title", 
  "description": "Task description",
  "role": "backend",
  "target_dir": "src/",
  "acceptance": {
    "lint": true,
    "typecheck": true,
    "tests": ["pytest tests/"]
  }
}
```

**Response:**
```json
{
  "job_id": "uuid-string",
  "task_id": "TSK-001"  
}
```

### Get Task Status

```http
GET /tasks/{task_id}
```

**Response:**
```json
{
  "id": "TSK-001",
  "role": "backend", 
  "branch": "auto/backend/TSK-001",
  "state": "running",
  "last_error": null
}
```

### Metrics Endpoint

```http
GET /metrics
```

Returns Prometheus-formatted metrics for monitoring and alerting.

## 🔧 Troubleshooting

### Common Issues

#### Task Stuck in Queue
```bash
# Check RQ worker status
rq worker autodev --url redis://localhost:6379

# Clear Redis queue
redis-cli flushall
```

#### Provider Authentication
```bash
# Test CLI providers
claude -p "test"
codex exec "test" 
gemini -p "test"

# Check API keys in .env
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY
```

#### Git Worktree Issues
```bash
# List active worktrees
git worktree list

# Remove stale worktree
git worktree remove worktrees/TSK-001 --force

# Clean up branches
git branch -D auto/backend/TSK-001
```

#### Port Conflicts
```bash
# Check port usage
lsof -i :8000  # FastAPI
lsof -i :6379  # Redis
lsof -i :9090  # Prometheus
lsof -i :3000  # Grafana
```

### Debug Mode

```bash
# Enable verbose logging
export AUTODEV_LOG_LEVEL=DEBUG

# Run with debug output  
python -m uvicorn orchestrator.app:app --reload --log-level debug
```

### Health Checks

```bash
# API health
curl http://localhost:8000/tasks

# Redis connectivity
redis-cli ping

# Provider availability
make test-providers  # TODO: implement
```

### Performance Tuning

#### Increase Worker Count
```bash
# Multiple workers
make workers  # Starts additional RQ workers

# Manual worker scaling
rq worker autodev &
rq worker autodev &  
rq worker autodev &
```

#### Optimize Git Operations
```bash
# Configure Git for performance
git config core.preloadindex true
git config core.fscache true
git config gc.auto 256
```

#### Provider Optimization
```yaml
# Prefer faster providers first
providers:
  order:
    - "claude_cli"     # Usually fastest
    - "cursor_cli"     # Local processing
    - "gemini_cli"     # Good performance  
    - "codex_cli"      # API rate limits
    - "anthropic_api"  # Fallback
```

---

## 📄 License

[License details]

## 🤝 Contributing

See individual component directories for detailed development documentation and contribution guidelines.

## 📞 Support

- **Issues**: GitHub Issues
- **Documentation**: Component-specific README files
- **Architecture**: `CLAUDE.md` for development context