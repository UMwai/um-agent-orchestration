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
from src.core.interactive_planner import InteractivePlanner, PlanningSession
from src.core.feedback_orchestrator import FeedbackOrchestrator, SuccessCriteria
from src.core.input_validator import InputValidator, ValidationError


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
        """Submit a new task with input validation"""
        try:
            # Validate and sanitize inputs
            safe_description = InputValidator.sanitize_task_description(description)
            safe_agent_type = InputValidator.validate_agent_type(agent_type)
            safe_priority = InputValidator.validate_priority(priority)

            # Validate context if provided
            if context is not None:
                if not isinstance(context, dict):
                    raise ValidationError("Context must be a dictionary")
                # Validate context structure
                InputValidator._validate_json_values(context)

        except ValidationError as e:
            raise ValueError(f"Invalid input: {e}")

        priority_map = {
            "high": Priority.HIGH,
            "normal": Priority.NORMAL,
            "low": Priority.LOW,
        }

        task_id = self.queue.add_task(
            description=safe_description,
            agent_type=safe_agent_type,
            priority=priority_map.get(safe_priority, Priority.NORMAL),
            context=context,
        )

        if context:
            self.context.set_task_context(task_id, context)

        return task_id

    def process_tasks(self, max_agents: int = 3):
        """Process tasks from queue"""
        existing_agents = [agent for agent in self.spawner.get_all_agents() if agent]
        active_agent_ids = {agent["agent_id"] for agent in existing_agents}
        requeued = self.queue.requeue_orphaned_tasks(
            active_agent_ids=active_agent_ids,
            force=not active_agent_ids,
        )
        if requeued:
            click.echo(f"♻️  Requeued {requeued} orphaned tasks")

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
                            try:
                                agent_id = self.spawner.spawn_agent(
                                    agent_type=agent_type,
                                    task_id=task.id,
                                    task_description=task.description,
                                    context=task.context,
                                )
                            except Exception as exc:
                                # Return task to queue and record failure reason
                                self.queue.update_status(
                                    task.id,
                                    TaskStatus.PENDING,
                                    error=f"Spawn failed: {exc}",
                                )
                                click.echo(
                                    f"❌ Failed to spawn agent for task {task.id}: {exc}",
                                    err=True,
                                )
                                continue

                            self.queue.update_assigned_agent(task.id, agent_id)
                            self.queue.update_status(task.id, TaskStatus.IN_PROGRESS)

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

    # Validate inputs first
    try:
        # Basic validation of required fields
        if not description or not description.strip():
            click.echo("❌ Task description cannot be empty", err=True)
            return

        # Validate agent type
        InputValidator.validate_agent_type(agent)
        # Validate priority
        InputValidator.validate_priority(priority)

    except ValidationError as e:
        click.echo(f"❌ Validation error: {e}", err=True)
        return

    context_dict = None
    if context:
        try:
            context_dict = InputValidator.validate_json_context(context)
        except ValidationError as e:
            click.echo(f"❌ Invalid JSON context: {e}", err=True)
            return

    try:
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
                # Create safe subtask context
                subtask_context = {
                    "parent_task": description[:100],  # Limit length
                    "subtask_index": i,
                }
                task_id = orchestrator.submit_task(
                    subtask.description,
                    subtask.agent_type,
                    priority,
                    subtask_context,
                )
                task_ids.append(task_id)
                click.echo(
                    f"  {i}. [{subtask.agent_type}] {subtask.description} - {task_id}"
                )

            click.echo(f"✅ Submitted {len(task_ids)} subtasks")
        else:
            task_id = orchestrator.submit_task(
                description, agent, priority, context_dict
            )
            click.echo(f"✅ Task submitted: {task_id}")

    except ValueError as e:
        click.echo(f"❌ Error submitting task: {e}", err=True)
        return


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


@cli.command()
@click.argument("description")
@click.option("--context", "-c", help="JSON context for the planning session")
def plan(description, context):
    """Start an interactive planning session with the head node"""
    planner = InteractivePlanner()

    # Validate description first
    try:
        if not description or not description.strip():
            click.echo("❌ Planning description cannot be empty", err=True)
            return

        # Sanitize description
        safe_description = InputValidator.sanitize_task_description(description)
    except ValidationError as e:
        click.echo(f"❌ Invalid planning description: {e}", err=True)
        return

    # Parse context if provided
    context_dict = None
    if context:
        try:
            context_dict = InputValidator.validate_json_context(context)
        except ValidationError as e:
            click.echo(f"❌ Invalid JSON context: {e}", err=True)
            return

    # Start planning session
    click.echo("🎯 Starting Interactive Planning Session")
    click.echo("=" * 70)
    click.echo(f"Goal: {safe_description}")
    click.echo("=" * 70)
    click.echo("\n🤖 Claude is analyzing and creating initial task decomposition...\n")

    session = planner.start_planning_session(safe_description, context_dict)

    # Main planning loop
    while session.status == "planning":
        # Show current plan
        click.echo(planner.visualize_plan(session))
        click.echo("\n" + "─" * 70)

        # Show options
        click.echo("\n📋 Planning Options:")
        click.echo("  [d] Discuss approach with Claude")
        click.echo("  [a] Add a new task")
        click.echo("  [r] Remove a task")
        click.echo("  [m] Modify a task")
        click.echo("  [s] Split a task into subtasks")
        click.echo("  [o] Reorder tasks")
        click.echo("  [v] View detailed plan")
        click.echo("  [p] Proceed to approval")
        click.echo("  [q] Quit without saving")
        click.echo("  [save] Save session for later")

        choice = click.prompt("\nYour choice", type=str).lower().strip()

        if choice == "d":
            # Discuss with Claude
            user_input = click.prompt(
                "\n💬 What would you like to discuss about the plan?"
            )

            # Validate user input
            try:
                safe_user_input = InputValidator.sanitize_task_description(user_input)
            except ValidationError as e:
                click.echo(f"❌ Invalid input: {e}", err=True)
                continue

            click.echo("\n🤖 Claude is thinking...")
            response = planner.discuss_approach(session, safe_user_input)
            click.echo("\n" + "─" * 70)
            click.echo("Claude's Response:")
            click.echo("─" * 70)
            click.echo(response)
            click.echo("─" * 70)
            click.prompt("\nPress Enter to continue")

        elif choice == "a":
            # Add task
            task_desc = click.prompt("Task description")
            agent_type = click.prompt("Agent type", default="claude")
            position = click.prompt(
                "Position (0 for beginning, -1 for end)", type=int, default=-1
            )

            # Validate inputs
            try:
                safe_task_desc = InputValidator.sanitize_task_description(task_desc)
                safe_agent_type = InputValidator.validate_agent_type(agent_type)
            except ValidationError as e:
                click.echo(f"❌ Invalid input: {e}", err=True)
                continue

            if position == -1:
                position = len(session.subtasks)

            session = planner.refine_plan(
                session,
                "add_task",
                {
                    "description": task_desc,
                    "agent_type": agent_type,
                    "position": position,
                },
            )
            click.echo("✅ Task added to plan")

        elif choice == "r":
            # Remove task
            for i, task in enumerate(session.subtasks):
                click.echo(f"{i}. [{task.agent_type}] {task.description}")

            task_index = click.prompt("\nTask number to remove", type=int)
            session = planner.refine_plan(
                session, "remove_task", {"task_index": task_index}
            )
            click.echo("✅ Task removed from plan")

        elif choice == "m":
            # Modify task
            for i, task in enumerate(session.subtasks):
                click.echo(f"{i}. [{task.agent_type}] {task.description}")

            task_index = click.prompt("\nTask number to modify", type=int)

            if 0 <= task_index < len(session.subtasks):
                current_task = session.subtasks[task_index]
                click.echo(f"\nCurrent: {current_task.description}")
                new_desc = click.prompt(
                    "New description (Enter to keep current)",
                    default=current_task.description,
                )
                new_agent = click.prompt(
                    "New agent type (Enter to keep current)",
                    default=current_task.agent_type,
                )

                session = planner.refine_plan(
                    session,
                    "modify_task",
                    {
                        "task_index": task_index,
                        "description": new_desc,
                        "agent_type": new_agent,
                    },
                )
                click.echo("✅ Task modified")

        elif choice == "s":
            # Split task
            for i, task in enumerate(session.subtasks):
                click.echo(f"{i}. [{task.agent_type}] {task.description}")

            task_index = click.prompt("\nTask number to split", type=int)
            split_count = click.prompt(
                "Split into how many tasks?", type=int, default=2
            )

            session = planner.refine_plan(
                session,
                "split_task",
                {"task_index": task_index, "split_count": split_count},
            )
            click.echo("✅ Task split successfully")

        elif choice == "o":
            # Reorder tasks
            for i, task in enumerate(session.subtasks):
                click.echo(f"{i}. [{task.agent_type}] {task.description}")

            old_index = click.prompt("\nTask to move", type=int)
            new_index = click.prompt("Move to position", type=int)

            session = planner.refine_plan(
                session, "reorder", {"old_index": old_index, "new_index": new_index}
            )
            click.echo("✅ Tasks reordered")

        elif choice == "v":
            # View detailed plan
            click.echo("\n" + planner.visualize_plan(session))
            click.prompt("\nPress Enter to continue")

        elif choice == "p":
            # Proceed to approval
            click.echo("\n" + planner.get_approval_summary(session))

            approval = click.prompt(
                "\n🚀 Execute this plan?",
                type=click.Choice(["yes", "no", "refine"]),
                default="no",
            )

            if approval == "yes":
                planner.approve_plan(session)
                click.echo("\n✅ Plan approved!")
                click.echo(f"Session ID: {session.session_id}")

                # Ask if they want to execute immediately
                execute_now = click.confirm("\n🚀 Execute plan now?")
                if execute_now:
                    _execute_plan_from_session(session)
                else:
                    click.echo(
                        f"\nTo execute later, run: ./orchestrate execute-plan {session.session_id}"
                    )
                break

            elif approval == "refine":
                click.echo("\n↩️ Returning to planning mode...")
                continue
            else:
                click.echo("\n❌ Plan not approved. Continuing planning...")

        elif choice == "save":
            click.echo(f"\n💾 Session saved: {session.session_id}")
            click.echo(f"Resume with: ./orchestrate plan-continue {session.session_id}")
            break

        elif choice == "q":
            if click.confirm("\n⚠️ Quit without saving?"):
                click.echo("Planning session abandoned")
                break
        else:
            click.echo("❌ Invalid choice. Please try again.")


@cli.command()
@click.argument("session_id")
def plan_continue(session_id):
    """Continue an existing planning session"""
    planner = InteractivePlanner()

    session = planner.load_session(session_id)
    if not session:
        click.echo(f"❌ Session {session_id} not found", err=True)
        return

    click.echo(f"📂 Resuming planning session: {session_id}")
    click.echo(f"Goal: {session.goal}")
    click.echo(f"Status: {session.status}")
    click.echo(f"Tasks: {len(session.subtasks)}")

    # If already approved, ask if they want to execute
    if session.status == "approved":
        if click.confirm("\n✅ This plan is already approved. Execute now?"):
            _execute_plan_from_session(session)
        return

    # Continue planning loop (reuse the same logic as plan command)
    # This is simplified - in production you'd refactor the common code
    click.echo("\nResuming planning...")
    # ... (planning loop code would go here, refactored from plan command)


@cli.command()
@click.argument("session_id")
def execute_plan(session_id):
    """Execute an approved plan from a planning session"""
    planner = InteractivePlanner()

    session = planner.load_session(session_id)
    if not session:
        click.echo(f"❌ Session {session_id} not found", err=True)
        return

    if session.status != "approved":
        click.echo(f"❌ Plan not approved. Current status: {session.status}", err=True)
        click.echo(f"Use './orchestrate plan-continue {session_id}' to finish planning")
        return

    _execute_plan_from_session(session)


@cli.command()
def plan_list():
    """List all planning sessions"""
    planner = InteractivePlanner()

    sessions = planner.list_sessions()
    if not sessions:
        click.echo("No planning sessions found")
        return

    click.echo("\n📋 Planning Sessions:")
    click.echo("=" * 80)

    for session in sessions:
        status_icon = {"planning": "🔄", "approved": "✅", "executed": "🚀"}.get(
            session["status"], "❓"
        )

        click.echo(f"\n{status_icon} {session['session_id']}")
        click.echo(f"   Goal: {session['goal'][:60]}...")
        click.echo(f"   Created: {session['created_at']}")
        click.echo(f"   Tasks: {session['task_count']}")
        click.echo(f"   Status: {session['status']}")

    click.echo("\n" + "=" * 80)
    click.echo("Use './orchestrate plan-continue <session-id>' to resume planning")
    click.echo(
        "Use './orchestrate execute-plan <session-id>' to execute approved plans"
    )


def _execute_plan_from_session(session: PlanningSession):
    """Helper function to execute tasks from a planning session"""
    orchestrator = Orchestrator()

    click.echo("\n🚀 Executing planned tasks...")
    click.echo("=" * 70)

    # Submit all tasks from the plan
    task_ids = []
    for i, subtask in enumerate(session.subtasks, 1):
        context = {
            "planning_session": session.session_id,
            "parent_goal": session.goal,
            "subtask_index": i,
            "total_subtasks": len(session.subtasks),
        }

        if subtask.context_needed:
            context["context_needed"] = subtask.context_needed

        task_id = orchestrator.submit_task(
            subtask.description, subtask.agent_type, "normal", context
        )
        task_ids.append(task_id)
        click.echo(
            f"  ✅ Submitted: [{subtask.agent_type}] {subtask.description[:50]}..."
        )

    click.echo(f"\n📊 Submitted {len(task_ids)} tasks from plan")

    # Ask if they want to start processing immediately
    if click.confirm("\n🎯 Start processing tasks now?"):
        max_agents = click.prompt("Maximum concurrent agents", type=int, default=3)
        click.echo(f"\n🚀 Starting orchestrator with max {max_agents} agents...")
        click.echo("Press Ctrl+C to stop\n")

        try:
            orchestrator.process_tasks(max_agents)
        except KeyboardInterrupt:
            click.echo("\n⚠️ Stopping orchestrator...")
            orchestrator.spawner.cleanup_all()
    else:
        click.echo("\nTasks queued. Run './orchestrate run' to start processing")


@cli.command()
@click.option("--port", "-p", default=3091, help="Port for web interface")
@click.option("--debug", is_flag=True, help="Run in debug mode")
@click.option(
    "--enhanced", is_flag=True, help="Use enhanced dashboard with feedback loop support"
)
def web(port, debug, enhanced):
    """Start web monitoring interface"""
    try:
        if enhanced:
            from src.core.enhanced_web_monitor import EnhancedWebMonitor

            monitor = EnhancedWebMonitor(port=port)
        else:
            from src.core.web_monitor import WebMonitor

            monitor = WebMonitor(port=port)
        monitor.run(debug=debug)
    except ImportError as e:
        if "flask" in str(e).lower():
            click.echo(
                "❌ Flask is required for web interface. Install with: pip install flask",
                err=True,
            )
        else:
            click.echo(f"❌ Import error: {e}", err=True)
    except KeyboardInterrupt:
        click.echo("\n⚠️  Stopping web server...")
    except Exception as e:
        click.echo(f"❌ Failed to start web server: {e}", err=True)


@cli.command("submit-validated")
@click.argument("description")
@click.option(
    "--criteria-type",
    "-ct",
    type=click.Choice(["threshold", "range", "multi_objective"]),
    default="threshold",
)
@click.option(
    "--domain",
    "-d",
    type=click.Choice(["financial", "data_science", "general"]),
    default="general",
)
@click.option("--agent", "-a", default="auto", help="Agent type")
@click.option("--max-iterations", "-i", default=5, help="Max refinement iterations")
@click.option(
    "--strategy",
    "-s",
    type=click.Choice(["adaptive", "grid_search"]),
    default="adaptive",
)
def submit_validated(
    description, criteria_type, domain, agent, max_iterations, strategy
):
    """Submit a task with success validation and feedback loop"""
    click.echo("🎯 Setting up success criteria...")

    criteria_params = {}
    criteria_desc = ""

    if domain == "financial":
        click.echo("\n📊 Financial metrics configuration:")
        if click.confirm("Set ROI target?"):
            roi_target = click.prompt("Target ROI (%)", type=float)
            criteria_params["roi"] = {"operator": ">", "value": roi_target}
            criteria_desc += f"ROI > {roi_target}%"

        if click.confirm("Set Sharpe ratio target?"):
            sharpe_target = click.prompt("Target Sharpe ratio", type=float)
            criteria_params["sharpe"] = {"operator": ">", "value": sharpe_target}
            criteria_desc += f", Sharpe > {sharpe_target}"

        if click.confirm("Set max drawdown limit?"):
            dd_limit = click.prompt("Max drawdown (%)", type=float)
            criteria_params["max_drawdown"] = {"operator": "<", "value": -abs(dd_limit)}
            criteria_desc += f", Max DD < {dd_limit}%"

    elif domain == "data_science":
        click.echo("\n🤖 ML metrics configuration:")
        if criteria_type == "threshold":
            if click.confirm("Set accuracy target?"):
                acc_target = click.prompt("Target accuracy (0-1)", type=float)
                criteria_params["accuracy"] = acc_target
                criteria_desc += f"Accuracy > {acc_target}"

            if click.confirm("Set F1 score target?"):
                f1_target = click.prompt("Target F1 score (0-1)", type=float)
                criteria_params["f1_score"] = f1_target
                criteria_desc += f", F1 > {f1_target}"

        elif criteria_type == "range":
            metric = click.prompt("Metric name (accuracy/precision/recall/f1)")
            min_val = click.prompt("Minimum value", type=float)
            max_val = click.prompt("Maximum value", type=float)
            criteria_params[metric] = {"min": min_val, "max": max_val}
            criteria_desc = f"{metric} in [{min_val}, {max_val}]"

    else:
        # General criteria - user defines
        criteria_desc = click.prompt("Describe success criteria")
        criteria_params = {"custom": criteria_desc}

    # Create success criteria
    criteria = SuccessCriteria(
        criteria_type=criteria_type,
        parameters=criteria_params,
        domain=domain,
        description=criteria_desc or "Custom criteria",
    )

    # Submit validated task
    orchestrator = FeedbackOrchestrator()
    task = orchestrator.submit_validated_task(
        description=description,
        success_criteria=criteria,
        agent_type=agent,
        max_iterations=max_iterations,
        refinement_strategy=strategy,
    )

    click.echo(f"\n✅ Validated task created: {task.task_id}")
    click.echo(f"📋 Success criteria: {criteria.description}")
    click.echo(f"🔄 Max iterations: {max_iterations}")
    click.echo(f"🎯 Strategy: {strategy}")

    if click.confirm("\n🚀 Start feedback loop now?"):
        click.echo("\n" + "=" * 50)
        results = orchestrator.process_feedback_loop(task.task_id)

        click.echo("\n" + "=" * 50)
        click.echo("📊 Final Results:")
        click.echo(f"Iterations: {results['iterations']}")
        click.echo(f"Status: {results['final_status']}")

        for result in results["results"]:
            click.echo(f"\nIteration {result['iteration']}: {result['evaluation']}")
            click.echo(f"Metrics: {json.dumps(result['metrics'], indent=2)}")
    else:
        click.echo(f"\nRun later: ./orchestrate feedback-run {task.task_id}")


@cli.command("feedback-run")
@click.argument("task_id")
def feedback_run(task_id):
    """Run feedback loop for a validated task"""
    orchestrator = FeedbackOrchestrator()

    click.echo(f"🔄 Starting feedback loop for task {task_id}")
    results = orchestrator.process_feedback_loop(task_id)

    if "error" in results:
        click.echo(f"❌ {results['error']}", err=True)
        return

    click.echo("\n" + "=" * 50)
    click.echo("📊 Final Results:")
    click.echo(f"Iterations: {results['iterations']}")
    click.echo(f"Status: {results['final_status']}")

    for result in results["results"]:
        click.echo(f"\nIteration {result['iteration']}: {result['evaluation']}")
        click.echo(f"Metrics: {json.dumps(result['metrics'], indent=2)}")


@cli.command("feedback-status")
@click.argument("task_id", required=False)
def feedback_status(task_id):
    """Check status of feedback loops"""
    orchestrator = FeedbackOrchestrator()

    if task_id:
        status = orchestrator.get_feedback_status(task_id)
        if "error" in status:
            click.echo(f"❌ {status['error']}", err=True)
            return

        click.echo(f"\n📋 Task: {status['description']}")
        click.echo(f"🎯 Criteria: {status['success_criteria']}")
        click.echo(f"🔄 Progress: {status['iterations']}")
        click.echo(f"📊 Status: {status['status']}")

        if status["history"]:
            click.echo("\n📈 History:")
            for entry in status["history"]:
                click.echo(f"  Iteration {entry['iteration']}: {entry['result']}")
    else:
        # List all validated tasks
        import sqlite3

        conn = sqlite3.connect("tasks.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT task_id, description, status, iteration_count, max_iterations
            FROM validated_tasks
            ORDER BY created_at DESC
            LIMIT 10
        """)

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            click.echo("No validated tasks found")
            return

        click.echo("\n📋 Recent Validated Tasks:")
        click.echo("-" * 80)

        for row in rows:
            task_id, desc, status, iters, max_iters = row
            click.echo(
                f"{task_id[:8]}... | {status:10} | {iters}/{max_iters} | {desc[:40]}..."
            )


if __name__ == "__main__":
    cli()
