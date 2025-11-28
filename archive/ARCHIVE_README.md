# Archive: Previous Implementation (2025-01-28)

This directory contains the archived overcomplicated implementation that was replaced with a simplified architecture.

## Why Archived?
- Over-engineered with ~5000 lines for what should be ~500-1000 lines
- Complex dependencies (Redis, RQ, Node.js, monitoring stack)
- Enterprise features not needed for local agent orchestration
- GitOps automation and worktrees added unnecessary complexity

## Original Components:
- `agents/` - Role-based agent system with complex abstractions
- `providers/` - 8 different provider implementations
- `orchestrator/` - FastAPI server with Redis queues
- `dashboard/` - Full React web interface
- `gitops/` - Automated git worktree management
- `monitoring/` - Prometheus/Grafana stack
- `roles/` - YAML-based role definitions

## Replaced With:
A simplified ~500 line implementation focused on:
- Direct CLI subprocess spawning (codex-cli, claude-code)
- SQLite for task queue (no Redis)
- File-based IPC (no WebSockets)
- CLI-first interface (no complex web UI)
- Simple head node → child nodes orchestration

Keep this archive for reference but DO NOT actively develop it.