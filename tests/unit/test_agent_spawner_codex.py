"""Ensure codex fallback path produces actionable artifacts."""

import shutil
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agent_spawner import AgentSpawner, AgentType


def test_codex_fallback_generates_script(tmp_path, monkeypatch):
    """Fallback execution should create a runnable script and document it."""
    spawner = AgentSpawner(base_dir=str(tmp_path / "agents"))

    # Force the fallback branch by pretending the codex binary is missing.
    original_which = shutil.which

    def fake_which(name: str):
        return None if name == "codex" else original_which(name)

    monkeypatch.setattr("src.core.agent_spawner.shutil.which", fake_which)

    agent_id = spawner.spawn_agent(
        AgentType.CODEX,
        "demo123",
        "Create a script that lists processes",
    )

    # Allow the fallback shell to complete
    for _ in range(20):
        status = spawner.get_agent_status(agent_id)
        if status and not status["running"]:
            break
        time.sleep(0.1)

    output = spawner.get_agent_output(agent_id)
    assert output is not None
    assert "generated_process_list.sh" in output
    assert "#!/usr/bin/env bash" in output

    working_dir = Path(spawner.agents[agent_id].working_dir)
    script_path = working_dir / "generated_process_list.sh"
    assert script_path.exists()
    script_body = script_path.read_text()
    assert "ps aux" in script_body

    spawner.cleanup_all()
