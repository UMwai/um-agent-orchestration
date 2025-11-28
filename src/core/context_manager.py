"""
File-based Context Sharing System
Simple, reliable context sharing between agents using filesystem
"""

import os
import json
import fcntl
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager

from .input_validator import InputValidator, ValidationError
from .file_operations import FileOperations


class ContextManager:
    """Thread-safe manager for shared context between agents using file-based storage"""

    def __init__(self, base_dir: str = "/tmp/agent_orchestrator/context"):
        # Thread safety locks
        self._global_lock = threading.RLock()  # Lock for global context operations
        self._task_lock = threading.RLock()  # Lock for task context operations
        self._output_lock = threading.RLock()  # Lock for output operations
        self._file_locks = {}  # Per-file locks
        self._file_locks_lock = threading.Lock()  # Lock for file locks dict

        # Validate and secure the base directory
        try:
            self.base_dir = InputValidator.validate_file_path(Path(base_dir))
            # Create with secure permissions
            self.base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        except (ValidationError, OSError) as e:
            raise ValueError(f"Cannot initialize context manager: {e}")

        # Directory structure
        self.global_context = self.base_dir / "global"
        self.task_contexts = self.base_dir / "tasks"
        self.agent_outputs = self.base_dir / "outputs"
        self.shared_docs = self.base_dir / "docs"

        # Create directories with proper error handling
        for dir_path in [
            self.global_context,
            self.task_contexts,
            self.agent_outputs,
            self.shared_docs,
        ]:
            FileOperations.create_safe_directory(dir_path)

    @contextmanager
    def _file_lock(self, file_path: Path):
        """Context manager for file-level locking"""
        file_key = str(file_path)

        # Get or create a lock for this specific file
        with self._file_locks_lock:
            if file_key not in self._file_locks:
                self._file_locks[file_key] = threading.RLock()
            file_lock = self._file_locks[file_key]

        # Acquire the file-specific lock
        with file_lock:
            # Also use OS-level file locking if possible
            lock_file = None
            try:
                lock_file_path = file_path.with_suffix(f"{file_path.suffix}.lock")
                lock_file = open(lock_file_path, "w")
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (OSError, IOError):
                    # Can't get OS lock, continue with thread lock only
                    pass

                yield

            finally:
                if lock_file:
                    try:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                        lock_file.close()
                        # Clean up lock file
                        try:
                            lock_file_path.unlink()
                        except OSError:
                            pass
                    except (OSError, IOError):
                        pass

    def set_global_context(self, key: str, value: Any):
        """Set a global context value accessible to all agents (thread-safe)"""
        # Validate key for path safety
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Context key must be a non-empty string")

        # Check for dangerous patterns in key
        if ".." in key or "/" in key or "\\" in key or len(key) > 100:
            raise ValueError("Context key contains invalid characters or is too long")

        # Sanitize key for safe filename use (only safe characters allowed)
        safe_key = key.strip()
        if not safe_key:
            raise ValueError("Context key cannot be empty")

        with self._global_lock:
            context_file = InputValidator.safe_path_join(
                self.global_context, f"{safe_key}.json"
            )
            data = {
                "key": safe_key,
                "value": value,
                "updated_at": datetime.now().isoformat(),
            }

            with self._file_lock(context_file):
                if not FileOperations.safe_write_json(context_file, data):
                    raise ValueError("Cannot write global context")

    def get_global_context(self, key: str) -> Optional[Any]:
        """Get a global context value (thread-safe)"""
        # Validate and sanitize key
        if not isinstance(key, str) or not key.strip():
            return None

        # Check for dangerous patterns in key
        if ".." in key or "/" in key or "\\" in key or len(key) > 100:
            return None

        safe_key = key.strip()
        if not safe_key:
            return None

        with self._global_lock:
            try:
                context_file = InputValidator.safe_path_join(
                    self.global_context, f"{safe_key}.json"
                )
                with self._file_lock(context_file):
                    data = FileOperations.safe_read_json(context_file)
                    return data.get("value") if data else None
            except ValidationError:
                return None

    def set_task_context(self, task_id: str, context: Dict[str, Any]):
        """Set context for a specific task (thread-safe)"""
        # Validate task_id
        try:
            safe_task_id = InputValidator.sanitize_agent_id(task_id)
        except ValidationError as e:
            raise ValueError(f"Invalid task ID: {e}")

        # Validate context
        if not isinstance(context, dict):
            raise ValueError("Context must be a dictionary")

        try:
            InputValidator._validate_json_values(context)
        except ValidationError as e:
            raise ValueError(f"Invalid context: {e}")

        with self._task_lock:
            try:
                task_dir = InputValidator.safe_path_join(
                    self.task_contexts, safe_task_id
                )
                FileOperations.create_safe_directory(task_dir)

                context_file = InputValidator.safe_path_join(task_dir, "context.json")
                data = {
                    "task_id": safe_task_id,
                    "context": context,
                    "updated_at": datetime.now().isoformat(),
                }

                with self._file_lock(context_file):
                    if not FileOperations.safe_write_json(context_file, data):
                        raise ValueError("Cannot write task context file")
            except ValidationError as e:
                raise ValueError(f"Cannot set task context: {e}")

    def get_task_context(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get context for a specific task (thread-safe)"""
        # Validate task_id
        try:
            safe_task_id = InputValidator.sanitize_agent_id(task_id)
        except ValidationError:
            return None

        with self._task_lock:
            try:
                task_dir = InputValidator.safe_path_join(
                    self.task_contexts, safe_task_id
                )
                context_file = InputValidator.safe_path_join(task_dir, "context.json")
                with self._file_lock(context_file):
                    data = FileOperations.safe_read_json(context_file)
                    return data.get("context") if data else None
            except ValidationError:
                return None

    def add_agent_output(
        self, agent_id: str, task_id: str, output: str, metadata: Dict = None
    ):
        """Store output from an agent (thread-safe)"""
        # Validate inputs
        try:
            safe_agent_id = InputValidator.sanitize_agent_id(agent_id)
            safe_task_id = InputValidator.sanitize_agent_id(task_id)
        except ValidationError as e:
            raise ValueError(f"Invalid agent or task ID: {e}")

        if not isinstance(output, str):
            raise ValueError("Output must be a string")

        if len(output) > 1000000:  # 1MB limit
            raise ValueError("Output too large")

        if metadata and not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        with self._output_lock:
            try:
                output_dir = InputValidator.safe_path_join(
                    self.agent_outputs, safe_task_id
                )
                FileOperations.create_safe_directory(output_dir)

                output_file = InputValidator.safe_path_join(
                    output_dir, f"{safe_agent_id}.json"
                )
                data = {
                    "agent_id": safe_agent_id,
                    "task_id": safe_task_id,
                    "output": output,
                    "metadata": metadata or {},
                    "created_at": datetime.now().isoformat(),
                }

                with self._file_lock(output_file):
                    if not FileOperations.safe_write_json(output_file, data):
                        raise ValueError("Cannot write agent output file")
            except ValidationError as e:
                raise ValueError(f"Cannot store agent output: {e}")

    def get_agent_outputs(self, task_id: str) -> List[Dict]:
        """Get all agent outputs for a task (thread-safe)"""
        # Validate task_id
        try:
            safe_task_id = InputValidator.sanitize_agent_id(task_id)
        except ValidationError:
            return []

        with self._output_lock:
            try:
                output_dir = InputValidator.safe_path_join(
                    self.agent_outputs, safe_task_id
                )
                if not output_dir.exists():
                    return []

                outputs = []
                for output_file in output_dir.glob("*.json"):
                    # Validate each file path
                    try:
                        validated_file = InputValidator.validate_file_path(output_file)
                        with self._file_lock(validated_file):
                            with open(validated_file, "r", encoding="utf-8") as f:
                                outputs.append(json.load(f))
                    except (OSError, json.JSONDecodeError, ValidationError):
                        continue  # Skip invalid files

                return sorted(outputs, key=lambda x: x.get("created_at", ""))
            except (ValidationError, OSError):
                return []

    def share_document(self, doc_name: str, content: str, format: str = "md"):
        """Share a document between agents (thread-safe)"""
        # Validate inputs
        if not isinstance(doc_name, str) or not doc_name.strip():
            raise ValueError("Document name must be a non-empty string")

        if not isinstance(content, str):
            raise ValueError("Content must be a string")

        if len(content) > 10000000:  # 10MB limit
            raise ValueError("Document too large")

        # Check for dangerous patterns in doc_name
        if (
            ".." in doc_name
            or "/" in doc_name
            or "\\" in doc_name
            or len(doc_name) > 100
        ):
            raise ValueError("Document name contains invalid characters or is too long")

        # Sanitize doc_name for safe filename use
        safe_doc_name = doc_name.strip()
        if not safe_doc_name:
            raise ValueError("Document name cannot be empty")

        # Validate format
        allowed_formats = ["md", "txt", "json", "yaml", "yml"]
        if format not in allowed_formats:
            raise ValueError(f"Invalid format. Allowed: {allowed_formats}")

        with self._global_lock:  # Use global lock for shared documents
            try:
                doc_file = InputValidator.safe_path_join(
                    self.shared_docs, f"{safe_doc_name}.{format}"
                )
                meta_file = InputValidator.safe_path_join(
                    self.shared_docs, f"{safe_doc_name}.meta.json"
                )

                with self._file_lock(doc_file):
                    with open(doc_file, "w", encoding="utf-8") as f:
                        f.write(content)

                    # Also create metadata
                    with self._file_lock(meta_file):
                        with open(meta_file, "w", encoding="utf-8") as f:
                            json.dump(
                                {
                                    "name": safe_doc_name,
                                    "format": format,
                                    "size": len(content),
                                    "created_at": datetime.now().isoformat(),
                                },
                                f,
                                indent=2,
                            )
            except (OSError, ValidationError) as e:
                raise ValueError(f"Cannot share document: {e}")

    def get_shared_document(self, doc_name: str) -> Optional[str]:
        """Get a shared document (thread-safe)"""
        # Validate and sanitize doc_name
        if not isinstance(doc_name, str) or not doc_name.strip():
            return None

        # Check for dangerous patterns in doc_name
        if (
            ".." in doc_name
            or "/" in doc_name
            or "\\" in doc_name
            or len(doc_name) > 100
        ):
            return None

        safe_doc_name = doc_name.strip()
        if not safe_doc_name:
            return None

        with self._global_lock:  # Use global lock for shared documents
            # Try different formats
            for ext in ["md", "txt", "json", "yaml"]:
                try:
                    doc_file = InputValidator.safe_path_join(
                        self.shared_docs, f"{safe_doc_name}.{ext}"
                    )
                    if doc_file.exists():
                        with self._file_lock(doc_file):
                            with open(doc_file, "r", encoding="utf-8") as f:
                                return f.read()
                except (OSError, ValidationError):
                    continue
            return None

    def list_shared_documents(self) -> List[Dict]:
        """List all shared documents (thread-safe)"""
        with self._global_lock:
            docs = []
            for meta_file in self.shared_docs.glob("*.meta.json"):
                try:
                    with self._file_lock(meta_file):
                        with open(meta_file, "r") as f:
                            docs.append(json.load(f))
                except (OSError, json.JSONDecodeError):
                    continue  # Skip invalid files
            return sorted(docs, key=lambda x: x.get("created_at", ""))

    def create_task_summary(self, task_id: str) -> Dict:
        """Create a summary of all context for a task (thread-safe)"""
        with self._task_lock:
            summary = {
                "task_id": task_id,
                "task_context": self.get_task_context(task_id),
                "agent_outputs": self.get_agent_outputs(task_id),
                "created_at": datetime.now().isoformat(),
            }

            # Save summary
            try:
                safe_task_id = InputValidator.sanitize_agent_id(task_id)
                task_dir = InputValidator.safe_path_join(
                    self.task_contexts, safe_task_id
                )
                summary_file = InputValidator.safe_path_join(task_dir, "summary.json")

                with self._file_lock(summary_file):
                    with open(summary_file, "w") as f:
                        json.dump(summary, f, indent=2)
            except (ValidationError, OSError):
                pass  # Summary save failed, but return summary anyway

            return summary

    def broadcast_message(
        self, message: str, sender: str = "orchestrator", recipients: List[str] = None
    ):
        """Broadcast a message to agents (thread-safe)"""
        # Validate inputs
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Message must be a non-empty string")

        if len(message) > 10000:  # 10KB limit
            raise ValueError("Message too large")

        if not isinstance(sender, str) or not sender.strip():
            raise ValueError("Sender must be a non-empty string")

        # Check for dangerous patterns in sender
        if ".." in sender or "/" in sender or "\\" in sender:
            raise ValueError("Sender contains invalid characters")

        # Sanitize sender
        safe_sender = sender.strip()[:50]
        if not safe_sender:
            raise ValueError("Sender cannot be empty")

        # Validate recipients if provided
        if recipients:
            if not isinstance(recipients, list):
                raise ValueError("Recipients must be a list")
            safe_recipients = []
            for recipient in recipients:
                if isinstance(recipient, str):
                    # Check for dangerous patterns
                    if (
                        ".." not in recipient
                        and "/" not in recipient
                        and "\\" not in recipient
                    ):
                        safe_recipient = recipient.strip()[:50]
                        if safe_recipient:
                            safe_recipients.append(safe_recipient)
            recipients = safe_recipients or ["all"]
        else:
            recipients = ["all"]

        with self._global_lock:
            try:
                msg_dir = InputValidator.safe_path_join(self.base_dir, "messages")
                msg_dir.mkdir(exist_ok=True, mode=0o700)

                msg_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                msg_file = InputValidator.safe_path_join(msg_dir, f"{msg_id}.json")

                with self._file_lock(msg_file):
                    with open(msg_file, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "id": msg_id,
                                "sender": safe_sender,
                                "recipients": recipients,
                                "message": message,
                                "timestamp": datetime.now().isoformat(),
                            },
                            f,
                            indent=2,
                        )
            except (OSError, ValidationError) as e:
                raise ValueError(f"Cannot broadcast message: {e}")

    def get_messages(self, recipient: str = None, since: str = None) -> List[Dict]:
        """Get messages for a recipient (thread-safe)"""
        # Validate inputs
        if recipient is not None:
            if not isinstance(recipient, str) or not recipient.strip():
                return []
            # Check for dangerous patterns
            if ".." in recipient or "/" in recipient or "\\" in recipient:
                return []
            recipient = recipient.strip()[:50]

        with self._global_lock:
            try:
                msg_dir = InputValidator.safe_path_join(self.base_dir, "messages")
                if not msg_dir.exists():
                    return []

                messages = []
                for msg_file in sorted(msg_dir.glob("*.json")):
                    try:
                        validated_file = InputValidator.validate_file_path(msg_file)
                        with self._file_lock(validated_file):
                            with open(validated_file, "r", encoding="utf-8") as f:
                                msg = json.load(f)

                        # Filter by recipient
                        if (
                            recipient
                            and recipient not in msg.get("recipients", [])
                            and "all" not in msg.get("recipients", [])
                        ):
                            continue

                        # Filter by time
                        if since and msg.get("timestamp", "") < since:
                            continue

                        messages.append(msg)
                    except (OSError, json.JSONDecodeError, ValidationError):
                        continue  # Skip invalid files

                return messages
            except (ValidationError, OSError):
                return []

    def cleanup_old_contexts(self, days: int = 7):
        """Clean up old context files (thread-safe)"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        cleaned = 0

        # Use all locks to ensure no operations are happening during cleanup
        with self._global_lock, self._task_lock, self._output_lock:
            for root, dirs, files in os.walk(self.base_dir):
                for file in files:
                    file_path = Path(root) / file
                    try:
                        if file_path.stat().st_mtime < cutoff.timestamp():
                            # Use file lock for safe deletion
                            with self._file_lock(file_path):
                                if file_path.exists():  # Double-check existence
                                    file_path.unlink()
                                    cleaned += 1
                    except (OSError, PermissionError):
                        continue  # Skip files we can't access/delete

            return cleaned

    def get_context_stats(self) -> Dict:
        """Get statistics about stored context safely (thread-safe)"""
        with self._global_lock, self._task_lock, self._output_lock:
            base_stats = FileOperations.get_directory_stats(self.base_dir)

            # Count specific file types safely
            global_contexts = len(
                FileOperations.safe_list_files(self.global_context, "*.json")
            )
            tasks_with_context = len(
                FileOperations.safe_list_files(self.task_contexts, "*")
            )
            agent_outputs = len(
                FileOperations.safe_list_files(
                    self.agent_outputs, "*.json", recursive=True
                )
            )
            shared_docs = len(
                FileOperations.safe_list_files(self.shared_docs, "*[!.meta].json")
            )

            messages_dir = self.base_dir / "messages"
            messages = (
                len(FileOperations.safe_list_files(messages_dir, "*.json"))
                if messages_dir.exists()
                else 0
            )

            return {
                "global_contexts": global_contexts,
                "tasks_with_context": tasks_with_context,
                "agent_outputs": agent_outputs,
                "shared_documents": shared_docs,
                "messages": messages,
                "total_size_mb": base_stats.get("total_size_mb", 0),
                "total_files": base_stats.get("total_files", 0),
                "total_size_bytes": base_stats.get("total_size_bytes", 0),
            }


if __name__ == "__main__":
    # Test the context manager
    cm = ContextManager()

    # Set global context
    cm.set_global_context("project_name", "agent-orchestrator")
    cm.set_global_context("environment", "development")

    # Set task context
    cm.set_task_context(
        "task-001",
        {
            "description": "Fix authentication",
            "priority": "high",
            "assigned_agents": ["claude-1", "codex-1"],
        },
    )

    # Add agent output
    cm.add_agent_output(
        "claude-1",
        "task-001",
        "Fixed the authentication bug in auth.py",
        {"lines_changed": 45, "files_modified": 2},
    )

    # Share a document
    cm.share_document(
        "architecture",
        """
# System Architecture

## Overview
Simple multi-agent orchestration system

## Components
- Task Queue (SQLite)
- Agent Spawner (subprocess)
- Context Manager (file-based)
""",
    )

    # Broadcast message
    cm.broadcast_message("Starting new sprint", "orchestrator")

    # Get stats
    print("Context Stats:", cm.get_context_stats())

    # Create task summary
    summary = cm.create_task_summary("task-001")
    print("Task Summary:", json.dumps(summary, indent=2))
