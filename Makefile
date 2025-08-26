SHELL := /bin/bash

.PHONY: install dev run workers tmuxp monitoring precommit enable-timers

install:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"
	pre-commit install

dev:
	uvicorn orchestrator.app:app --reload --host 0.0.0.0 --port 8000

run:
	redis-server & sleep 1
	rq worker autodev

workers:
	rq worker autodev

tmuxp:
	tmuxp load tmuxp/session.yaml -d
	tmux a -t autodev || true

monitoring:
	docker compose -f docker/monitoring/docker-compose.yml up -d

precommit:
	pre-commit run --all-files

enable-timers:
	systemctl --user daemon-reload
	systemctl --user enable --now systemd/git-checkpointer.timer
	systemctl --user enable --now systemd/git-prizer.timer