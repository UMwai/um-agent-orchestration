SHELL := /bin/bash

.PHONY: install dev run workers tmuxp monitoring precommit enable-timers merge-queue merge-process

install:
	source .venv/bin/activate && python -m pip install --upgrade pip
	source .venv/bin/activate && pip install -e ".[dev]"
	source .venv/bin/activate && pre-commit install

dev:
	source .venv/bin/activate && uvicorn orchestrator.app:app --reload --host 0.0.0.0 --port 8001

run:
	redis-server & sleep 1
	source .venv/bin/activate && rq worker autodev

workers:
	source .venv/bin/activate && rq worker autodev

tmuxp:
	tmuxp load tmuxp/session.yaml -d
	tmux a -t autodev || true

monitoring:
	docker compose -f docker/monitoring/docker-compose.yml up -d

precommit:
	source .venv/bin/activate && pre-commit run --all-files

enable-timers:
	systemctl --user daemon-reload
	systemctl --user enable --now systemd/git-checkpointer.timer
	systemctl --user enable --now systemd/git-prizer.timer
	systemctl --user enable --now systemd/merge-processor.timer

merge-queue:
	curl -X GET http://localhost:8001/merge/status

merge-process:
	./scripts/merge_queue_processor.py