#!/usr/bin/env python3
"""
Comprehensive Thread Safety Testing for Agent Orchestrator

This script tests the thread safety of core components under concurrent load.
"""

import sys
import time
import threading
import tempfile
import shutil
import concurrent.futures
from pathlib import Path
import uuid

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.task_queue import TaskQueue, TaskStatus, Priority
from src.core.agent_spawner import AgentSpawner, AgentType
from src.core.context_manager import ContextManager
from src.core.database import DatabaseManager


class ThreadSafetyTester:
    """Test suite for concurrent operations"""

    def __init__(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="orchestrator_test_"))
        self.results = {}
        self.errors = []
        self.lock = threading.Lock()

    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Thread-safe result logging"""
        with self.lock:
            self.results[test_name] = {
                "success": success,
                "details": details,
                "timestamp": time.time(),
            }
            if not success:
                self.errors.append(f"{test_name}: {details}")

    def test_task_queue_concurrent_assignment(self):
        """Test concurrent task assignment without race conditions"""
        print("Testing TaskQueue concurrent assignment...")

        db_path = self.test_dir / "test_tasks.db"
        queue = TaskQueue(str(db_path))

        # Add test tasks
        task_ids = []
        for i in range(20):
            task_id = queue.add_task(f"Test task {i}", "claude", Priority.NORMAL)
            task_ids.append(task_id)

        # Simulate multiple agents trying to claim tasks concurrently
        assigned_tasks = []
        assignment_lock = threading.Lock()

        def agent_worker(agent_id: str):
            """Simulate an agent trying to claim and process tasks"""
            local_assignments = []
            try:
                for _ in range(5):  # Each agent tries to get 5 tasks
                    # Use atomic operation to get and assign task
                    task = queue.get_and_assign_next_task("claude", agent_id)
                    if task:
                        local_assignments.append(task.id)
                        # Simulate some work
                        time.sleep(0.01)
                        # Update task status
                        queue.update_status(
                            task.id, TaskStatus.COMPLETED, f"Completed by {agent_id}"
                        )

                with assignment_lock:
                    assigned_tasks.extend(local_assignments)

                return True
            except Exception as e:
                self.log_result(f"agent_{agent_id}_error", False, str(e))
                return False

        # Run multiple agents concurrently
        agents = [f"agent_{i}" for i in range(10)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(agent_worker, agent_id) for agent_id in agents]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Verify no duplicate assignments
        unique_assignments = set(assigned_tasks)
        success = len(assigned_tasks) == len(unique_assignments) and len(
            assigned_tasks
        ) <= len(task_ids)

        self.log_result(
            "task_queue_concurrent_assignment",
            success,
            f"Assigned {len(assigned_tasks)} tasks, {len(unique_assignments)} unique, {len(task_ids)} total",
        )

        return success

    def test_agent_spawner_concurrent_operations(self):
        """Test AgentSpawner thread safety with concurrent spawning/cleanup"""
        print("Testing AgentSpawner concurrent operations...")

        spawner = AgentSpawner(str(self.test_dir / "agents"), max_agents=5)
        spawned_agents = []
        spawn_lock = threading.Lock()

        def spawn_worker(worker_id: int):
            """Worker that spawns and monitors agents"""
            try:
                agent_id = spawner.spawn_agent(
                    AgentType.CLAUDE,
                    f"task_{worker_id}_{uuid.uuid4().hex[:8]}",
                    f"Test task from worker {worker_id}",
                    {"worker": worker_id},
                )

                with spawn_lock:
                    spawned_agents.append(agent_id)

                # Wait a bit then check status
                time.sleep(0.1)
                status = spawner.get_agent_status(agent_id)

                return status is not None
            except Exception as e:
                if "maximum number of agents" not in str(e).lower():
                    self.log_result(f"spawn_worker_{worker_id}_error", False, str(e))
                return False

        def cleanup_worker():
            """Worker that randomly cleans up agents"""
            try:
                time.sleep(0.05)  # Let some agents spawn first
                for _ in range(3):
                    with spawn_lock:
                        if spawned_agents:
                            agent_id = spawned_agents.pop(0)
                            spawner.cleanup_agent(agent_id)
                    time.sleep(0.02)
                return True
            except Exception as e:
                self.log_result("cleanup_worker_error", False, str(e))
                return False

        # Run concurrent spawn and cleanup operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # Spawn workers
            spawn_futures = [executor.submit(spawn_worker, i) for i in range(10)]
            # Cleanup workers
            cleanup_futures = [executor.submit(cleanup_worker) for _ in range(2)]

            spawn_results = [
                f.result() for f in concurrent.futures.as_completed(spawn_futures)
            ]
            cleanup_results = [
                f.result() for f in concurrent.futures.as_completed(cleanup_futures)
            ]

        # Clean up remaining agents
        spawner.cleanup_all()

        success = any(spawn_results) and all(cleanup_results)
        self.log_result(
            "agent_spawner_concurrent_operations",
            success,
            f"Spawn success: {sum(spawn_results)}/{len(spawn_results)}, Cleanup success: {sum(cleanup_results)}",
        )

        return success

    def test_context_manager_concurrent_access(self):
        """Test ContextManager file operations under concurrent access"""
        print("Testing ContextManager concurrent access...")

        cm = ContextManager(str(self.test_dir / "context"))
        operation_results = []
        results_lock = threading.Lock()

        def context_writer(worker_id: int):
            """Worker that writes context data"""
            try:
                # Write global context
                cm.set_global_context(
                    f"worker_{worker_id}", f"data_from_worker_{worker_id}"
                )

                # Write task context
                task_id = f"task_{worker_id}_{uuid.uuid4().hex[:8]}"
                cm.set_task_context(
                    task_id,
                    {
                        "worker": worker_id,
                        "data": f"context_data_{worker_id}",
                        "timestamp": time.time(),
                    },
                )

                # Add agent output
                cm.add_agent_output(
                    f"agent_{worker_id}",
                    task_id,
                    f"Output from worker {worker_id}",
                    {"lines": worker_id * 10},
                )

                # Share document
                cm.share_document(
                    f"doc_{worker_id}",
                    f"# Document {worker_id}\n\nContent from worker {worker_id}",
                    "md",
                )

                with results_lock:
                    operation_results.append(("writer", worker_id, True))

                return True
            except Exception as e:
                with results_lock:
                    operation_results.append(("writer", worker_id, False))
                self.log_result(f"context_writer_{worker_id}_error", False, str(e))
                return False

        def context_reader(worker_id: int):
            """Worker that reads context data"""
            try:
                time.sleep(0.05)  # Let writers start first

                # Read some global context
                for i in range(5):
                    value = cm.get_global_context(f"worker_{i}")
                    # Value might be None if writer hasn't finished yet

                # Read shared documents
                docs = cm.list_shared_documents()

                # Read task contexts (might be empty initially)
                stats = cm.get_context_stats()

                with results_lock:
                    operation_results.append(("reader", worker_id, True))

                return True
            except Exception as e:
                with results_lock:
                    operation_results.append(("reader", worker_id, False))
                self.log_result(f"context_reader_{worker_id}_error", False, str(e))
                return False

        # Run concurrent read/write operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            # Writers
            write_futures = [executor.submit(context_writer, i) for i in range(8)]
            # Readers
            read_futures = [executor.submit(context_reader, i) for i in range(4)]

            write_results = [
                f.result() for f in concurrent.futures.as_completed(write_futures)
            ]
            read_results = [
                f.result() for f in concurrent.futures.as_completed(read_futures)
            ]

        success = all(write_results) and all(read_results)
        successful_ops = sum(1 for _, _, success in operation_results if success)

        self.log_result(
            "context_manager_concurrent_access",
            success,
            f"Successful operations: {successful_ops}/{len(operation_results)}",
        )

        return success

    def test_database_concurrent_transactions(self):
        """Test database connection pooling and concurrent transactions"""
        print("Testing database concurrent transactions...")

        db_path = self.test_dir / "test_concurrent.db"
        db = DatabaseManager(str(db_path))

        # Initialize test schema
        schema = """
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                value TEXT,
                thread_id TEXT,
                timestamp REAL
            )
        """
        db.init_schema(schema)

        transaction_results = []
        results_lock = threading.Lock()

        def db_worker(worker_id: int):
            """Worker that performs database operations"""
            try:
                thread_id = f"thread_{worker_id}"

                # Perform multiple operations
                for i in range(5):
                    # Insert data
                    insert_query = "INSERT INTO test_table (value, thread_id, timestamp) VALUES (?, ?, ?)"
                    params = (f"value_{worker_id}_{i}", thread_id, time.time())
                    rows_affected = db.execute_update(insert_query, params)

                    if rows_affected != 1:
                        raise Exception(f"Insert failed for worker {worker_id}")

                    # Read data
                    select_query = (
                        "SELECT COUNT(*) as count FROM test_table WHERE thread_id = ?"
                    )
                    results = db.execute_query(select_query, (thread_id,))
                    count = results[0]["count"] if results else 0

                    time.sleep(0.001)  # Small delay to increase concurrency

                with results_lock:
                    transaction_results.append((worker_id, True))

                return True
            except Exception as e:
                with results_lock:
                    transaction_results.append((worker_id, False))
                self.log_result(f"db_worker_{worker_id}_error", False, str(e))
                return False

        # Run concurrent database operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(db_worker, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Verify data integrity
        final_count_result = db.execute_query(
            "SELECT COUNT(*) as total FROM test_table"
        )
        total_records = final_count_result[0]["total"] if final_count_result else 0

        success = all(results) and total_records == 50  # 10 workers * 5 inserts each
        successful_transactions = sum(
            1 for _, success in transaction_results if success
        )

        self.log_result(
            "database_concurrent_transactions",
            success,
            f"Successful transactions: {successful_transactions}/{len(transaction_results)}, Total records: {total_records}",
        )

        return success

    def test_mixed_operations(self):
        """Test all components working together under concurrent load"""
        print("Testing mixed concurrent operations...")

        # Initialize all components
        queue = TaskQueue(str(self.test_dir / "mixed_tasks.db"))
        spawner = AgentSpawner(str(self.test_dir / "mixed_agents"), max_agents=3)
        cm = ContextManager(str(self.test_dir / "mixed_context"))

        mixed_results = []
        results_lock = threading.Lock()

        def mixed_worker(worker_id: int):
            """Worker that uses all components"""
            try:
                # Add task to queue
                task_id = queue.add_task(
                    f"Mixed task from worker {worker_id}",
                    "claude",
                    Priority.NORMAL,
                    {"worker": worker_id},
                )

                # Set context
                cm.set_task_context(
                    task_id, {"step": "initialized", "worker": worker_id}
                )

                # Try to spawn agent (might fail due to limit)
                try:
                    agent_id = spawner.spawn_agent(
                        AgentType.CLAUDE,
                        task_id,
                        f"Process task {task_id}",
                        {"worker": worker_id},
                    )
                    spawned = True
                except Exception:
                    spawned = False

                # Update task status
                if spawned:
                    queue.update_status(task_id, TaskStatus.IN_PROGRESS)
                    time.sleep(0.02)
                    queue.update_status(
                        task_id,
                        TaskStatus.COMPLETED,
                        f"Completed by worker {worker_id}",
                    )
                else:
                    # Manually assign and complete
                    if queue.assign_task(task_id, f"manual_agent_{worker_id}"):
                        queue.update_status(
                            task_id,
                            TaskStatus.COMPLETED,
                            f"Manually completed by worker {worker_id}",
                        )

                # Add output
                cm.add_agent_output(
                    f"agent_{worker_id}",
                    task_id,
                    f"Output from mixed worker {worker_id}",
                    {"spawned": spawned},
                )

                with results_lock:
                    mixed_results.append((worker_id, True))

                return True
            except Exception as e:
                with results_lock:
                    mixed_results.append((worker_id, False))
                self.log_result(f"mixed_worker_{worker_id}_error", False, str(e))
                return False

        # Run mixed operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(mixed_worker, i) for i in range(12)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Clean up
        spawner.cleanup_all()

        success = (
            sum(results) >= len(results) * 0.8
        )  # Allow 20% failure due to resource limits
        successful_mixed = sum(1 for _, success in mixed_results if success)

        self.log_result(
            "mixed_operations",
            success,
            f"Successful mixed operations: {successful_mixed}/{len(mixed_results)}",
        )

        return success

    def run_all_tests(self):
        """Run all thread safety tests"""
        print("Starting comprehensive thread safety tests...\n")

        tests = [
            self.test_task_queue_concurrent_assignment,
            self.test_agent_spawner_concurrent_operations,
            self.test_context_manager_concurrent_access,
            self.test_database_concurrent_transactions,
            self.test_mixed_operations,
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_result(test.__name__, False, f"Test crashed: {e}")

        print("\n" + "=" * 60)
        print("THREAD SAFETY TEST RESULTS")
        print("=" * 60)

        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result["success"])

        for test_name, result in self.results.items():
            status = "PASS" if result["success"] else "FAIL"
            print(f"{status:4} | {test_name:40} | {result['details']}")

        print("-" * 60)
        print(f"Total: {passed_tests}/{total_tests} tests passed")

        if self.errors:
            print("\nErrors encountered:")
            for error in self.errors:
                print(f"  - {error}")

        return passed_tests == total_tests

    def cleanup(self):
        """Clean up test directory"""
        try:
            if self.test_dir.exists():
                shutil.rmtree(self.test_dir)
        except Exception as e:
            print(f"Cleanup warning: {e}")


def main():
    """Main test execution"""
    tester = ThreadSafetyTester()

    try:
        success = tester.run_all_tests()

        if success:
            print("\n✅ All thread safety tests PASSED!")
            return 0
        else:
            print("\n❌ Some thread safety tests FAILED!")
            return 1

    finally:
        tester.cleanup()


if __name__ == "__main__":
    exit(main())
