"""
Simple Agent Spawner for CLI processes
Direct subprocess management for codex and claude CLI tools
"""

import subprocess
import os
import json
import time
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import threading
import queue


class AgentType(Enum):
    CLAUDE = "claude"
    CODEX = "codex"


@dataclass
class AgentProcess:
    """Represents a running agent process"""

    agent_id: str
    agent_type: AgentType
    process: subprocess.Popen
    working_dir: str
    task_id: Optional[str] = None
    status: str = "idle"
    started_at: float = 0
    output_file: Optional[str] = None


class AgentSpawner:
    """Manages spawning and monitoring of CLI agent processes"""

    def __init__(self, base_dir: str = "/tmp/agent_orchestrator"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.agents: Dict[str, AgentProcess] = {}
        self.output_queue = queue.Queue()

    def spawn_agent(
        self,
        agent_type: AgentType,
        task_id: str,
        task_description: str,
        context: Dict = None,
    ) -> str:
        """Spawn a new agent process for a task"""
        agent_id = f"{agent_type.value}-{task_id}"
        working_dir = self.base_dir / f"agent_{agent_id}"
        working_dir.mkdir(parents=True, exist_ok=True)

        # Prepare context file if provided
        if context:
            context_file = working_dir / "context.json"
            with open(context_file, "w") as f:
                json.dump(context, f, indent=2)

        # Prepare the prompt with task description
        prompt = self._prepare_prompt(task_description, context)

        # Build the command based on agent type
        cmd = self._build_command(agent_type, prompt, working_dir)

        # Create output file for capturing results
        output_file = working_dir / "output.txt"

        # Spawn the process
        with open(output_file, "w") as out_f:
            process = subprocess.Popen(
                cmd,
                cwd=str(working_dir),
                stdout=out_f,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True,
            )

        # Create agent process record
        agent = AgentProcess(
            agent_id=agent_id,
            agent_type=agent_type,
            process=process,
            working_dir=str(working_dir),
            task_id=task_id,
            status="running",
            started_at=time.time(),
            output_file=str(output_file),
        )

        self.agents[agent_id] = agent

        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=self._monitor_agent, args=(agent_id,), daemon=True
        )
        monitor_thread.start()

        return agent_id

    def _prepare_prompt(self, task_description: str, context: Dict = None) -> str:
        """Prepare the prompt for the agent"""
        prompt_parts = [
            f"Task: {task_description}",
            "",
            "Instructions:",
            "1. Complete the task described above",
            "2. Write any output or results to output.txt in the current directory",
            "3. If context is provided, it's available in context.json",
            "",
        ]

        if context:
            prompt_parts.append(
                "Context has been provided in context.json. Please review it."
            )
            prompt_parts.append("")

        prompt_parts.append("Please complete this task now.")

        return "\n".join(prompt_parts)

    def _build_command(
        self, agent_type: AgentType, prompt: str, working_dir: Path
    ) -> str:
        """Build the command to spawn the agent"""
        # Save prompt to file to avoid shell escaping issues
        prompt_file = working_dir / "prompt.txt"
        with open(prompt_file, "w") as f:
            f.write(prompt)

        if agent_type == AgentType.CLAUDE:
            # Claude CLI with dangerous permissions for full access
            return f'claude --dangerously-skip-permissions -p "$(cat {prompt_file})"'
        elif agent_type == AgentType.CODEX:
            # Codex CLI with full access
            return f'codex --ask-for-approval never --sandbox danger-full-access exec "$(cat {prompt_file})"'
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

    def _monitor_agent(self, agent_id: str):
        """Monitor an agent process"""
        agent = self.agents.get(agent_id)
        if not agent:
            return

        # Wait for process to complete
        return_code = agent.process.wait()

        # Update agent status
        agent.status = "completed" if return_code == 0 else "failed"

        # Read output
        output = ""
        if agent.output_file and os.path.exists(agent.output_file):
            with open(agent.output_file, "r") as f:
                output = f.read()

        # Add to output queue
        self.output_queue.put(
            {
                "agent_id": agent_id,
                "task_id": agent.task_id,
                "status": agent.status,
                "output": output,
                "return_code": return_code,
                "duration": time.time() - agent.started_at,
            }
        )

    def get_agent_status(self, agent_id: str) -> Optional[Dict]:
        """Get status of a specific agent"""
        agent = self.agents.get(agent_id)
        if not agent:
            return None

        return {
            "agent_id": agent_id,
            "agent_type": agent.agent_type.value,
            "task_id": agent.task_id,
            "status": agent.status,
            "working_dir": agent.working_dir,
            "running": agent.process.poll() is None,
            "duration": time.time() - agent.started_at if agent.started_at else 0,
        }

    def get_all_agents(self) -> List[Dict]:
        """Get status of all agents"""
        return [self.get_agent_status(aid) for aid in self.agents.keys()]

    def kill_agent(self, agent_id: str) -> bool:
        """Kill a running agent process"""
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        if agent.process.poll() is None:
            agent.process.terminate()
            time.sleep(1)
            if agent.process.poll() is None:
                agent.process.kill()
            agent.status = "killed"
            return True

        return False

    def get_agent_output(self, agent_id: str) -> Optional[str]:
        """Get the output from an agent"""
        agent = self.agents.get(agent_id)
        if not agent or not agent.output_file:
            return None

        if os.path.exists(agent.output_file):
            with open(agent.output_file, "r") as f:
                return f.read()

        return None

    def cleanup_agent(self, agent_id: str):
        """Clean up agent working directory"""
        agent = self.agents.get(agent_id)
        if agent:
            # Kill process if still running
            self.kill_agent(agent_id)

            # Remove working directory
            import shutil

            if os.path.exists(agent.working_dir):
                shutil.rmtree(agent.working_dir)

            # Remove from agents dict
            del self.agents[agent_id]

    def cleanup_all(self):
        """Clean up all agents and working directories"""
        for agent_id in list(self.agents.keys()):
            self.cleanup_agent(agent_id)


if __name__ == "__main__":
    # Simple test
    spawner = AgentSpawner()

    # Spawn a test agent
    print("Spawning test agent...")
    agent_id = spawner.spawn_agent(
        AgentType.CLAUDE,
        "test-task-1",
        "Write a simple Python hello world program",
        {"language": "python", "style": "simple"},
    )

    print(f"Agent spawned: {agent_id}")

    # Check status
    time.sleep(2)
    status = spawner.get_agent_status(agent_id)
    print(f"Agent status: {status}")

    # Wait for completion (with timeout)
    max_wait = 30
    start = time.time()
    while time.time() - start < max_wait:
        status = spawner.get_agent_status(agent_id)
        if status and not status["running"]:
            break
        time.sleep(1)

    # Get output
    output = spawner.get_agent_output(agent_id)
    if output:
        print(f"Agent output:\n{output}")

    # Cleanup
    spawner.cleanup_all()
    print("Cleanup complete")
