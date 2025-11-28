"""
Task Decomposer - Breaks high-level tasks into subtasks
Uses an LLM to intelligently decompose tasks
"""

from typing import List
from dataclasses import dataclass

from .agent_types import AgentType, AgentCapabilities
from .exceptions import validate_not_empty, safe_execute
from .claude_cli_manager import get_claude_manager


@dataclass
class Subtask:
    description: str
    agent_type: str  # Agent type: claude, codex, or specialized agents
    dependencies: List[str] = None
    context_needed: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.context_needed is None:
            self.context_needed = []


class TaskDecomposer:
    """Breaks down high-level tasks into executable subtasks"""

    def decompose_task(
        self, task_description: str, max_subtasks: int = 5
    ) -> List[Subtask]:
        """
        Use Claude to decompose a high-level task into subtasks
        """
        task_description = validate_not_empty(task_description, "task description")

        prompt = self._build_decomposition_prompt(task_description, max_subtasks)

        # Try LLM decomposition first
        result = self._call_claude(prompt)

        llm_subtasks = safe_execute(
            lambda: self._parse_llm_response(result), default=None
        )

        # Fallback to heuristic decomposition if LLM fails
        return llm_subtasks or self._heuristic_decompose(task_description)

    def _build_decomposition_prompt(
        self, task_description: str, max_subtasks: int
    ) -> str:
        """Build the prompt for task decomposition"""
        agent_types = [t.value for t in AgentType]
        claude_manager = get_claude_manager()
        return claude_manager.create_decomposition_prompt(
            task_description, max_subtasks, agent_types
        )

    def _call_claude(self, prompt: str) -> str:
        """Call Claude CLI to decompose the task"""
        claude_manager = get_claude_manager()
        response = claude_manager.call_claude(prompt)
        return response.content if response.success else "[]"

    def _parse_llm_response(self, response: str) -> List[Subtask]:
        """Parse LLM response into Subtask objects"""
        from .claude_cli_manager import ClaudeResponse

        claude_manager = get_claude_manager()
        mock_response = ClaudeResponse(success=True, content=response)
        subtasks_data = claude_manager.parse_json_response(mock_response)

        if not subtasks_data:
            return []

        return [
            Subtask(
                description=st["description"],
                agent_type=st.get("agent_type", "claude"),
                dependencies=st.get("dependencies", []),
                context_needed=st.get("context_needed", []),
            )
            for st in subtasks_data
        ]

    def _heuristic_decompose(self, task_description: str) -> List[Subtask]:
        """Simple heuristic-based task decomposition"""
        recommended_agent = AgentCapabilities.recommend_agent(task_description)
        task_lower = task_description.lower()

        # Use predefined templates for common patterns
        templates = {
            "app_build": [
                (
                    "Gather requirements and create specifications",
                    "specifications-engineer",
                ),
                ("Design architecture and data model", "data-architect-governance"),
                ("Implement backend/API", "backend-systems-engineer"),
                ("Create frontend/UI", "frontend-ui-engineer"),
                ("Write tests and documentation", recommended_agent.value),
            ],
            "api_build": [
                ("Design API endpoints", "specifications-engineer"),
                ("Implement API handlers", "backend-systems-engineer"),
                ("Add authentication", "backend-systems-engineer"),
                ("Write API tests", "backend-systems-engineer"),
            ],
            "data_pipeline": [
                ("Design pipeline architecture", "data-architect-governance"),
                ("Implement data ingestion", "data-pipeline-engineer"),
                ("Build transformation logic", "data-pipeline-engineer"),
                ("Set up monitoring", "data-pipeline-engineer"),
            ],
            "ml_project": [
                ("Design ML architecture", "ml-systems-architect"),
                ("Prepare and analyze data", "data-science-analyst"),
                ("Train models", "data-science-analyst"),
                ("Deploy pipeline", "ml-systems-architect"),
            ],
        }

        # Select template based on keywords
        if (
            any(k in task_lower for k in ["app", "application"])
            and "build" in task_lower
        ):
            template_key = "app_build"
        elif "api" in task_lower and "build" in task_lower:
            template_key = "api_build"
        elif any(k in task_lower for k in ["pipeline", "etl"]):
            template_key = "data_pipeline"
        elif any(k in task_lower for k in ["ml", "machine learning"]):
            template_key = "ml_project"
        else:
            # Generic template
            return [
                Subtask(f"Analyze: {task_description}", "specifications-engineer"),
                Subtask(f"Implement: {task_description}", recommended_agent.value),
                Subtask(
                    f"Test and validate: {task_description}", recommended_agent.value
                ),
            ]

        template = templates[template_key]
        return [Subtask(desc, agent_type) for desc, agent_type in template]

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
