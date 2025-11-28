"""
Resource Management System
Coordinates resource cleanup and monitoring across all components
"""

import threading
import time
import signal
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

from .database import DatabaseManager
from .agent_spawner import AgentSpawner
from .task_queue import TaskQueue
from .context_manager import ContextManager
from .config import get_config


class ResourceManager:
    """Centralized resource management and monitoring"""

    def __init__(self):
        self.config = get_config()
        self._cleanup_thread = None
        self._monitoring_thread = None
        self._shutdown = False
        self._lock = threading.Lock()

        # Resource limits
        self.max_db_size_mb = 100  # 100MB database limit
        self.max_context_size_mb = 200  # 200MB context storage limit
        self.max_task_count = 10000  # Maximum tasks in database
        self.cleanup_interval = 300  # 5 minutes

        # Component references
        self._components: Dict[str, Any] = {}

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

    def register_component(self, name: str, component: Any):
        """Register a component for resource management"""
        with self._lock:
            self._components[name] = component

    def start_resource_monitoring(self):
        """Start background resource monitoring and cleanup"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return

        self._shutdown = False

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker, daemon=True
        )
        self._cleanup_thread.start()

        # Start monitoring thread
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_worker, daemon=True
        )
        self._monitoring_thread.start()

    def stop_resource_monitoring(self):
        """Stop background monitoring and cleanup"""
        self._shutdown = True

        # Wait for threads to finish
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=10)

        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=10)

    def force_cleanup(self) -> Dict[str, int]:
        """Force immediate cleanup of all resources"""
        results = {}

        with self._lock:
            # Cleanup database
            if "task_queue" in self._components:
                task_queue: TaskQueue = self._components["task_queue"]
                results["tasks_cleaned"] = task_queue.cleanup_old_tasks(
                    days=self.config.cleanup_days, max_tasks=self.max_task_count
                )

            # Cleanup context files
            if "context_manager" in self._components:
                context_mgr: ContextManager = self._components["context_manager"]
                results["context_files_cleaned"] = context_mgr.cleanup_old_contexts(
                    days=self.config.cleanup_days
                )

            # Cleanup agents
            if "agent_spawner" in self._components:
                agent_spawner: AgentSpawner = self._components["agent_spawner"]
                agent_spawner._cleanup_completed_agents()
                agent_spawner._cleanup_stale_agents()
                results["agents_cleaned"] = True

            # Cleanup database connections
            DatabaseManager.cleanup_pools()
            results["db_connections_cleaned"] = True

        return results

    def get_resource_stats(self) -> Dict[str, Any]:
        """Get comprehensive resource usage statistics"""
        stats = {"timestamp": datetime.now().isoformat(), "components": {}}

        with self._lock:
            # Database stats
            if "task_queue" in self._components:
                task_queue: TaskQueue = self._components["task_queue"]
                stats["components"]["database"] = task_queue.get_memory_stats()

            # Agent stats
            if "agent_spawner" in self._components:
                agent_spawner: AgentSpawner = self._components["agent_spawner"]
                stats["components"]["agents"] = agent_spawner.get_resource_stats()

            # Context stats
            if "context_manager" in self._components:
                context_mgr: ContextManager = self._components["context_manager"]
                stats["components"]["context"] = context_mgr.get_context_stats()

        # System resource usage
        stats["system"] = self._get_system_stats()

        return stats

    def check_resource_limits(self) -> List[str]:
        """Check if any resource limits are exceeded"""
        warnings = []
        stats = self.get_resource_stats()

        # Check database size
        db_stats = stats["components"].get("database", {})
        db_size_mb = db_stats.get("db_size_mb", 0)
        if db_size_mb > self.max_db_size_mb:
            warnings.append(
                f"Database size ({db_size_mb:.1f}MB) exceeds limit ({self.max_db_size_mb}MB)"
            )

        # Check context storage size
        context_stats = stats["components"].get("context", {})
        context_size_mb = context_stats.get("total_size_mb", 0)
        if context_size_mb > self.max_context_size_mb:
            warnings.append(
                f"Context storage ({context_size_mb:.1f}MB) exceeds limit ({self.max_context_size_mb}MB)"
            )

        # Check task count
        task_counts = db_stats.get("task_counts", {})
        total_tasks = sum(task_counts.values())
        if total_tasks > self.max_task_count:
            warnings.append(
                f"Task count ({total_tasks}) exceeds limit ({self.max_task_count})"
            )

        # Check agent usage
        agent_stats = stats["components"].get("agents", {})
        resource_usage = agent_stats.get("resource_usage_percent", 0)
        if resource_usage > 90:
            warnings.append(
                f"Agent resource usage ({resource_usage:.1f}%) is very high"
            )

        return warnings

    def _cleanup_worker(self):
        """Background cleanup worker"""
        while not self._shutdown:
            try:
                time.sleep(self.cleanup_interval)
                if not self._shutdown:
                    self._perform_periodic_cleanup()
            except Exception:
                # Log error but don't crash cleanup thread
                pass

    def _monitoring_worker(self):
        """Background monitoring worker"""
        while not self._shutdown:
            try:
                time.sleep(60)  # Check every minute
                if not self._shutdown:
                    warnings = self.check_resource_limits()
                    if warnings:
                        # Force cleanup if resources are over limit
                        self.force_cleanup()
            except Exception:
                # Log error but don't crash monitoring thread
                pass

    def _perform_periodic_cleanup(self):
        """Perform routine cleanup operations"""
        with self._lock:
            # Cleanup old tasks
            if "task_queue" in self._components:
                task_queue: TaskQueue = self._components["task_queue"]
                task_queue.cleanup_old_tasks(days=self.config.cleanup_days)

            # Cleanup context files
            if "context_manager" in self._components:
                context_mgr: ContextManager = self._components["context_manager"]
                context_mgr.cleanup_old_contexts(days=self.config.cleanup_days)

            # Cleanup completed agents
            if "agent_spawner" in self._components:
                agent_spawner: AgentSpawner = self._components["agent_spawner"]
                agent_spawner._cleanup_completed_agents()

    def _get_system_stats(self) -> Dict[str, Any]:
        """Get basic system resource statistics"""
        try:
            import psutil
            import os

            # Memory usage
            memory = psutil.virtual_memory()
            process = psutil.Process(os.getpid())

            return {
                "process_memory_mb": process.memory_info().rss / (1024 * 1024),
                "system_memory_percent": memory.percent,
                "system_memory_available_mb": memory.available / (1024 * 1024),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "open_files": len(process.open_files())
                if hasattr(process, "open_files")
                else 0,
            }
        except ImportError:
            # psutil not available - provide basic stats
            import os
            import resource

            try:
                # Get basic memory info from resource module
                usage = resource.getrusage(resource.RUSAGE_SELF)
                return {
                    "process_memory_mb": usage.ru_maxrss
                    / 1024,  # Convert from KB to MB
                    "system_memory_percent": 0,
                    "system_memory_available_mb": 0,
                    "cpu_percent": 0,
                    "open_files": 0,
                    "note": "Install psutil for detailed system stats",
                }
            except Exception:
                return {
                    "process_memory_mb": 0,
                    "system_memory_percent": 0,
                    "system_memory_available_mb": 0,
                    "cpu_percent": 0,
                    "open_files": 0,
                    "note": "Limited system stats available",
                }
        except Exception:
            return {"error": "Cannot get system stats"}

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            self.shutdown()
            sys.exit(0)

        try:
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
        except (OSError, ValueError):
            # Signal handling might not be available in all environments
            pass

    def shutdown(self):
        """Graceful shutdown of resource manager"""
        # Stop monitoring
        self.stop_resource_monitoring()

        # Cleanup all resources
        self.force_cleanup()

        with self._lock:
            # Shutdown all components
            if "agent_spawner" in self._components:
                agent_spawner: AgentSpawner = self._components["agent_spawner"]
                agent_spawner.cleanup_all()

            # Cleanup database connections
            DatabaseManager.cleanup_pools()


# Global resource manager instance
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def init_resource_management(
    task_queue: TaskQueue, agent_spawner: AgentSpawner, context_manager: ContextManager
):
    """Initialize resource management with components"""
    rm = get_resource_manager()
    rm.register_component("task_queue", task_queue)
    rm.register_component("agent_spawner", agent_spawner)
    rm.register_component("context_manager", context_manager)
    rm.start_resource_monitoring()
    return rm


def shutdown_resource_management():
    """Shutdown resource management"""
    global _resource_manager
    if _resource_manager:
        _resource_manager.shutdown()
        _resource_manager = None


if __name__ == "__main__":
    # Test resource manager
    rm = ResourceManager()

    # Simulate resource stats
    print("Resource Stats:", rm.get_resource_stats())
    print("Resource Warnings:", rm.check_resource_limits())

    # Test cleanup
    print("Cleanup Results:", rm.force_cleanup())

    rm.shutdown()
