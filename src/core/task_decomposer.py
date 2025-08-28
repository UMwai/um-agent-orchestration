"""
Task Decomposer - Breaks high-level tasks into subtasks
Uses an LLM to intelligently decompose tasks
"""

import json
import subprocess
from typing import List
from dataclasses import dataclass


@dataclass
class Subtask:
    description: str
    agent_type: str  # 'claude' or 'codex'
    dependencies: List[str] = None
    context_needed: List[str] = None


class TaskDecomposer:
    """Breaks down high-level tasks into executable subtasks"""

    def decompose_task(
        self, task_description: str, max_subtasks: int = 5
    ) -> List[Subtask]:
        """
        Use Claude to decompose a high-level task into subtasks
        """
        prompt = f"""Break down this task into {max_subtasks} or fewer specific subtasks.
        
Task: {task_description}

For each subtask, specify:
1. A clear, actionable description
2. Which agent type is best suited (claude for analysis/design, codex for implementation)
3. Any dependencies on other subtasks
4. What context it needs from other subtasks

Return as JSON array with format:
[
  {{
    "description": "Specific actionable task",
    "agent_type": "claude|codex",
    "dependencies": ["subtask_1", "subtask_2"],
    "context_needed": ["database_schema", "api_design"]
  }}
]

Focus on practical implementation steps. Be specific and actionable."""

        # Use Claude to decompose the task
        result = self._call_claude(prompt)

        try:
            subtasks_data = json.loads(result)
            return [
                Subtask(
                    description=st["description"],
                    agent_type=st.get("agent_type", "any"),
                    dependencies=st.get("dependencies", []),
                    context_needed=st.get("context_needed", []),
                )
                for st in subtasks_data
            ]
        except (json.JSONDecodeError, KeyError):
            # Fallback to simple decomposition
            return self._simple_decompose(task_description)

    def _call_claude(self, prompt: str) -> str:
        """Call Claude CLI to decompose the task"""
        try:
            result = subprocess.run(
                ["claude", "--dangerously-skip-permissions", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback response
        return "[]"

    def _simple_decompose(self, task_description: str) -> List[Subtask]:
        """Simple heuristic-based task decomposition"""
        subtasks = []

        task_lower = task_description.lower()

        # Common patterns
        if "build" in task_lower or "create" in task_lower:
            if "app" in task_lower or "application" in task_lower:
                subtasks = [
                    Subtask("Design the data model and architecture", "claude"),
                    Subtask("Implement the backend/API", "codex"),
                    Subtask("Create the frontend/UI", "codex"),
                    Subtask("Write tests", "codex"),
                    Subtask("Create documentation", "claude"),
                ]
            elif "api" in task_lower:
                subtasks = [
                    Subtask("Design API endpoints and data structures", "claude"),
                    Subtask("Implement API handlers", "codex"),
                    Subtask("Add authentication/authorization", "codex"),
                    Subtask("Write API tests", "codex"),
                ]
            elif "website" in task_lower or "page" in task_lower:
                subtasks = [
                    Subtask("Create HTML structure", "codex"),
                    Subtask("Style with CSS", "codex"),
                    Subtask("Add JavaScript functionality", "codex"),
                ]
        elif "fix" in task_lower or "debug" in task_lower:
            subtasks = [
                Subtask("Analyze and identify the issue", "claude"),
                Subtask("Implement the fix", "codex"),
                Subtask("Test the fix", "codex"),
            ]
        elif "refactor" in task_lower:
            subtasks = [
                Subtask("Analyze current code structure", "claude"),
                Subtask("Plan refactoring approach", "claude"),
                Subtask("Implement refactoring", "codex"),
                Subtask("Update tests", "codex"),
            ]
        else:
            # Generic decomposition
            subtasks = [
                Subtask(f"Analyze requirements for: {task_description}", "claude"),
                Subtask(f"Implement: {task_description}", "codex"),
                Subtask(f"Test and validate: {task_description}", "codex"),
            ]

        return subtasks

    def create_execution_plan(self, subtasks: List[Subtask]) -> List[List[Subtask]]:
        """
        Create execution phases based on dependencies
        Returns list of phases, each phase contains tasks that can run in parallel
        """
        phases = []
        completed = set()
        remaining = subtasks.copy()

        while remaining:
            phase = []
            for task in remaining[:]:
                # Check if all dependencies are completed
                deps = task.dependencies or []
                if all(dep in completed for dep in deps):
                    phase.append(task)
                    remaining.remove(task)

            if not phase:
                # No progress made, just add remaining tasks
                phases.append(remaining)
                break

            phases.append(phase)
            for task in phase:
                completed.add(task.description)

        return phases


if __name__ == "__main__":
    # Test the decomposer
    decomposer = TaskDecomposer()

    # Test with a high-level task
    task = "Build a todo list application with user authentication"
    print(f"Original task: {task}\n")

    subtasks = decomposer.decompose_task(task)
    print("Decomposed into subtasks:")
    for i, st in enumerate(subtasks, 1):
        print(f"{i}. [{st.agent_type}] {st.description}")
        if st.dependencies:
            print(f"   Dependencies: {st.dependencies}")
        if st.context_needed:
            print(f"   Context needed: {st.context_needed}")

    # Create execution plan
    phases = decomposer.create_execution_plan(subtasks)
    print("\nExecution phases:")
    for i, phase in enumerate(phases, 1):
        print(f"Phase {i}:")
        for task in phase:
            print(f"  - [{task.agent_type}] {task.description}")
