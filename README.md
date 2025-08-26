# AutoDev - Multi-Agent Orchestration System

A complete, production-grade autonomous multi-agent coding system with:

- **Local-first CLI support** - Uses your pre-configured `claude`, `codex`, `gemini`, `cursor-agent` commands
- **Dynamic role system** - Add unlimited roles via YAML files (data_analyst, computational_biologist, fund_manager, etc.)
- **Git hygiene** - Auto-commits every 30min, auto-PRs every 2h, git worktrees for parallel work
- **Monitoring** - Prometheus metrics, optional Grafana/Loki logging
- **CI/CD** - GitHub Actions, CODEOWNERS, branch protection

## Quick Start

1. **Setup**:
   ```bash
   cp .env.example .env  # Edit with your paths
   make install
   ```

2. **Run locally**:
   ```bash
   # Terminal 1: API server
   make dev

   # Terminal 2: Redis + Worker
   redis-server &
   rq worker autodev

   # Optional: Monitoring stack
   make monitoring
   ```

3. **Submit tasks**:
   ```bash
   curl -X POST http://localhost:8000/tasks \
     -H 'Content-Type: application/json' \
     -d @specs/fm_example.yaml
   ```

4. **Enable git hygiene**:
   ```bash
   make enable-timers  # Auto-commit + auto-PR
   ```

## Local CLI vs API

**Default**: CLI-first using your pre-configured tools
- `claude -p "prompt"` (Claude Code CLI)
- `codex exec "prompt"` (OpenAI Codex CLI) 
- `gemini -p "prompt"` (Gemini CLI)
- `cursor-agent -p "prompt"` (Cursor CLI)

**API mode**: Set `mode: "api"` in `config/config.yaml` and provide keys in `.env`

## Adding New Roles

Create `roles/your_role.yaml`:

```yaml
name: sre
branch_prefix: "feat/sre"
reviewers: ["@org/devops"]
prompt: |
  You are an SRE. Focus on reliability, monitoring, and automation.
```

Submit tasks with `role: sre` - no code changes needed!

## Architecture

- **Orchestrator**: FastAPI app with Redis queue
- **Agents**: Generic agents use role-specific prompts
- **GitOps**: Parallel worktrees, feature branches, auto-rebase
- **Providers**: CLI-first router with API fallback
- **Monitoring**: Prometheus metrics at `/metrics`

## Deployment Options

- **tmux**: `make tmuxp` for local development
- **systemd**: User timers for git hygiene automation
- **Docker**: Monitoring stack with Prometheus/Grafana

See full documentation in individual component directories.