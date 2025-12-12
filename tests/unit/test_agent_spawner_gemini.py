"""Ensure gemini fallback path produces output when CLI missing."""

import shutil
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agent_spawner import AgentSpawner, AgentType


def test_gemini_fallback_writes_output(tmp_path, monkeypatch):
    """Fallback execution should write demo output to output.txt."""
    spawner = AgentSpawner(base_dir=str(tmp_path / "agents"))

    original_which = shutil.which

    def fake_which(name: str):
        return None if name == "gemini" else original_which(name)

    monkeypatch.setattr("src.core.agent_spawner.shutil.which", fake_which)

    agent_id = spawner.spawn_agent(
        AgentType.GEMINI,
        "demo123",
        "Analyze biotech M and A opportunities",
    )

    for _ in range(20):
        status = spawner.get_agent_status(agent_id)
        if status and not status["running"]:
            break
        time.sleep(0.1)

    output = spawner.get_agent_output(agent_id)
    assert output is not None
    assert "DEMO MODE: Gemini" in output

    spawner.cleanup_all()

