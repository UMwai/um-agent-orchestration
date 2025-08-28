#!/usr/bin/env python3
"""
Main CLI interface for the simplified agent orchestrator
"""

import click
import json
import time
from pathlib import Path
import sys
from typing import Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.task_queue import TaskQueue, TaskStatus, Priority
from src.core.agent_spawner import AgentSpawner, AgentType
from src.core.context_manager import ContextManager
from src.core.task_decomposer import TaskDecomposer


class Orchestrator:
    """Main orchestrator that coordinates everything"""

    def __init__(
        self, db_path: str = "tasks.db", base_dir: str = "/tmp/agent_orchestrator"
    ):
        self.queue = TaskQueue(db_path)
        self.spawner = AgentSpawner(base_dir)
        self.context = ContextManager(f"{base_dir}/context")
        self.running = False

    def submit_task(
        self,
        description: str,
        agent_type: str = "any",
        priority: str = "normal",
        context: Dict = None,
    ) -> str:
        """Submit a new task"""
        priority_map = {
            "high": Priority.HIGH,
            "normal": Priority.NORMAL,
            "low": Priority.LOW,
        }

        task_id = self.queue.add_task(
            description=description,
            agent_type=agent_type,
            priority=priority_map.get(priority, Priority.NORMAL),
            context=context,
        )

        if context:
            self.context.set_task_context(task_id, context)

        return task_id

    def process_tasks(self, max_agents: int = 3):
        """Process tasks from queue"""
        active_agents = []

        while True:
            # Clean up completed agents
            for agent_id in list(active_agents):
                status = self.spawner.get_agent_status(agent_id)
                if status and not status["running"]:
                    # Get output and update task
                    output = self.spawner.get_agent_output(agent_id)
                    task_id = status["task_id"]

                    if output:
                        self.context.add_agent_output(agent_id, task_id, output)

                    # Update task status
                    if status["status"] == "completed":
                        self.queue.update_status(
                            task_id, TaskStatus.COMPLETED, result=output
                        )
                        click.echo(f"✅ Task {task_id} completed by {agent_id}")
                    else:
                        self.queue.update_status(
                            task_id, TaskStatus.FAILED, error="Agent failed"
                        )
                        click.echo(f"❌ Task {task_id} failed on {agent_id}")

                    active_agents.remove(agent_id)

            # Spawn new agents if under limit
            while len(active_agents) < max_agents:
                # Try each agent type
                for agent_type_str in ["claude", "codex"]:
                    task = self.queue.get_next_task(agent_type_str)
                    if task:
                        # Assign and spawn
                        agent_type = (
                            AgentType.CLAUDE
                            if agent_type_str == "claude"
                            else AgentType.CODEX
                        )

                        if self.queue.assign_task(task.id, f"{agent_type_str}-agent"):
                            self.queue.update_status(task.id, TaskStatus.IN_PROGRESS)

                            agent_id = self.spawner.spawn_agent(
                                agent_type=agent_type,
                                task_id=task.id,
                                task_description=task.description,
                                context=task.context,
                            )

                            active_agents.append(agent_id)
                            click.echo(f"🚀 Spawned {agent_id} for task {task.id}")
                            break
                else:
                    # No more tasks for any agent type
                    break

            # Check if we're done
            if not active_agents and not self.queue.get_next_task():
                break

            # Wait a bit before next iteration
            time.sleep(2)

        click.echo("✨ All tasks completed!")


@click.group()
def cli():
    """Simple Agent Orchestrator - Manage multiple CLI agents"""
    pass


@cli.command()
@click.argument("description")
@click.option(
    "--agent",
    "-a",
    default="any",
    type=click.Choice(["claude", "codex", "any"]),
    help="Preferred agent type",
)
@click.option(
    "--priority",
    "-p",
    default="normal",
    type=click.Choice(["high", "normal", "low"]),
    help="Task priority",
)
@click.option("--context", "-c", help="JSON context for the task")
@click.option(
    "--decompose", "-d", is_flag=True, help="Automatically decompose into subtasks"
)
def submit(description, agent, priority, context, decompose):
    """Submit a new task to the queue"""
    orchestrator = Orchestrator()

    context_dict = None
    if context:
        try:
            context_dict = json.loads(context)
        except json.JSONDecodeError:
            click.echo("❌ Invalid JSON context", err=True)
            return

    if decompose:
        # Decompose the task into subtasks
        click.echo(f"🔍 Decomposing task: {description}")
        decomposer = TaskDecomposer()
        subtasks = decomposer.decompose_task(description)

        if not subtasks:
            click.echo("❌ Failed to decompose task", err=True)
            return

        click.echo(f"📝 Created {len(subtasks)} subtasks:")
        task_ids = []
        for i, subtask in enumerate(subtasks, 1):
            task_id = orchestrator.submit_task(
                subtask.description,
                subtask.agent_type,
                priority,
                {"parent_task": description, "subtask_index": i},
            )
            task_ids.append(task_id)
            click.echo(
                f"  {i}. [{subtask.agent_type}] {subtask.description} - {task_id}"
            )

        click.echo(f"✅ Submitted {len(task_ids)} subtasks")
    else:
        task_id = orchestrator.submit_task(description, agent, priority, context_dict)
        click.echo(f"✅ Task submitted: {task_id}")


@cli.command()
@click.option("--max-agents", "-m", default=3, help="Maximum concurrent agents")
def run(max_agents):
    """Run the orchestrator to process tasks"""
    orchestrator = Orchestrator()

    click.echo(f"🎯 Starting orchestrator with max {max_agents} agents...")
    click.echo("Press Ctrl+C to stop\n")

    try:
        orchestrator.process_tasks(max_agents)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Stopping orchestrator...")
        orchestrator.spawner.cleanup_all()


@cli.command()
def status():
    """Show status of all tasks and agents"""
    orchestrator = Orchestrator()

    # Show queue stats
    stats = orchestrator.queue.get_stats()
    click.echo("📊 Task Queue Status:")
    for status, count in stats.items():
        if count > 0:
            click.echo(f"  {status}: {count}")

    # Show running agents
    agents = orchestrator.spawner.get_all_agents()
    if agents:
        click.echo("\n🤖 Active Agents:")
        for agent in agents:
            click.echo(
                f"  {agent['agent_id']}: {agent['status']} (Task: {agent['task_id']})"
            )

    # Show recent tasks
    click.echo("\n📝 Recent Tasks:")
    tasks = orchestrator.queue.get_all_tasks()[:5]
    for task in tasks:
        click.echo(f"  [{task.id}] {task.description[:50]}... - {task.status}")


@cli.command()
@click.argument("task_id")
def task(task_id):
    """Show details of a specific task"""
    orchestrator = Orchestrator()

    task = orchestrator.queue.get_task(task_id)
    if not task:
        click.echo(f"❌ Task {task_id} not found", err=True)
        return

    click.echo("📋 Task Details:")
    click.echo(f"  ID: {task.id}")
    click.echo(f"  Description: {task.description}")
    click.echo(f"  Status: {task.status}")
    click.echo(f"  Agent Type: {task.agent_type}")
    click.echo(f"  Priority: {task.priority}")
    click.echo(f"  Created: {task.created_at}")

    if task.assigned_to:
        click.echo(f"  Assigned To: {task.assigned_to}")
    if task.result:
        click.echo(f"  Result: {task.result[:200]}...")
    if task.error:
        click.echo(f"  Error: {task.error}")

    # Show agent outputs
    outputs = orchestrator.context.get_agent_outputs(task_id)
    if outputs:
        click.echo("\n📤 Agent Outputs:")
        for output in outputs:
            click.echo(f"  {output['agent_id']}: {output['output'][:100]}...")


@cli.command()
def agents():
    """List all active agents"""
    orchestrator = Orchestrator()

    agents = orchestrator.spawner.get_all_agents()
    if not agents:
        click.echo("No active agents")
        return

    click.echo("🤖 Active Agents:")
    for agent in agents:
        status_icon = "🟢" if agent["running"] else "🔴"
        click.echo(f"{status_icon} {agent['agent_id']}")
        click.echo(f"   Type: {agent['agent_type']}")
        click.echo(f"   Task: {agent['task_id']}")
        click.echo(f"   Status: {agent['status']}")
        click.echo(f"   Duration: {agent['duration']:.1f}s")


@cli.command()
@click.argument("agent_id")
def kill(agent_id):
    """Kill a running agent"""
    orchestrator = Orchestrator()

    if orchestrator.spawner.kill_agent(agent_id):
        click.echo(f"✅ Killed agent {agent_id}")
    else:
        click.echo(f"❌ Could not kill agent {agent_id}", err=True)


@cli.command()
def cleanup():
    """Clean up all agents and old tasks"""
    orchestrator = Orchestrator()

    # Clean up agents
    orchestrator.spawner.cleanup_all()
    click.echo("✅ Cleaned up all agents")

    # Clean up old tasks
    deleted = orchestrator.queue.cleanup_old_tasks(days=7)
    click.echo(f"✅ Removed {deleted} old tasks")

    # Clean up old context
    deleted = orchestrator.context.cleanup_old_contexts(days=7)
    click.echo(f"✅ Cleaned up {deleted} old context files")


@cli.command()
def demo():
    """Run a demo with sample tasks"""
    orchestrator = Orchestrator()

    click.echo("🎭 Running demo with sample tasks...")

    # Submit sample tasks
    tasks = [
        ("Write a Python function to calculate fibonacci numbers", "claude", "high"),
        ("Create a simple TODO list in JavaScript", "codex", "normal"),
        ("Explain the difference between TCP and UDP", "any", "low"),
    ]

    task_ids = []
    for desc, agent, priority in tasks:
        task_id = orchestrator.submit_task(desc, agent, priority)
        task_ids.append(task_id)
        click.echo(f"  Submitted: {task_id} - {desc[:40]}...")

    click.echo("\n🚀 Processing tasks...")
    orchestrator.process_tasks(max_agents=2)

    click.echo("\n📊 Results:")
    for task_id in task_ids:
        task = orchestrator.queue.get_task(task_id)
        if task:
            status_icon = "✅" if task.status == "completed" else "❌"
            click.echo(f"  {status_icon} {task_id}: {task.status}")


if __name__ == "__main__":
    cli()
