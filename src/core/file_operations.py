"""
Centralized file operations utilities
Consolidates safe file handling patterns used across the codebase
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from .input_validator import InputValidator, ValidationError


class FileOperations:
    """Centralized file operations with security and error handling"""

    @staticmethod
    def safe_write_json(
        file_path: Union[str, Path],
        data: Dict[str, Any],
        create_dirs: bool = True,
        mode: int = 0o600,
    ) -> bool:
        """
        Safely write JSON data to a file with proper error handling

        Args:
            file_path: Path to write the file
            data: Data to write as JSON
            create_dirs: Whether to create parent directories
            mode: File permissions (default: owner read/write only)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate and normalize path
            safe_path = InputValidator.validate_file_path(file_path)

            # Create parent directories if needed
            if create_dirs:
                safe_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

            # Validate data is JSON serializable
            try:
                json.dumps(data)
            except (TypeError, ValueError) as e:
                raise ValidationError(f"Data is not JSON serializable: {e}")

            # Write file with secure permissions
            with open(safe_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Set file permissions
            if hasattr(os, "chmod"):
                os.chmod(safe_path, mode)

            return True

        except (OSError, ValidationError, json.JSONEncodeError):
            return False

    @staticmethod
    def safe_read_json(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Safely read JSON data from a file

        Args:
            file_path: Path to read from

        Returns:
            Parsed JSON data or None if reading fails
        """
        try:
            safe_path = InputValidator.validate_file_path(file_path)

            if not safe_path.exists():
                return None

            with open(safe_path, "r", encoding="utf-8") as f:
                return json.load(f)

        except (OSError, json.JSONDecodeError, ValidationError):
            return None

    @staticmethod
    def safe_write_text(
        file_path: Union[str, Path],
        content: str,
        create_dirs: bool = True,
        mode: int = 0o600,
    ) -> bool:
        """
        Safely write text content to a file

        Args:
            file_path: Path to write the file
            content: Text content to write
            create_dirs: Whether to create parent directories
            mode: File permissions

        Returns:
            True if successful, False otherwise
        """
        try:
            safe_path = InputValidator.validate_file_path(file_path)

            if create_dirs:
                safe_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

            # Validate content
            if not isinstance(content, str):
                raise ValidationError("Content must be a string")

            # Limit content size to prevent DoS
            if len(content) > 10_000_000:  # 10MB limit
                raise ValidationError("Content too large")

            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Set file permissions
            if hasattr(os, "chmod"):
                os.chmod(safe_path, mode)

            return True

        except (OSError, ValidationError):
            return False

    @staticmethod
    def safe_read_text(file_path: Union[str, Path]) -> Optional[str]:
        """
        Safely read text content from a file

        Args:
            file_path: Path to read from

        Returns:
            File content or None if reading fails
        """
        try:
            safe_path = InputValidator.validate_file_path(file_path)

            if not safe_path.exists():
                return None

            with open(safe_path, "r", encoding="utf-8") as f:
                return f.read()

        except (OSError, ValidationError):
            return None

    @staticmethod
    def create_safe_directory(
        dir_path: Union[str, Path], mode: int = 0o700, parents: bool = True
    ) -> bool:
        """
        Create a directory with safe permissions

        Args:
            dir_path: Directory path to create
            mode: Directory permissions
            parents: Whether to create parent directories

        Returns:
            True if successful, False otherwise
        """
        try:
            safe_path = InputValidator.validate_file_path(dir_path)
            safe_path.mkdir(parents=parents, exist_ok=True, mode=mode)
            return True
        except (OSError, ValidationError):
            return False

    @staticmethod
    def safe_list_files(
        dir_path: Union[str, Path], pattern: str = "*", recursive: bool = False
    ) -> List[Path]:
        """
        Safely list files in a directory

        Args:
            dir_path: Directory to list
            pattern: Glob pattern to match
            recursive: Whether to search recursively

        Returns:
            List of matched file paths
        """
        try:
            safe_path = InputValidator.validate_file_path(dir_path)

            if not safe_path.exists() or not safe_path.is_dir():
                return []

            if recursive:
                return list(safe_path.rglob(pattern))
            else:
                return list(safe_path.glob(pattern))

        except (OSError, ValidationError):
            return []

    @staticmethod
    def safe_delete_file(file_path: Union[str, Path]) -> bool:
        """
        Safely delete a file

        Args:
            file_path: Path to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            safe_path = InputValidator.validate_file_path(file_path)

            if safe_path.exists() and safe_path.is_file():
                safe_path.unlink()
                return True
            return False

        except (OSError, ValidationError):
            return False

    @staticmethod
    def create_timestamped_file(
        base_dir: Union[str, Path], prefix: str, extension: str, data: Any = None
    ) -> Optional[Path]:
        """
        Create a file with timestamp in name

        Args:
            base_dir: Base directory for the file
            prefix: File name prefix
            extension: File extension (without dot)
            data: Optional data to write as JSON

        Returns:
            Path to created file or None if failed
        """
        try:
            safe_base = InputValidator.validate_file_path(base_dir)

            # Create timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{prefix}_{timestamp}.{extension}"

            file_path = safe_base / filename

            # Create directory if needed
            FileOperations.create_safe_directory(safe_base)

            if data is not None:
                success = FileOperations.safe_write_json(file_path, data)
            else:
                success = FileOperations.safe_write_text(file_path, "")

            return file_path if success else None

        except (ValidationError, OSError):
            return None

    @staticmethod
    def cleanup_old_files(
        dir_path: Union[str, Path], days: int, pattern: str = "*"
    ) -> int:
        """
        Clean up files older than specified days

        Args:
            dir_path: Directory to clean
            days: Age threshold in days
            pattern: File pattern to match

        Returns:
            Number of files deleted
        """
        try:
            from datetime import timedelta

            safe_path = InputValidator.validate_file_path(dir_path)

            if not safe_path.exists():
                return 0

            cutoff = datetime.now() - timedelta(days=days)
            cutoff_timestamp = cutoff.timestamp()

            deleted = 0
            for file_path in safe_path.glob(pattern):
                try:
                    if (
                        file_path.is_file()
                        and file_path.stat().st_mtime < cutoff_timestamp
                    ):
                        file_path.unlink()
                        deleted += 1
                except OSError:
                    continue  # Skip files that can't be deleted

            return deleted

        except (ValidationError, OSError):
            return 0

    @staticmethod
    def get_directory_stats(dir_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Get statistics about a directory

        Args:
            dir_path: Directory to analyze

        Returns:
            Dictionary with directory statistics
        """
        try:
            safe_path = InputValidator.validate_file_path(dir_path)

            if not safe_path.exists():
                return {"exists": False}

            total_files = 0
            total_size = 0
            subdirs = 0

            for item in safe_path.rglob("*"):
                if item.is_file():
                    total_files += 1
                    try:
                        total_size += item.stat().st_size
                    except OSError:
                        pass  # Skip files we can't stat
                elif item.is_dir() and item != safe_path:
                    subdirs += 1

            return {
                "exists": True,
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "subdirectories": subdirs,
                "path": str(safe_path),
            }

        except (ValidationError, OSError):
            return {"exists": False, "error": "Cannot access directory"}


class SessionFileManager:
    """Specialized file manager for session-based data"""

    def __init__(self, base_dir: Union[str, Path]):
        self.base_dir = InputValidator.validate_file_path(base_dir)
        FileOperations.create_safe_directory(self.base_dir)

    def save_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Save session data to file"""
        try:
            safe_session_id = InputValidator.sanitize_agent_id(session_id)
            file_path = self.base_dir / f"{safe_session_id}.json"
            return FileOperations.safe_write_json(file_path, data)
        except ValidationError:
            return False

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data from file"""
        try:
            safe_session_id = InputValidator.sanitize_agent_id(session_id)
            file_path = self.base_dir / f"{safe_session_id}.json"
            return FileOperations.safe_read_json(file_path)
        except ValidationError:
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all session files with metadata"""
        sessions = []
        for file_path in FileOperations.safe_list_files(self.base_dir, "*.json"):
            data = FileOperations.safe_read_json(file_path)
            if data:
                # Add file metadata
                try:
                    stat = file_path.stat()
                    data["file_info"] = {
                        "path": str(file_path),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                except OSError:
                    pass
                sessions.append(data)

        return sorted(sessions, key=lambda x: x.get("created_at", ""), reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session file"""
        try:
            safe_session_id = InputValidator.sanitize_agent_id(session_id)
            file_path = self.base_dir / f"{safe_session_id}.json"
            return FileOperations.safe_delete_file(file_path)
        except ValidationError:
            return False
