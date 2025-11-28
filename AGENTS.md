# Repository Guidelines

## Project Structure & Module Organization
The orchestrator logic lives in `src/core/` (task queue, agent spawners, context management) while the CLI entry point is in `src/cli/orchestrate.py`. Shared helpers sit under `src/utils/`. Tests are grouped by intent inside `tests/` (unit, integration, performance, security) with additional scenario scripts in the repository root (`test_*.py`) and walkthroughs inside `docs/`. Configuration defaults and prompt templates are under `config/`, reusable launch helpers in `scripts/`, and sample workflows in `examples/`.

## Build, Test, and Development Commands
Run `./quickstart.sh` once for full environment bootstrap (venv, dependencies, `.env` scaffolding). During daily work use `./run.sh plan|submit|run` to interact with the orchestrator. For focused development, activate the virtualenv (`source venv_orchestrator/bin/activate`) and install extras as needed with `pip install -r requirements.txt`. Execute targeted test suites via `python -m pytest tests/unit -q`, broaden to `tests/integration` for end-to-end flows, and use `pytest test_cli_websocket.py -k scenario` when iterating on a specific regression.

## Coding Style & Naming Conventions
Stick to Python 3.8+ conventions: four-space indentation, descriptive module-level docstrings, and explicit type hints on public interfaces. Modules should expose orchestrator capabilities via verbs (`task_decomposer.py`, `feedback_orchestrator.py`), and new CLI commands belong beside `src/cli/orchestrate.py`. Prefer dataclasses for structured payloads, favor pure functions inside `src/utils/`, and keep configuration constants in `config/`. Run `ruff check src tests` and `mypy src` before PR submission if those tools are available locally.

## Testing Guidelines
Place new unit tests under `tests/unit/` mirroring the module path (`test_task_decomposer.py` for `core/task_decomposer.py`). Integration coverage belongs in `tests/integration/`, exercising orchestration flows through the CLI. Performance and security suites in their respective folders should stay green; mark long-running cases with `pytest.mark.slow` so they can be skipped locally. Use descriptive test names (`test_run_adds_task_to_queue`) and keep fixtures in `tests/conftest.py`.

## Commit & Pull Request Guidelines
Follow Conventional Commits (`feat:`, `fix:`, `docs:`, optional scope) as reflected in recent history (`docs:`, `feat(gitops):`, `fix(dashboard):`). Each PR should summarize intent, link tracking issues, and include CLI output or screenshots for user-visible changes. Note configuration impacts (e.g., `.env` keys, new scripts), confirm relevant pytest suites pass, and request review from an orchestrator maintainer.

## Security & Configuration Tips
Never commit real API keys; keep `.env` entries placeholder-only and reference secret management notes in `docs/`. Validate changes against `config/config.yaml` prompts to avoid leaking credentials, and exercise caution when modifying `tasks.db`—wipe it locally with `rm tasks.db` rather than shipping altered SQLite files.
