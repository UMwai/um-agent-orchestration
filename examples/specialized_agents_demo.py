#!/usr/bin/env python3
"""
Demo script showing how the orchestrator uses Claude's specialized agents
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.agent_spawner import AgentSpawner, AgentType
from src.core.task_decomposer import TaskDecomposer
import time


def demo_specialized_agents():
    """Demonstrate using different specialized agents"""

    print("=== Claude Specialized Agents Demo ===\n")

    # Initialize spawner
    spawner = AgentSpawner()

    # Example tasks for different specialized agents
    tasks = [
        {
            "type": AgentType.DATA_PIPELINE,
            "description": "Design a data pipeline to ingest CSV files from S3, transform them, and load into a data warehouse",
        },
        {
            "type": AgentType.BACKEND_ENGINEER,
            "description": "Build a REST API endpoint for user authentication with JWT tokens",
        },
        {
            "type": AgentType.FRONTEND_ENGINEER,
            "description": "Create a responsive React component for a user dashboard",
        },
        {
            "type": AgentType.AWS_ARCHITECT,
            "description": "Design infrastructure for a highly available web application on AWS",
        },
        {
            "type": AgentType.ML_ARCHITECT,
            "description": "Design an ML pipeline for real-time fraud detection",
        },
        {
            "type": AgentType.SPECS_ENGINEER,
            "description": "Convert these vague requirements into clear specifications: 'We need a better way to track customer orders'",
        },
    ]

    print("Spawning specialized agents for different tasks:\n")

    agent_ids = []
    for i, task in enumerate(tasks, 1):
        print(f"{i}. Spawning {task['type'].value} agent")
        print(f"   Task: {task['description'][:80]}...")

        agent_id = spawner.spawn_agent(
            agent_type=task["type"],
            task_id=f"demo-{i}",
            task_description=task["description"],
        )
        agent_ids.append(agent_id)
        print(f"   Agent ID: {agent_id}\n")

    print("\nAgents are running. Waiting for completion...\n")

    # Wait for agents to complete (with timeout)
    max_wait = 60
    start = time.time()

    while time.time() - start < max_wait:
        all_done = True
        for agent_id in agent_ids:
            status = spawner.get_agent_status(agent_id)
            if status and status["running"]:
                all_done = False
                break

        if all_done:
            break

        time.sleep(2)

    print("\n=== Results ===\n")

    # Show results
    for agent_id in agent_ids:
        status = spawner.get_agent_status(agent_id)
        if status:
            print(f"Agent: {status['agent_type']}")
            print(f"Status: {status['status']}")

            output = spawner.get_agent_output(agent_id)
            if output:
                print(f"Output preview: {output[:200]}...")
            print("-" * 40)

    # Cleanup
    spawner.cleanup_all()
    print("\nDemo complete!")


def demo_task_decomposition():
    """Demonstrate automatic task decomposition with specialized agents"""

    print("\n=== Task Decomposition with Specialized Agents ===\n")

    decomposer = TaskDecomposer()

    # High-level task
    task = "Build a real-time analytics dashboard with machine learning predictions for e-commerce sales"

    print(f"Original task: {task}\n")
    print("Decomposing into subtasks with specialized agents...\n")

    subtasks = decomposer.decompose_task(task)

    for i, subtask in enumerate(subtasks, 1):
        print(f"{i}. [{subtask.agent_type}]")
        print(f"   {subtask.description}")
        if subtask.dependencies:
            print(f"   Dependencies: {', '.join(subtask.dependencies)}")
        print()

    # Create execution plan
    phases = decomposer.create_execution_plan(subtasks)

    print("\nExecution phases (tasks in each phase run in parallel):\n")
    for i, phase in enumerate(phases, 1):
        print(f"Phase {i}:")
        for task in phase:
            print(f"  - [{task.agent_type}] {task.description[:60]}...")
        print()


if __name__ == "__main__":
    print(
        "This demo shows how the orchestrator leverages Claude's specialized agents\n"
    )
    print(
        "The system will use Claude CLI to spawn specialized agents via the Task tool\n"
    )

    # Run demos
    demo_specialized_agents()
    demo_task_decomposition()
