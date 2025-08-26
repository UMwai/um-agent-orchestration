# Global Agent Rules

- Follow Conventional Commits for all commit messages (`feat(scope): ...`, `fix(scope): ...`).
- Limit changes per commit to a cohesive unit; push drafts frequently.
- Always update or add tests. Do not remove tests without justification.
- Preferred stack for samples: FastAPI + pytest + ruff + mypy.

## Branching / Worktrees

- Your working directory is an isolated git worktree. Never modify the root checkout.
- Rebase onto `origin/dev` before opening PR.

## Feedback Loop

1. Implement minimal viable change.
2. Run `ruff`, `mypy`, `pytest`.
3. If failing, summarize failures and propose the smallest corrective patch.
4. Repeat up to 6 iterations.