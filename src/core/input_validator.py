"""
Input validation and sanitization utilities
Provides secure input handling for the Agent Orchestrator
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, Union
import shlex


class ValidationError(Exception):
    """Custom exception for validation errors"""

    pass


class InputValidator:
    """Centralized input validation and sanitization"""

    # Safe characters for task descriptions and agent IDs
    SAFE_TASK_CHARS = re.compile(
        r'^[a-zA-Z0-9\s\-_.,!?()[\]{}:;"\'+=@#$%^&*<>/\\|\n\r\t]+$'
    )
    SAFE_AGENT_ID_CHARS = re.compile(r"^[a-zA-Z0-9\-_]+$")
    SAFE_PATH_CHARS = re.compile(r"^[a-zA-Z0-9\-_./]+$")

    # Maximum lengths to prevent DoS
    MAX_TASK_DESCRIPTION_LENGTH = 10000
    MAX_AGENT_ID_LENGTH = 100
    MAX_PATH_LENGTH = 500
    MAX_JSON_SIZE = 100000  # 100KB

    @staticmethod
    def sanitize_task_description(description: str) -> str:
        """Sanitize task description for safe processing"""
        if not isinstance(description, str):
            raise ValidationError("Task description must be a string")

        if len(description) > InputValidator.MAX_TASK_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"Task description too long (max {InputValidator.MAX_TASK_DESCRIPTION_LENGTH} chars)"
            )

        if not description.strip():
            raise ValidationError("Task description cannot be empty")

        # Remove any null bytes
        description = description.replace("\x00", "")

        # Basic sanitization for shell safety
        # Remove potential command injection patterns
        dangerous_patterns = [
            r"`[^`]*`",  # Backticks
            r"\$\([^)]*\)",  # Command substitution
            r"&&\s*\w+",  # Command chaining
            r";\s*\w+",  # Command separation
            r"\|\s*\w+",  # Pipes
            r">\s*[/\w]",  # Redirects
            r"<\s*[/\w]",  # Input redirects
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, description):
                raise ValidationError(
                    f"Task description contains potentially dangerous pattern: {pattern}"
                )

        return description.strip()

    @staticmethod
    def sanitize_agent_id(agent_id: str) -> str:
        """Sanitize agent ID for safe use in file paths and commands"""
        if not isinstance(agent_id, str):
            raise ValidationError("Agent ID must be a string")

        if len(agent_id) > InputValidator.MAX_AGENT_ID_LENGTH:
            raise ValidationError(
                f"Agent ID too long (max {InputValidator.MAX_AGENT_ID_LENGTH} chars)"
            )

        if not InputValidator.SAFE_AGENT_ID_CHARS.match(agent_id):
            raise ValidationError("Agent ID contains invalid characters")

        return agent_id.strip()

    @staticmethod
    def validate_file_path(file_path: Union[str, Path]) -> Path:
        """Validate and normalize file paths to prevent directory traversal"""
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # Convert to string for validation
        path_str = str(file_path)

        if len(path_str) > InputValidator.MAX_PATH_LENGTH:
            raise ValidationError(
                f"Path too long (max {InputValidator.MAX_PATH_LENGTH} chars)"
            )

        # Check for directory traversal attempts
        if ".." in path_str:
            raise ValidationError("Path contains directory traversal (..) characters")

        # Check for null bytes
        if "\x00" in path_str:
            raise ValidationError("Path contains null bytes")

        # Resolve the path and ensure it doesn't escape the base directory
        try:
            resolved_path = file_path.resolve()
        except (OSError, ValueError) as e:
            raise ValidationError(f"Invalid path: {e}")

        return resolved_path

    @staticmethod
    def safe_path_join(base_dir: Path, *parts: str) -> Path:
        """Safely join path components and validate result"""
        # Sanitize each part
        safe_parts = []
        for part in parts:
            if not isinstance(part, str):
                raise ValidationError("Path component must be a string")

            # Remove dangerous characters
            part = part.replace("..", "").replace("\x00", "").strip()
            if not part or part in (".", ".."):
                raise ValidationError(f"Invalid path component: {part}")

            safe_parts.append(part)

        # Join paths safely
        result_path = base_dir
        for part in safe_parts:
            result_path = result_path / part

        # Validate the final path
        return InputValidator.validate_file_path(result_path)

    @staticmethod
    def validate_json_context(json_str: str) -> Dict[str, Any]:
        """Safely parse and validate JSON context"""
        if not isinstance(json_str, str):
            raise ValidationError("JSON context must be a string")

        if len(json_str) > InputValidator.MAX_JSON_SIZE:
            raise ValidationError(
                f"JSON too large (max {InputValidator.MAX_JSON_SIZE} bytes)"
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

        if not isinstance(data, dict):
            raise ValidationError("JSON context must be an object")

        # Recursively validate all string values in the JSON
        InputValidator._validate_json_values(data)

        return data

    @staticmethod
    def _validate_json_values(obj: Any, depth: int = 0) -> None:
        """Recursively validate JSON values for safety"""
        if depth > 10:  # Prevent deep recursion attacks
            raise ValidationError("JSON structure too deeply nested")

        if isinstance(obj, dict):
            for key, value in obj.items():
                if not isinstance(key, str):
                    raise ValidationError("JSON keys must be strings")
                if len(key) > 100:
                    raise ValidationError("JSON key too long")
                InputValidator._validate_json_values(value, depth + 1)

        elif isinstance(obj, list):
            if len(obj) > 1000:  # Prevent large array attacks
                raise ValidationError("JSON array too large")
            for item in obj:
                InputValidator._validate_json_values(item, depth + 1)

        elif isinstance(obj, str):
            if len(obj) > 10000:  # Prevent large string attacks
                raise ValidationError("JSON string value too long")
            if "\x00" in obj:
                raise ValidationError("JSON string contains null bytes")

            # Check for potentially dangerous patterns in JSON strings
            dangerous_patterns = [
                r"\$\([^)]*\)",  # Command substitution
                r"`[^`]*`",  # Backticks
                r"&&\s*\w+",  # Command chaining
                r";\s*\w+",  # Command separation
                r"\|\s*\w+",  # Pipes
                r"rm\s+-rf",  # Dangerous commands
                r"eval\s*\(",  # Code evaluation
                r"exec\s*\(",  # Code execution
            ]

            for pattern in dangerous_patterns:
                if re.search(pattern, obj, re.IGNORECASE):
                    raise ValidationError(
                        f"JSON string contains dangerous pattern: {pattern}"
                    )

    @staticmethod
    def sanitize_command_arg(arg: str) -> str:
        """Sanitize a command argument for safe shell execution"""
        if not isinstance(arg, str):
            raise ValidationError("Command argument must be a string")

        # Use shlex.quote for proper shell escaping
        return shlex.quote(arg)

    @staticmethod
    def validate_agent_type(agent_type: str) -> str:
        """Validate agent type against allowed values"""
        valid_types = [
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
            "any",
        ]

        if agent_type not in valid_types:
            raise ValidationError(f"Invalid agent type: {agent_type}")

        return agent_type

    @staticmethod
    def validate_priority(priority: str) -> str:
        """Validate priority value"""
        valid_priorities = ["high", "normal", "low"]

        if priority not in valid_priorities:
            raise ValidationError(f"Invalid priority: {priority}")

        return priority

    @staticmethod
    def create_safe_working_dir(base_dir: Path, agent_id: str) -> Path:
        """Create a safe working directory for an agent"""
        # Sanitize the agent ID first
        safe_agent_id = InputValidator.sanitize_agent_id(agent_id)

        # Create the working directory path safely
        working_dir = InputValidator.safe_path_join(base_dir, f"agent_{safe_agent_id}")

        # Ensure the base directory exists and is secure
        if not base_dir.exists():
            try:
                base_dir.mkdir(parents=True, mode=0o700)  # Restrictive permissions
            except OSError as e:
                raise ValidationError(f"Cannot create base directory: {e}")

        # Create the working directory with restrictive permissions
        try:
            working_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as e:
            raise ValidationError(f"Cannot create working directory: {e}")

        return working_dir
