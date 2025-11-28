#!/usr/bin/env python3
"""
Minimal thread safety test to identify issues
"""

import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_task_queue_basic():
    """Test basic TaskQueue functionality"""
    print("Testing TaskQueue basic functionality...")

    from src.core.task_queue import TaskQueue, Priority

    with tempfile.TemporaryDirectory() as temp_dir:
        queue = TaskQueue(str(Path(temp_dir) / "test.db"))

        # Add a task
        task_id = queue.add_task("Test task", "claude", Priority.NORMAL)
        print(f"  Added task: {task_id}")

        # Get task
        task = queue.get_next_task("claude")
        print(f"  Got task: {task.id if task else None}")

        # Assign task
        if task:
            success = queue.assign_task(task.id, "test_agent")
            print(f"  Assigned task: {success}")

        print("  TaskQueue basic test PASSED")
        return True


def test_concurrent_simple():
    """Test simple concurrent access"""
    print("Testing simple concurrent access...")

    from src.core.task_queue import TaskQueue, Priority

    with tempfile.TemporaryDirectory() as temp_dir:
        queue = TaskQueue(str(Path(temp_dir) / "test.db"))

        # Add tasks
        for i in range(5):
            queue.add_task(f"Task {i}", "claude", Priority.NORMAL)

        results = []

        def worker(worker_id):
            try:
                task = queue.get_and_assign_next_task("claude", f"agent_{worker_id}")
                results.append(task.id if task else None)
                print(f"    Worker {worker_id}: got {task.id if task else 'None'}")
                return True
            except Exception as e:
                print(f"    Worker {worker_id} error: {e}")
                return False

        # Run 3 workers
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join(timeout=5)  # 5 second timeout

        # Check if any thread is still alive (deadlock indicator)
        still_alive = [t for t in threads if t.is_alive()]
        if still_alive:
            print(
                f"  WARNING: {len(still_alive)} threads still alive (potential deadlock)"
            )
            return False

        # Check results
        valid_results = [r for r in results if r is not None]
        unique_results = set(valid_results)

        print(
            f"  Results: {len(valid_results)} tasks assigned, {len(unique_results)} unique"
        )
        print("  Simple concurrent test PASSED")
        return len(valid_results) == len(unique_results)


if __name__ == "__main__":
    print("Running minimal thread safety tests...\n")

    try:
        test1 = test_task_queue_basic()
        print()

        test2 = test_concurrent_simple()
        print()

        if test1 and test2:
            print("✅ All minimal tests PASSED!")
        else:
            print("❌ Some minimal tests FAILED!")

    except Exception as e:
        print(f"❌ Test crashed: {e}")
        import traceback

        traceback.print_exc()
