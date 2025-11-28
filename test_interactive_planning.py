#!/usr/bin/env python3
"""
Test script for the interactive planning feature
Demonstrates the head node planning workflow
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.interactive_planner import InteractivePlanner


def main():
    print("=" * 70)
    print("INTERACTIVE PLANNING DEMO")
    print("=" * 70)
    print("\nThis demonstrates the new head node planning capability.")
    print("The planner allows you to:")
    print("  • Discuss plans with Claude before execution")
    print("  • Refine and modify task decomposition")
    print("  • Visualize dependencies and execution phases")
    print("  • Approve plans before launching agents")
    print()

    planner = InteractivePlanner()

    # Example 1: Start a planning session
    goal = "Build a blog platform with user authentication and comments"
    print(f"📋 Planning Goal: {goal}\n")

    session = planner.start_planning_session(goal)
    print(f"✅ Created planning session: {session.session_id}\n")

    # Show initial plan
    print("Initial Plan Visualization:")
    print("─" * 70)
    print(planner.visualize_plan(session))
    print()

    # Example 2: Discuss the plan with Claude
    print("💬 Discussing with Claude about adding caching...")
    print("─" * 70)
    response = planner.discuss_approach(
        session, "Should we add Redis caching for blog posts and user sessions?"
    )
    print(response)
    print()

    # Example 3: Add a task based on discussion
    print("📝 Adding caching task based on Claude's recommendation...")
    session = planner.refine_plan(
        session,
        "add_task",
        {
            "description": "Implement Redis caching for posts and sessions",
            "agent_type": "backend-systems-engineer",
            "position": 3,
        },
    )
    print("✅ Task added\n")

    # Example 4: Show approval summary
    print("Final Plan for Approval:")
    print("─" * 70)
    print(planner.get_approval_summary(session))
    print()

    # Example 5: Approve the plan
    print("✅ Approving plan...")
    planner.approve_plan(session)
    print(f"Plan approved and saved as: {session.session_id}")
    print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\n✨ The interactive planning system is ready!")
    print("\nTo use it with the CLI:")
    print("  1. Start planning:     ./orchestrate plan 'Your project goal'")
    print("  2. List sessions:      ./orchestrate plan-list")
    print("  3. Resume planning:    ./orchestrate plan-continue <session-id>")
    print("  4. Execute approved:   ./orchestrate execute-plan <session-id>")
    print("\nThe head node will:")
    print("  • Interactively discuss and refine plans with you")
    print("  • Get your approval before launching any agents")
    print("  • Coordinate the execution of approved plans")
    print("  • Maintain context across planning and execution phases")


if __name__ == "__main__":
    main()
