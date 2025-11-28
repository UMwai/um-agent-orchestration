"""
File system utilities and operations
"""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from .exceptions import safe_execute
from .config import get_config


class FileManager:
    """Manages file operations with consistent error handling"""

    @staticmethod
    def ensure_directory(path: Path) -> Path:
        """Ensure directory exists, create if not"""
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def write_json(file_path: Path, data: Any) -> bool:
        """Write data to JSON file safely"""

        def _write():
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            return True

        return safe_execute(_write, default=False)

    @staticmethod
    def read_json(file_path: Path) -> Optional[Dict]:
        """Read JSON file safely"""
        if not file_path.exists():
            return None

        def _read():
            with open(file_path, "r") as f:
                return json.load(f)

        return safe_execute(_read, default=None)

    @staticmethod
    def write_text(file_path: Path, content: str) -> bool:
        """Write text to file safely"""

        def _write():
            with open(file_path, "w") as f:
                f.write(content)
            return True

        return safe_execute(_write, default=False)

    @staticmethod
    def read_text(file_path: Path) -> Optional[str]:
        """Read text file safely"""
        if not file_path.exists():
            return None

        def _read():
            with open(file_path, "r") as f:
                return f.read()

        return safe_execute(_read, default=None)

    @staticmethod
    def cleanup_old_files(directory: Path, days: int = None) -> int:
        """Remove files older than specified days"""
        from datetime import timedelta

        days = days or get_config().cleanup_days
        cutoff = datetime.now() - timedelta(days=days)
        cleaned = 0

        if not directory.exists():
            return 0

        for file_path in directory.rglob("*"):
            if file_path.is_file():
                if file_path.stat().st_mtime < cutoff.timestamp():
                    safe_execute(lambda: file_path.unlink())
                    cleaned += 1

        return cleaned

    @staticmethod
    def check_tool_available(tool_name: str) -> bool:
        """Check if a command-line tool is available"""
        return shutil.which(tool_name) is not None


class WorkspaceManager:
    """Manages agent workspaces and temporary directories"""

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or get_config().base_path
        FileManager.ensure_directory(self.base_dir)

    def create_agent_workspace(self, agent_id: str) -> Path:
        """Create isolated workspace for an agent"""
        workspace = self.base_dir / f"agent_{agent_id}"
        return FileManager.ensure_directory(workspace)

    def cleanup_workspace(self, agent_id: str) -> bool:
        """Clean up an agent's workspace"""
        workspace = self.base_dir / f"agent_{agent_id}"
        if workspace.exists():
            return safe_execute(lambda: shutil.rmtree(workspace), default=False)
        return True

    def get_workspace_info(self, agent_id: str) -> Dict:
        """Get information about an agent's workspace"""
        workspace = self.base_dir / f"agent_{agent_id}"
        if not workspace.exists():
            return {"exists": False}

        size = sum(f.stat().st_size for f in workspace.rglob("*") if f.is_file())
        file_count = len(list(workspace.rglob("*")))

        return {
            "exists": True,
            "path": str(workspace),
            "size_bytes": size,
            "file_count": file_count,
            "created": datetime.fromtimestamp(workspace.stat().st_ctime).isoformat(),
        }
