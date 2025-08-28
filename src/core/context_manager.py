"""
File-based Context Sharing System
Simple, reliable context sharing between agents using filesystem
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class ContextManager:
    """Manages shared context between agents using file-based storage"""

    def __init__(self, base_dir: str = "/tmp/agent_orchestrator/context"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Directory structure
        self.global_context = self.base_dir / "global"
        self.task_contexts = self.base_dir / "tasks"
        self.agent_outputs = self.base_dir / "outputs"
        self.shared_docs = self.base_dir / "docs"

        # Create directories
        for dir_path in [
            self.global_context,
            self.task_contexts,
            self.agent_outputs,
            self.shared_docs,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def set_global_context(self, key: str, value: Any):
        """Set a global context value accessible to all agents"""
        context_file = self.global_context / f"{key}.json"
        with open(context_file, "w") as f:
            json.dump(
                {"key": key, "value": value, "updated_at": datetime.now().isoformat()},
                f,
                indent=2,
            )

    def get_global_context(self, key: str) -> Optional[Any]:
        """Get a global context value"""
        context_file = self.global_context / f"{key}.json"
        if context_file.exists():
            with open(context_file, "r") as f:
                data = json.load(f)
                return data.get("value")
        return None

    def set_task_context(self, task_id: str, context: Dict[str, Any]):
        """Set context for a specific task"""
        task_dir = self.task_contexts / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        context_file = task_dir / "context.json"
        with open(context_file, "w") as f:
            json.dump(
                {
                    "task_id": task_id,
                    "context": context,
                    "updated_at": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

    def get_task_context(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get context for a specific task"""
        context_file = self.task_contexts / task_id / "context.json"
        if context_file.exists():
            with open(context_file, "r") as f:
                data = json.load(f)
                return data.get("context")
        return None

    def add_agent_output(
        self, agent_id: str, task_id: str, output: str, metadata: Dict = None
    ):
        """Store output from an agent"""
        output_dir = self.agent_outputs / task_id
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{agent_id}.json"
        with open(output_file, "w") as f:
            json.dump(
                {
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "output": output,
                    "metadata": metadata or {},
                    "created_at": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

    def get_agent_outputs(self, task_id: str) -> List[Dict]:
        """Get all agent outputs for a task"""
        output_dir = self.agent_outputs / task_id
        if not output_dir.exists():
            return []

        outputs = []
        for output_file in output_dir.glob("*.json"):
            with open(output_file, "r") as f:
                outputs.append(json.load(f))

        return sorted(outputs, key=lambda x: x.get("created_at", ""))

    def share_document(self, doc_name: str, content: str, format: str = "md"):
        """Share a document between agents"""
        doc_file = self.shared_docs / f"{doc_name}.{format}"
        with open(doc_file, "w") as f:
            f.write(content)

        # Also create metadata
        meta_file = self.shared_docs / f"{doc_name}.meta.json"
        with open(meta_file, "w") as f:
            json.dump(
                {
                    "name": doc_name,
                    "format": format,
                    "size": len(content),
                    "created_at": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

    def get_shared_document(self, doc_name: str) -> Optional[str]:
        """Get a shared document"""
        # Try different formats
        for ext in ["md", "txt", "json", "yaml"]:
            doc_file = self.shared_docs / f"{doc_name}.{ext}"
            if doc_file.exists():
                with open(doc_file, "r") as f:
                    return f.read()
        return None

    def list_shared_documents(self) -> List[Dict]:
        """List all shared documents"""
        docs = []
        for meta_file in self.shared_docs.glob("*.meta.json"):
            with open(meta_file, "r") as f:
                docs.append(json.load(f))
        return sorted(docs, key=lambda x: x.get("created_at", ""))

    def create_task_summary(self, task_id: str) -> Dict:
        """Create a summary of all context for a task"""
        summary = {
            "task_id": task_id,
            "task_context": self.get_task_context(task_id),
            "agent_outputs": self.get_agent_outputs(task_id),
            "created_at": datetime.now().isoformat(),
        }

        # Save summary
        summary_file = self.task_contexts / task_id / "summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        return summary

    def broadcast_message(
        self, message: str, sender: str = "orchestrator", recipients: List[str] = None
    ):
        """Broadcast a message to agents"""
        msg_dir = self.base_dir / "messages"
        msg_dir.mkdir(exist_ok=True)

        msg_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        msg_file = msg_dir / f"{msg_id}.json"

        with open(msg_file, "w") as f:
            json.dump(
                {
                    "id": msg_id,
                    "sender": sender,
                    "recipients": recipients or ["all"],
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

    def get_messages(self, recipient: str = None, since: str = None) -> List[Dict]:
        """Get messages for a recipient"""
        msg_dir = self.base_dir / "messages"
        if not msg_dir.exists():
            return []

        messages = []
        for msg_file in sorted(msg_dir.glob("*.json")):
            with open(msg_file, "r") as f:
                msg = json.load(f)

                # Filter by recipient
                if (
                    recipient
                    and recipient not in msg["recipients"]
                    and "all" not in msg["recipients"]
                ):
                    continue

                # Filter by time
                if since and msg["timestamp"] < since:
                    continue

                messages.append(msg)

        return messages

    def cleanup_old_contexts(self, days: int = 7):
        """Clean up old context files"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)

        cleaned = 0
        for root, dirs, files in os.walk(self.base_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.stat().st_mtime < cutoff.timestamp():
                    file_path.unlink()
                    cleaned += 1

        return cleaned

    def get_context_stats(self) -> Dict:
        """Get statistics about stored context"""
        stats = {
            "global_contexts": len(list(self.global_context.glob("*.json"))),
            "tasks_with_context": len(list(self.task_contexts.iterdir())),
            "agent_outputs": sum(1 for _ in self.agent_outputs.rglob("*.json")),
            "shared_documents": len(list(self.shared_docs.glob("*[!.meta].json"))),
            "messages": len(list((self.base_dir / "messages").glob("*.json")))
            if (self.base_dir / "messages").exists()
            else 0,
            "total_size_mb": sum(
                f.stat().st_size for f in self.base_dir.rglob("*") if f.is_file()
            )
            / (1024 * 1024),
        }
        return stats


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
