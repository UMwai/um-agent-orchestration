"""
Tools definition for Autonomous Harness
"""
from typing import Dict, List, Any
from abc import ABC, abstractmethod
import subprocess
import os
import re
from .file_operations import FileOperations
from .input_validator import InputValidator, ValidationError
from .config import get_config


# Security Constants
MAX_READ_SIZE = 1_048_576  # 1MB file read limit
MAX_COMMAND_LENGTH = 10_000
WORKSPACE_ROOT = os.path.abspath(os.getcwd())  # Restrict file operations to workspace


class Tool(ABC):
    """Abstract base class for all tools"""
    name: str
    description: str
    input_schema: Dict[str, Any]

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the tool with given arguments"""
        raise NotImplementedError


class BashTool(Tool):
    name = "bash"
    description = "Execute a bash command. Use this for listing files, running scripts, or any terminal command. Do not use interactive commands like vim or nano."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to execute"}
        },
        "required": ["command"]
    }

    # Command whitelist - safe read-only operations
    SAFE_COMMAND_PREFIXES = {
        'ls', 'cat', 'head', 'tail', 'grep', 'find', 'echo', 'pwd', 'wc',
        'sort', 'uniq', 'diff', 'which', 'whereis', 'file', 'stat',
        'git status', 'git log', 'git diff', 'git show', 'git branch',
        'python -c', 'node -e', 'npm list', 'pip list', 'pip show',
        'docker ps', 'docker images', 'docker inspect',
        'curl -s', 'wget --spider', 'ping -c', 'dig', 'host', 'nslookup',
        'ps aux', 'top -b -n 1', 'df -h', 'du -sh', 'free -h', 'uptime',
        'env', 'printenv', 'date', 'cal', 'whoami', 'hostname', 'uname'
    }

    # Dangerous patterns that should always be blocked
    DANGEROUS_PATTERNS = [
        r'\brm\s+-rf\s+/',  # rm -rf /
        r'\brm\s+-rf\s+~',  # rm -rf ~
        r'\brm\s+-rf\s+\*',  # rm -rf *
        r'>\s*/dev/sd[a-z]',  # Write to disk devices
        r'dd\s+if=.*of=/dev',  # dd to devices
        r'mkfs\.',  # Format filesystem
        r'fdisk',  # Disk partitioning
        r':(){:\|:&};:',  # Fork bomb
        r'chmod\s+-R\s+777',  # Dangerous permissions
        r'chown\s+-R',  # Recursive ownership change
        r'/etc/shadow',  # Password file access
        r'/etc/passwd',  # User file modification
        r'iptables\s+-F',  # Firewall flush
        r'shutdown',  # System shutdown
        r'reboot',  # System reboot
        r'init\s+0',  # Shutdown via init
        r'killall\s+-9',  # Kill all processes
        r'pkill\s+-9',  # Kill processes
        r'curl.*\|\s*bash',  # Pipe to bash
        r'wget.*\|\s*sh',  # Pipe to shell
        r'eval\s*\(',  # Code evaluation
        r'exec\s*\(',  # Code execution
        r'__import__',  # Python imports
        r'system\(',  # System calls
        r'popen\(',  # Process execution
        r'subprocess\.',  # Subprocess calls
        r'os\.system',  # OS system calls
    ]

    def execute(self, command: str) -> str:
        try:
            # Validate command is a string
            if not isinstance(command, str):
                return "Error: Command must be a string"

            # Check command length
            if len(command) > MAX_COMMAND_LENGTH:
                return f"Error: Command too long (max {MAX_COMMAND_LENGTH} characters)"

            # Remove null bytes
            command = command.replace('\x00', '')

            # Strip and validate non-empty
            command = command.strip()
            if not command:
                return "Error: Empty command"

            # Check for dangerous patterns
            for pattern in self.DANGEROUS_PATTERNS:
                if re.search(pattern, command, re.IGNORECASE):
                    return f"Error: Command contains dangerous pattern and is blocked for security"

            # Check whitelist for safe commands
            command_start = command.split()[0] if command.split() else ""
            is_whitelisted = False

            for safe_prefix in self.SAFE_COMMAND_PREFIXES:
                if command.startswith(safe_prefix):
                    is_whitelisted = True
                    break

            if not is_whitelisted:
                return f"Error: Command '{command_start}' is not in the whitelist of safe commands. Only read-only operations are permitted."

            # Additional validation: check for command chaining that might bypass whitelist
            if any(sep in command for sep in ['&&', '||', ';', '|']):
                # Only allow pipes for safe filtering operations
                if '|' in command and not any(sep in command for sep in ['&&', '||', ';']):
                    # Validate each part of the pipe chain
                    parts = command.split('|')
                    for part in parts:
                        part_cmd = part.strip().split()[0] if part.strip().split() else ""
                        cmd_whitelisted = False
                        for safe_prefix in self.SAFE_COMMAND_PREFIXES:
                            if part.strip().startswith(safe_prefix):
                                cmd_whitelisted = True
                                break
                        if not cmd_whitelisted:
                            return f"Error: Piped command '{part_cmd}' is not in the whitelist"
                else:
                    return "Error: Command chaining with &&, ||, or ; is not permitted"

            # Execute with timeout and restricted environment
            process = subprocess.Popen(
                ["bash", "-c", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=WORKSPACE_ROOT,  # Restrict to workspace
                env={**os.environ, 'PATH': os.environ.get('PATH', '')},  # Limited env
            )

            try:
                timeout_seconds = get_config().bash_timeout_seconds
                if timeout_seconds is None or timeout_seconds <= 0:
                    stdout, stderr = process.communicate()
                else:
                    stdout, stderr = process.communicate(timeout=timeout_seconds)
                return (
                    f"Stdout:\n{stdout}\nStderr:\n{stderr}\nExit Code: {process.returncode}"
                )
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                timeout_seconds = get_config().bash_timeout_seconds or 120
                return f"Error: Command timed out after {timeout_seconds} seconds"

        except Exception as e:
            return f"Error executing command: {str(e)}"


class FileEditTool(Tool):
    name = "edit_file"
    description = "Write or edit a file. Overwrites the entire file content. Only works within the workspace directory."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "content": {"type": "string", "description": "New content for the file"}
        },
        "required": ["path", "content"]
    }

    def execute(self, path: str, content: str) -> str:
        try:
            # Validate path using InputValidator
            try:
                safe_path = InputValidator.validate_file_path(path)
            except ValidationError as e:
                return f"Error: Invalid path - {str(e)}"

            # Ensure path is within workspace
            try:
                safe_path_str = str(safe_path.resolve())
                workspace_str = str(os.path.abspath(WORKSPACE_ROOT))

                if not safe_path_str.startswith(workspace_str):
                    return f"Error: Path must be within workspace directory {workspace_str}"
            except Exception as e:
                return f"Error: Cannot resolve path - {str(e)}"

            # Check for symlink attacks
            if safe_path.exists() and safe_path.is_symlink():
                # Resolve symlink and check it's still in workspace
                try:
                    real_path = safe_path.resolve(strict=True)
                    real_path_str = str(real_path)
                    if not real_path_str.startswith(workspace_str):
                        return "Error: Symlink target is outside workspace directory"
                except Exception:
                    return "Error: Cannot resolve symlink safely"

            # Use FileOperations for safe write
            if FileOperations.safe_write_text(safe_path, content):
                return f"Successfully wrote to {safe_path}"
            return f"Failed to write to {safe_path}"

        except Exception as e:
            return f"Error writing file: {str(e)}"


class FileReadTool(Tool):
    name = "read_file"
    description = "Read the contents of a file. Limited to files under 1MB. Only works within the workspace directory."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"}
        },
        "required": ["path"]
    }

    def execute(self, path: str) -> str:
        try:
            # Validate path using InputValidator
            try:
                safe_path = InputValidator.validate_file_path(path)
            except ValidationError as e:
                return f"Error: Invalid path - {str(e)}"

            # Ensure path is within workspace
            try:
                safe_path_str = str(safe_path.resolve())
                workspace_str = str(os.path.abspath(WORKSPACE_ROOT))

                if not safe_path_str.startswith(workspace_str):
                    return f"Error: Path must be within workspace directory {workspace_str}"
            except Exception as e:
                return f"Error: Cannot resolve path - {str(e)}"

            # Check if file exists
            if not safe_path.exists():
                return f"Error: File does not exist: {safe_path}"

            # Check for symlink attacks
            if safe_path.is_symlink():
                try:
                    real_path = safe_path.resolve(strict=True)
                    real_path_str = str(real_path)
                    if not real_path_str.startswith(workspace_str):
                        return "Error: Symlink target is outside workspace directory"
                except Exception:
                    return "Error: Cannot resolve symlink safely"

            # Check file size before reading
            try:
                file_size = safe_path.stat().st_size
                if file_size > MAX_READ_SIZE:
                    size_mb = file_size / (1024 * 1024)
                    max_mb = MAX_READ_SIZE / (1024 * 1024)
                    return f"Error: File too large ({size_mb:.2f}MB). Maximum allowed size is {max_mb}MB. Use bash tool with 'head' or 'tail' for large files."
            except OSError as e:
                return f"Error: Cannot check file size - {str(e)}"

            # Read file using safe operations
            content = FileOperations.safe_read_text(safe_path)
            if content is not None:
                return content
            return f"Error: Could not read file {safe_path}"

        except Exception as e:
            return f"Error reading file: {str(e)}"


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Get list of tool definitions for API calls"""
    tools = [BashTool(), FileEditTool(), FileReadTool()]
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema
        }
        for t in tools
    ]


def get_tool_map() -> Dict[str, Tool]:
    """Get mapping of tool names to tool instances"""
    return {
        "bash": BashTool(),
        "edit_file": FileEditTool(),
        "read_file": FileReadTool()
    }
