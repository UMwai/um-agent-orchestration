"""
Interactive Planner - Head node for interactive task planning and refinement
Allows users to collaborate with Claude on planning before execution
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.task_decomposer import TaskDecomposer, Subtask
from .claude_cli_manager import get_claude_manager
from .file_operations import SessionFileManager


@dataclass
class PlanningSession:
    """Represents an interactive planning session"""

    session_id: str
    goal: str
    created_at: str
    subtasks: List[Subtask]
    iterations: List[Dict]  # History of planning iterations
    status: str  # 'planning', 'approved', 'executed'
    context: Dict = None


class InteractivePlanner:
    """Interactive planning head node for task orchestration"""

    def __init__(self, base_dir: str = "/tmp/agent_orchestrator"):
        self.decomposer = TaskDecomposer()
        self.sessions_dir = Path(base_dir) / "planning_sessions"
        self.session_manager = SessionFileManager(self.sessions_dir)

    def start_planning_session(
        self, goal: str, context: Dict = None
    ) -> PlanningSession:
        """Start a new interactive planning session"""
        session_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Get initial decomposition
        initial_subtasks = self.decomposer.decompose_task(goal)

        session = PlanningSession(
            session_id=session_id,
            goal=goal,
            created_at=datetime.now().isoformat(),
            subtasks=initial_subtasks,
            iterations=[
                {
                    "timestamp": datetime.now().isoformat(),
                    "action": "initial_decomposition",
                    "subtasks": [asdict(st) for st in initial_subtasks],
                }
            ],
            status="planning",
            context=context or {},
        )

        # Save session
        self._save_session(session)
        return session

    def discuss_approach(self, session: PlanningSession, user_input: str) -> str:
        """Have Claude discuss the planning approach with the user"""

        # Build context about current plan
        plan_context = self._format_plan_for_discussion(session)

        prompt = f"""You are a planning assistant helping to refine a task execution plan.

Current Goal: {session.goal}

Current Plan:
{plan_context}

User Feedback/Question: {user_input}

Provide a thoughtful response discussing:
1. How the feedback could improve the plan
2. Any potential issues or considerations
3. Specific recommendations for plan modification
4. Trade-offs between different approaches

Be concise but thorough. Format your response for readability."""

        response = self._call_claude(prompt)

        # Log the discussion
        session.iterations.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "discussion",
                "user_input": user_input,
                "claude_response": response,
            }
        )

        self._save_session(session)
        return response

    def refine_plan(
        self, session: PlanningSession, refinement_type: str, details: Dict
    ) -> PlanningSession:
        """Refine the plan based on user input"""

        if refinement_type == "add_task":
            new_task = Subtask(
                description=details["description"],
                agent_type=details.get("agent_type", "claude"),
                dependencies=details.get("dependencies", []),
                context_needed=details.get("context_needed", []),
            )
            session.subtasks.insert(
                details.get("position", len(session.subtasks)), new_task
            )

        elif refinement_type == "remove_task":
            task_index = details["task_index"]
            if 0 <= task_index < len(session.subtasks):
                removed = session.subtasks.pop(task_index)
                # Update dependencies in remaining tasks
                for task in session.subtasks:
                    if task.dependencies and removed.description in task.dependencies:
                        task.dependencies.remove(removed.description)

        elif refinement_type == "modify_task":
            task_index = details["task_index"]
            if 0 <= task_index < len(session.subtasks):
                task = session.subtasks[task_index]
                if "description" in details:
                    task.description = details["description"]
                if "agent_type" in details:
                    task.agent_type = details["agent_type"]
                if "dependencies" in details:
                    task.dependencies = details["dependencies"]

        elif refinement_type == "reorder":
            old_index = details["old_index"]
            new_index = details["new_index"]
            if 0 <= old_index < len(session.subtasks) and 0 <= new_index < len(
                session.subtasks
            ):
                task = session.subtasks.pop(old_index)
                session.subtasks.insert(new_index, task)

        elif refinement_type == "split_task":
            task_index = details["task_index"]
            if 0 <= task_index < len(session.subtasks):
                original_task = session.subtasks[task_index]
                # Use Claude to split the task
                split_tasks = self._split_task(
                    original_task, details.get("split_count", 2)
                )
                # Replace original with split tasks
                session.subtasks[task_index : task_index + 1] = split_tasks

        # Log the refinement
        session.iterations.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": f"refinement_{refinement_type}",
                "details": details,
                "subtasks": [asdict(st) for st in session.subtasks],
            }
        )

        self._save_session(session)
        return session

    def visualize_plan(self, session: PlanningSession) -> str:
        """Create ASCII visualization of the plan with dependencies"""
        if not session.subtasks:
            return "No tasks in plan"

        # Create execution phases
        phases = self.decomposer.create_execution_plan(session.subtasks)

        output = []
        output.append("=" * 70)
        output.append(f"EXECUTION PLAN: {session.goal}")
        output.append("=" * 70)
        output.append("")

        total_tasks = len(session.subtasks)
        output.append(f"Total Tasks: {total_tasks}")
        output.append(f"Execution Phases: {len(phases)}")
        output.append(f"Status: {session.status.upper()}")
        output.append("")

        # Show phases
        for phase_num, phase in enumerate(phases, 1):
            output.append(f"{'─' * 70}")
            output.append(f"PHASE {phase_num} (Parallel Execution)")
            output.append(f"{'─' * 70}")

            for i, task in enumerate(phase, 1):
                agent_icon = self._get_agent_icon(task.agent_type)
                output.append(f"  {agent_icon} [{task.agent_type}]")
                output.append(f"     └─ {task.description}")

                if task.dependencies:
                    output.append(
                        f"        Dependencies: {', '.join(task.dependencies[:2])}"
                    )
                    if len(task.dependencies) > 2:
                        output.append(
                            f"                     and {len(task.dependencies)-2} more..."
                        )

                if task.context_needed:
                    output.append(
                        f"        Context: {', '.join(task.context_needed[:2])}"
                    )
            output.append("")

        # Show estimated execution stats
        output.append("=" * 70)
        output.append("EXECUTION ESTIMATES")
        output.append("=" * 70)
        output.append(
            f"Max concurrent agents needed: {max(len(phase) for phase in phases)}"
        )
        output.append(f"Sequential phases: {len(phases)}")

        # Count agent types
        agent_counts = {}
        for task in session.subtasks:
            agent_counts[task.agent_type] = agent_counts.get(task.agent_type, 0) + 1

        output.append("\nAgent allocation:")
        for agent_type, count in sorted(
            agent_counts.items(), key=lambda x: x[1], reverse=True
        ):
            output.append(f"  • {agent_type}: {count} task(s)")

        return "\n".join(output)

    def get_approval_summary(self, session: PlanningSession) -> str:
        """Generate a summary for final approval"""
        phases = self.decomposer.create_execution_plan(session.subtasks)

        summary = []
        summary.append("=" * 70)
        summary.append("PLAN APPROVAL SUMMARY")
        summary.append("=" * 70)
        summary.append(f"\nGoal: {session.goal}")
        summary.append(f"Total tasks: {len(session.subtasks)}")
        summary.append(f"Execution phases: {len(phases)}")
        summary.append(f"Planning iterations: {len(session.iterations)}")

        summary.append("\n" + "─" * 70)
        summary.append("TASK BREAKDOWN:")
        summary.append("─" * 70)

        for i, task in enumerate(session.subtasks, 1):
            summary.append(f"\n{i}. {task.description}")
            summary.append(f"   Agent: {task.agent_type}")
            if task.dependencies:
                summary.append(f"   Depends on: {', '.join(task.dependencies)}")

        summary.append("\n" + "─" * 70)
        summary.append("EXECUTION STRATEGY:")
        summary.append("─" * 70)

        for phase_num, phase in enumerate(phases, 1):
            task_descriptions = [
                f"{t.agent_type}: {t.description[:40]}..." for t in phase
            ]
            summary.append(f"\nPhase {phase_num} (Parallel):")
            for desc in task_descriptions:
                summary.append(f"  • {desc}")

        summary.append("\n" + "=" * 70)
        summary.append("Ready to execute this plan? (yes/no/refine)")

        return "\n".join(summary)

    def approve_plan(self, session: PlanningSession) -> bool:
        """Mark plan as approved and ready for execution"""
        session.status = "approved"
        session.iterations.append(
            {"timestamp": datetime.now().isoformat(), "action": "plan_approved"}
        )
        self._save_session(session)
        return True

    def load_session(self, session_id: str) -> Optional[PlanningSession]:
        """Load an existing planning session"""
        data = self.session_manager.load_session(session_id)
        if not data:
            return None

        # Reconstruct Subtask objects
        subtasks = [
            Subtask(
                description=st["description"],
                agent_type=st.get("agent_type", "claude"),
                dependencies=st.get("dependencies"),
                context_needed=st.get("context_needed"),
            )
            for st in data["subtasks"]
        ]

        return PlanningSession(
            session_id=data["session_id"],
            goal=data["goal"],
            created_at=data["created_at"],
            subtasks=subtasks,
            iterations=data["iterations"],
            status=data["status"],
            context=data.get("context", {}),
        )

    def list_sessions(self) -> List[Dict]:
        """List all planning sessions"""
        sessions = self.session_manager.list_sessions()
        return [
            {
                "session_id": session["session_id"],
                "goal": session["goal"],
                "created_at": session["created_at"],
                "status": session["status"],
                "task_count": len(session["subtasks"]),
            }
            for session in sessions
        ]

    def _save_session(self, session: PlanningSession):
        """Save session to disk"""
        # Convert to dict for JSON serialization
        data = {
            "session_id": session.session_id,
            "goal": session.goal,
            "created_at": session.created_at,
            "subtasks": [asdict(st) for st in session.subtasks],
            "iterations": session.iterations,
            "status": session.status,
            "context": session.context,
        }

        self.session_manager.save_session(session.session_id, data)

    def _format_plan_for_discussion(self, session: PlanningSession) -> str:
        """Format the current plan for discussion with Claude"""
        lines = []
        for i, task in enumerate(session.subtasks, 1):
            lines.append(f"{i}. [{task.agent_type}] {task.description}")
            if task.dependencies:
                lines.append(f"   Dependencies: {', '.join(task.dependencies)}")
        return "\n".join(lines)

    def _call_claude(self, prompt: str) -> str:
        """Call Claude CLI for planning assistance"""
        claude_manager = get_claude_manager()
        response = claude_manager.call_claude(prompt, timeout=30)

        if response.success:
            return response.content
        else:
            return response.error or "Failed to get response from Claude."

    def _split_task(self, task: Subtask, split_count: int) -> List[Subtask]:
        """Split a task into multiple subtasks"""
        prompt = f"""Split this task into {split_count} smaller, more focused subtasks:

Task: {task.description}
Agent Type: {task.agent_type}

Return a JSON array of subtasks with the same format as before.
Each subtask should be a logical part of the original task."""

        claude_manager = get_claude_manager()
        subtasks_data = claude_manager.call_claude_for_json(prompt, fallback_data=[])

        if subtasks_data:
            return [
                Subtask(
                    description=st["description"],
                    agent_type=st.get("agent_type", task.agent_type),
                    dependencies=st.get("dependencies", task.dependencies),
                    context_needed=st.get("context_needed", task.context_needed),
                )
                for st in subtasks_data
            ]
        else:
            # Fallback: simple split
            return [
                Subtask(
                    description=f"{task.description} - Part {i+1}",
                    agent_type=task.agent_type,
                    dependencies=task.dependencies
                    if i == 0
                    else [f"{task.description} - Part {i}"],
                    context_needed=task.context_needed,
                )
                for i in range(split_count)
            ]

    def _get_agent_icon(self, agent_type: str) -> str:
        """Get icon for agent type"""
        icons = {
            "backend-systems-engineer": "⚙️",
            "frontend-ui-engineer": "🎨",
            "data-pipeline-engineer": "🔄",
            "data-science-analyst": "📊",
            "aws-cloud-architect": "☁️",
            "ml-systems-architect": "🤖",
            "specifications-engineer": "📋",
            "project-delivery-manager": "📅",
            "llm-architect": "🧠",
            "data-architect-governance": "🏗️",
            "claude": "🤔",
            "codex": "💻",
        }
        return icons.get(agent_type, "📦")


if __name__ == "__main__":
    # Test the interactive planner
    planner = InteractivePlanner()

    # Start a planning session
    session = planner.start_planning_session("Build a REST API for user management")

    print("Created planning session:", session.session_id)
    print("\nInitial plan visualization:")
    print(planner.visualize_plan(session))

    # Simulate discussion
    response = planner.discuss_approach(
        session, "Should we add rate limiting and caching to the API?"
    )
    print("\nClaude's response:", response)

    # Get approval summary
    print("\nApproval summary:")
    print(planner.get_approval_summary(session))
