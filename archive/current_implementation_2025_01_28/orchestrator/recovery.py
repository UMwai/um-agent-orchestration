"""
Task Recovery System for AutoDev
Handles recovery of tasks from persistent storage after system restarts.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from orchestrator.models import TaskStatus
from orchestrator.persistence import get_persistence_manager
from orchestrator.persistence_models import TaskRecord, TaskState
from orchestrator.queue import _redis


class TaskRecoveryManager:
    """
    Manages recovery of tasks from persistent storage to Redis after system restarts.
    Handles interrupted tasks and restores system state.
    """

    def __init__(self, redis_client=None):
        self.redis_client = redis_client or _redis
        self.persistence_manager = get_persistence_manager()

    def recover_tasks_on_startup(self) -> dict[str, int]:
        """
        Recover tasks from persistent storage on system startup.
        Returns counts of recovered tasks by state.
        """
        print("🔄 Starting task recovery from persistent storage...")

        recovery_stats = {
            "total_recovered": 0,
            "running_interrupted": 0,
            "queued_restored": 0,
            "completed_restored": 0,
            "failed_restored": 0,
            "errors": 0,
        }

        try:
            # Get all tasks from persistent storage
            all_tasks = self.persistence_manager.get_all_tasks()

            for task_record in all_tasks:
                try:
                    # Recover task to Redis
                    success = self._recover_single_task(task_record)

                    if success:
                        recovery_stats["total_recovered"] += 1

                        # Update specific counters based on state
                        if task_record.state == TaskState.RUNNING:
                            # Mark interrupted running tasks as failed
                            self._handle_interrupted_task(task_record)
                            recovery_stats["running_interrupted"] += 1

                        elif task_record.state == TaskState.QUEUED:
                            recovery_stats["queued_restored"] += 1

                        elif task_record.state in [TaskState.PASSED, TaskState.COMPLETED]:
                            recovery_stats["completed_restored"] += 1

                        elif task_record.state in [TaskState.FAILED, TaskState.ERROR]:
                            recovery_stats["failed_restored"] += 1
                    else:
                        recovery_stats["errors"] += 1

                except Exception as e:
                    print(f"⚠️  Failed to recover task {task_record.id}: {e}")
                    recovery_stats["errors"] += 1

            # Print recovery summary
            print("✅ Task recovery completed:")
            print(f"   📊 Total tasks recovered: {recovery_stats['total_recovered']}")
            print(f"   🔄 Running tasks interrupted: {recovery_stats['running_interrupted']}")
            print(f"   📋 Queued tasks restored: {recovery_stats['queued_restored']}")
            print(f"   ✅ Completed tasks restored: {recovery_stats['completed_restored']}")
            print(f"   ❌ Failed tasks restored: {recovery_stats['failed_restored']}")
            if recovery_stats["errors"] > 0:
                print(f"   ⚠️  Recovery errors: {recovery_stats['errors']}")

        except Exception as e:
            print(f"❌ Task recovery failed: {e}")
            recovery_stats["errors"] += 1

        return recovery_stats

    def _recover_single_task(self, task_record: TaskRecord) -> bool:
        """
        Recover a single task to Redis.
        Returns True if successful, False otherwise.
        """
        try:
            # Create TaskStatus for Redis
            task_status = TaskStatus(
                id=task_record.id,
                role=task_record.role,
                branch=task_record.branch or f"auto/{task_record.role}/{task_record.id}",
                state=self._map_state_to_redis_format(task_record.state),
                last_error=task_record.last_error,
                provider=task_record.provider,
                model=task_record.model,
            )

            # Store in Redis with 24-hour expiry
            key = f"task_status:{task_record.id}"
            self.redis_client.setex(key, 86400, task_status.json())

            return True

        except Exception as e:
            print(f"❌ Failed to recover task {task_record.id} to Redis: {e}")
            return False

    def _handle_interrupted_task(self, task_record: TaskRecord):
        """
        Handle tasks that were running when the system was shut down.
        Mark them as failed with appropriate error message.
        """
        try:
            error_message = (
                f"Task interrupted due to system restart at {datetime.utcnow().isoformat()}"
            )

            # Update in persistent storage
            self.persistence_manager.update_task_state(
                task_record.id, TaskState.FAILED, error_message=error_message
            )

            print(f"🔄 Marked interrupted task {task_record.id} as failed")

        except Exception as e:
            print(f"⚠️  Failed to mark task {task_record.id} as interrupted: {e}")

    def _map_state_to_redis_format(self, task_state: TaskState) -> str:
        """
        Map TaskState enum to Redis-compatible string format.
        """
        state_mapping = {
            TaskState.QUEUED: "queued",
            TaskState.STARTING: "starting",
            TaskState.RUNNING: "running",
            TaskState.PASSED: "passed",
            TaskState.FAILED: "failed",
            TaskState.ERROR: "error",
            TaskState.CANCELLED: "cancelled",
            TaskState.TIMEOUT: "failed",  # Map timeout to failed
            TaskState.PAUSED: "running",  # Map paused to running
            TaskState.COMPLETING: "running",  # Map completing to running
        }
        return state_mapping.get(task_state, "error")

    def recover_redis_from_backup(self, max_age_hours: int = 24) -> dict[str, int]:
        """
        Recover recent tasks from persistent storage to Redis.
        Only recovers tasks modified within the last max_age_hours.
        """
        print(f"🔄 Recovering recent tasks (last {max_age_hours} hours) to Redis...")

        recovery_stats = {"recovered": 0, "skipped": 0, "errors": 0}
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        try:
            # Get recent tasks
            from orchestrator.persistence_models import TaskSearchFilter

            filter_criteria = TaskSearchFilter(date_from=cutoff_time, limit=1000)
            recent_tasks = self.persistence_manager.get_all_tasks(filter_criteria)

            for task_record in recent_tasks:
                try:
                    # Check if task already exists in Redis
                    key = f"task_status:{task_record.id}"
                    if self.redis_client.exists(key):
                        recovery_stats["skipped"] += 1
                        continue

                    # Recover task
                    success = self._recover_single_task(task_record)
                    if success:
                        recovery_stats["recovered"] += 1
                    else:
                        recovery_stats["errors"] += 1

                except Exception as e:
                    print(f"⚠️  Error recovering recent task {task_record.id}: {e}")
                    recovery_stats["errors"] += 1

            print(f"✅ Recent task recovery completed: {recovery_stats}")

        except Exception as e:
            print(f"❌ Recent task recovery failed: {e}")
            recovery_stats["errors"] += 1

        return recovery_stats

    def cleanup_expired_redis_tasks(self, keep_hours: int = 48) -> int:
        """
        Clean up expired task entries from Redis based on persistent storage.
        Remove Redis entries for tasks older than keep_hours.
        """
        print(f"🧹 Cleaning up Redis task entries older than {keep_hours} hours...")

        cleaned_count = 0
        cutoff_time = datetime.utcnow() - timedelta(hours=keep_hours)

        try:
            # Get all task keys from Redis
            task_keys = self.redis_client.keys("task_status:*")

            for key in task_keys:
                try:
                    key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                    task_id = key_str.replace("task_status:", "")

                    # Get task from persistent storage
                    task_record = self.persistence_manager.get_task(task_id)

                    if not task_record:
                        # Task not in persistent storage, remove from Redis
                        self.redis_client.delete(key)
                        cleaned_count += 1
                        continue

                    # Check if task is old enough to cleanup
                    if task_record.updated_at < cutoff_time:
                        # Only cleanup if task is in terminal state
                        if task_record.state in [
                            TaskState.PASSED,
                            TaskState.FAILED,
                            TaskState.ERROR,
                            TaskState.CANCELLED,
                        ]:
                            self.redis_client.delete(key)
                            cleaned_count += 1

                except Exception as e:
                    print(f"⚠️  Error cleaning up Redis key {key}: {e}")

            if cleaned_count > 0:
                print(f"🧹 Cleaned up {cleaned_count} expired Redis task entries")

        except Exception as e:
            print(f"❌ Redis cleanup failed: {e}")

        return cleaned_count

    def verify_data_consistency(self) -> dict[str, any]:
        """
        Verify consistency between Redis and persistent storage.
        Returns report of inconsistencies found.
        """
        print("🔍 Verifying data consistency between Redis and persistent storage...")

        consistency_report = {
            "redis_only": [],  # Tasks in Redis but not in persistent storage
            "persistent_only": [],  # Tasks in persistent storage but not in Redis
            "state_mismatches": [],  # Tasks with different states
            "total_redis_tasks": 0,
            "total_persistent_tasks": 0,
            "consistent_tasks": 0,
        }

        try:
            # Get all Redis task keys
            redis_tasks = {}
            task_keys = self.redis_client.keys("task_status:*")
            consistency_report["total_redis_tasks"] = len(task_keys)

            for key in task_keys:
                try:
                    key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                    task_id = key_str.replace("task_status:", "")
                    task_data = self.redis_client.get(key)
                    if task_data:
                        task_status = TaskStatus.parse_raw(task_data)
                        redis_tasks[task_id] = task_status
                except Exception as e:
                    print(f"⚠️  Error reading Redis task {key}: {e}")

            # Get all persistent tasks
            persistent_tasks = {}
            all_persistent = self.persistence_manager.get_all_tasks()
            consistency_report["total_persistent_tasks"] = len(all_persistent)

            for task in all_persistent:
                persistent_tasks[task.id] = task

            # Find tasks only in Redis
            redis_only_ids = set(redis_tasks.keys()) - set(persistent_tasks.keys())
            consistency_report["redis_only"] = list(redis_only_ids)

            # Find tasks only in persistent storage
            persistent_only_ids = set(persistent_tasks.keys()) - set(redis_tasks.keys())
            consistency_report["persistent_only"] = list(persistent_only_ids)

            # Check for state mismatches
            common_ids = set(redis_tasks.keys()) & set(persistent_tasks.keys())
            for task_id in common_ids:
                redis_state = redis_tasks[task_id].state
                persistent_state = self._map_state_to_redis_format(persistent_tasks[task_id].state)

                if redis_state != persistent_state:
                    consistency_report["state_mismatches"].append(
                        {
                            "task_id": task_id,
                            "redis_state": redis_state,
                            "persistent_state": persistent_state,
                        }
                    )
                else:
                    consistency_report["consistent_tasks"] += 1

            # Print consistency report
            print("📊 Data consistency report:")
            print(f"   Redis tasks: {consistency_report['total_redis_tasks']}")
            print(f"   Persistent tasks: {consistency_report['total_persistent_tasks']}")
            print(f"   Consistent tasks: {consistency_report['consistent_tasks']}")
            print(f"   Redis-only tasks: {len(consistency_report['redis_only'])}")
            print(f"   Persistent-only tasks: {len(consistency_report['persistent_only'])}")
            print(f"   State mismatches: {len(consistency_report['state_mismatches'])}")

        except Exception as e:
            print(f"❌ Consistency check failed: {e}")
            consistency_report["error"] = str(e)

        return consistency_report


# Global recovery manager instance
_recovery_manager: TaskRecoveryManager | None = None


def get_recovery_manager() -> TaskRecoveryManager:
    """Get global recovery manager instance."""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = TaskRecoveryManager()
    return _recovery_manager


def run_startup_recovery() -> dict[str, int]:
    """
    Run task recovery on system startup.
    This function should be called during application initialization.
    """
    recovery_manager = get_recovery_manager()
    return recovery_manager.recover_tasks_on_startup()
