"""
Centralized Claude CLI interaction manager
Consolidates all Claude CLI calls to eliminate duplication
"""

import subprocess
import shutil
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import time

from .exceptions import safe_execute
from .config import get_config
from .input_validator import InputValidator, ValidationError


@dataclass
class ClaudeResponse:
    """Structured response from Claude CLI"""

    success: bool
    content: str
    error: Optional[str] = None
    return_code: Optional[int] = None
    duration: float = 0.0


class ClaudeCLIManager:
    """Manages all interactions with Claude CLI"""

    def __init__(self, timeout: int = None):
        self.timeout = timeout or get_config().agent_timeout
        self.claude_available = self._check_claude_availability()

    def _check_claude_availability(self) -> bool:
        """Check if Claude CLI is available"""
        return shutil.which("claude") is not None

    def call_claude(
        self, prompt: str, timeout: Optional[int] = None, skip_permissions: bool = True
    ) -> ClaudeResponse:
        """
        Make a standardized call to Claude CLI

        Args:
            prompt: The prompt to send to Claude
            timeout: Override default timeout
            skip_permissions: Whether to use --dangerously-skip-permissions

        Returns:
            ClaudeResponse with success status and content
        """
        if not self.claude_available:
            return ClaudeResponse(
                success=False, content="", error="Claude CLI not available"
            )

        # Validate prompt
        try:
            safe_prompt = InputValidator.sanitize_task_description(prompt)
        except ValidationError as e:
            return ClaudeResponse(
                success=False, content="", error=f"Invalid prompt: {e}"
            )

        # Build command arguments
        cmd_args = ["claude"]
        if skip_permissions:
            cmd_args.append("--dangerously-skip-permissions")
        cmd_args.extend(["-p", safe_prompt])

        # Execute with timeout and error handling
        start_time = time.time()
        timeout_val = timeout or self.timeout

        try:
            result = subprocess.run(
                cmd_args, capture_output=True, text=True, timeout=timeout_val
            )

            duration = time.time() - start_time

            return ClaudeResponse(
                success=result.returncode == 0,
                content=result.stdout.strip() if result.returncode == 0 else "",
                error=result.stderr.strip() if result.returncode != 0 else None,
                return_code=result.returncode,
                duration=duration,
            )

        except subprocess.TimeoutExpired:
            return ClaudeResponse(
                success=False,
                content="",
                error=f"Claude CLI timed out after {timeout_val} seconds",
                duration=time.time() - start_time,
            )
        except Exception as e:
            return ClaudeResponse(
                success=False,
                content="",
                error=f"Claude CLI execution failed: {e}",
                duration=time.time() - start_time,
            )

    def parse_json_response(self, response: ClaudeResponse) -> Optional[Dict[str, Any]]:
        """
        Parse Claude response as JSON with error handling

        Args:
            response: ClaudeResponse from call_claude

        Returns:
            Parsed JSON dict or None if parsing fails
        """
        if not response.success or not response.content:
            return None

        return safe_execute(lambda: json.loads(response.content), default=None)

    def call_claude_for_json(
        self, prompt: str, fallback_data: Any = None, timeout: Optional[int] = None
    ) -> Any:
        """
        Call Claude expecting JSON response with fallback

        Args:
            prompt: Prompt to send to Claude
            fallback_data: Data to return if JSON parsing fails
            timeout: Override default timeout

        Returns:
            Parsed JSON data or fallback_data
        """
        response = self.call_claude(prompt, timeout)

        if response.success:
            parsed = self.parse_json_response(response)
            if parsed is not None:
                return parsed

        return fallback_data

    def build_specialized_agent_prompt(
        self, agent_type: str, original_prompt: str
    ) -> str:
        """
        Build prompt for specialized agents using Task tool

        Args:
            agent_type: The specialized agent type
            original_prompt: Original task prompt

        Returns:
            Enhanced prompt for specialized agent
        """
        # Agent type mapping for specialized agents
        specialized_agents = {
            "data-pipeline-engineer",
            "backend-systems-engineer",
            "frontend-ui-engineer",
            "data-science-analyst",
            "aws-cloud-architect",
            "ml-systems-architect",
            "project-delivery-manager",
            "data-architect-governance",
            "llm-architect",
            "specifications-engineer",
        }

        if agent_type not in specialized_agents:
            return original_prompt

        return f"""Use the Task tool to launch a {agent_type} agent with the following task:

{original_prompt}

IMPORTANT: You must use the Task tool with subagent_type='{agent_type}' to complete this task.
Provide the task description and let the specialized agent handle the implementation.

After the agent completes, summarize the results."""

    def create_decomposition_prompt(
        self,
        task_description: str,
        max_subtasks: int = 5,
        agent_types: List[str] = None,
    ) -> str:
        """
        Create standardized task decomposition prompt

        Args:
            task_description: High-level task to decompose
            max_subtasks: Maximum number of subtasks
            agent_types: Available agent types

        Returns:
            Formatted decomposition prompt
        """
        if not agent_types:
            agent_types = [
                "claude",
                "codex",
                "data-pipeline-engineer",
                "backend-systems-engineer",
                "frontend-ui-engineer",
                "data-science-analyst",
                "aws-cloud-architect",
                "ml-systems-architect",
                "project-delivery-manager",
                "data-architect-governance",
                "llm-architect",
                "specifications-engineer",
            ]

        agent_list = "\n   - ".join(
            [f"{t}: Specialized for {t.replace('-', ' ')}" for t in agent_types]
        )

        return f"""Break down this task into {max_subtasks} or fewer specific subtasks.

Task: {task_description}

For each subtask, specify:
1. A clear, actionable description
2. Which agent type is best suited. Choose from:
   - {agent_list}
3. Any dependencies on other subtasks
4. What context it needs from other subtasks

Return as JSON array with format:
[{{
    "description": "Specific actionable task",
    "agent_type": "<agent-type-from-above>",
    "dependencies": ["subtask_1", "subtask_2"],
    "context_needed": ["database_schema", "api_design"]
}}]

Focus on practical implementation steps. Be specific and actionable."""


# Global instance for shared use
_claude_manager = None


def get_claude_manager() -> ClaudeCLIManager:
    """Get shared Claude CLI manager instance"""
    global _claude_manager
    if _claude_manager is None:
        _claude_manager = ClaudeCLIManager()
    return _claude_manager
