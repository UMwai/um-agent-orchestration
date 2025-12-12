"""
Parallel Executor for Concurrent Agent Task Execution

Enables multiple independent tasks to run concurrently using ThreadPoolExecutor,
significantly improving throughput for complex multi-step orchestration tasks.
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, Future, TimeoutError
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Set
from threading import Lock, Event
from enum import Enum

logger = logging.getLogger(__name__)

# Maximum total timeout for all tasks in a batch (1 hour)
MAX_TOTAL_TIMEOUT = 3600.0

# Circuit breaker configuration
CIRCUIT_BREAKER_THRESHOLD = 5  # Failures before opening
CIRCUIT_BREAKER_COOLDOWN = 60.0  # Seconds before attempting half-open


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected in task graph"""
    pass


class ExecutionStatus(Enum):
    """Status of a parallel execution batch"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class TaskResult:
    """Result from a single task execution"""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    worker_id: Optional[str] = None


@dataclass
class ParallelExecutionResult:
    """Aggregated result from parallel execution"""
    batch_id: str
    status: ExecutionStatus
    results: List[TaskResult] = field(default_factory=list)
    total_tasks: int = 0
    successful: int = 0
    failed: int = 0
    total_time: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.successful / self.total_tasks

    @property
    def error_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.failed / self.total_tasks


class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing if system recovered, allow limited requests
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD,
        cooldown_period: float = CIRCUIT_BREAKER_COOLDOWN,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_period = cooldown_period

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self._lock:
            if self._state == CircuitBreakerState.OPEN:
                # Check if cooldown period has elapsed
                if self._last_failure_time and \
                   (time.time() - self._last_failure_time) >= self.cooldown_period:
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._failure_count = 0
                    logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise RuntimeError("Circuit breaker is OPEN, rejecting request")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful execution"""
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.CLOSED
                logger.info("Circuit breaker closed after successful recovery")
            self._failure_count = 0

    def _on_failure(self):
        """Handle failed execution"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                logger.error(
                    f"Circuit breaker opened after {self._failure_count} failures"
                )

    def reset(self):
        """Manually reset circuit breaker to CLOSED state"""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            logger.info("Circuit breaker manually reset to CLOSED")

    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state"""
        with self._lock:
            return self._state


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts delay based on error rates.

    Implements exponential backoff on failures and returns to normal
    operation when errors decrease.
    """

    def __init__(
        self,
        base_delay: float = 0.1,
        max_delay: float = 5.0,
        backoff_multiplier: float = 2.0,
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier

        self._current_delay = base_delay
        self._consecutive_errors = 0
        self._lock = Lock()

    def wait(self):
        """Wait according to current rate limit"""
        with self._lock:
            delay = self._current_delay

        if delay > 0:
            time.sleep(delay)

    def on_success(self):
        """Record successful execution, reduce delay"""
        with self._lock:
            self._consecutive_errors = 0
            # Gradually return to base delay
            if self._current_delay > self.base_delay:
                self._current_delay = max(
                    self.base_delay,
                    self._current_delay / self.backoff_multiplier
                )

    def on_error(self):
        """Record failed execution, increase delay"""
        with self._lock:
            self._consecutive_errors += 1
            # Exponential backoff
            self._current_delay = min(
                self.max_delay,
                self._current_delay * self.backoff_multiplier
            )
            logger.warning(
                f"Rate limiter increased delay to {self._current_delay:.2f}s "
                f"after {self._consecutive_errors} consecutive errors"
            )

    def get_current_delay(self) -> float:
        """Get current delay value"""
        with self._lock:
            return self._current_delay

    def reset(self):
        """Reset to base delay"""
        with self._lock:
            self._current_delay = self.base_delay
            self._consecutive_errors = 0


class ParallelExecutor:
    """
    Execute multiple agent tasks in parallel using ThreadPoolExecutor.

    Features:
    - Configurable worker pool size
    - Dependency-aware execution with phases
    - Result aggregation and error propagation
    - Progress callbacks for monitoring
    - Graceful shutdown and cancellation
    - Circuit breaker for fault tolerance
    - Adaptive rate limiting based on errors
    - Health check monitoring
    """

    def __init__(
        self,
        max_workers: int = 5,
        timeout_per_task: float = 300.0,  # 5 minutes default
        rate_limit_delay: float = 0.1,     # Base delay between task submissions
        enable_circuit_breaker: bool = True,
    ):
        self.max_workers = max_workers
        self.timeout_per_task = timeout_per_task
        self.enable_circuit_breaker = enable_circuit_breaker

        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_futures: Dict[str, Future] = {}
        self._lock = Lock()
        self._shutdown_event = Event()
        self._batch_counter = 0

        # Circuit breaker for fault tolerance
        self._circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None

        # Adaptive rate limiter
        self._rate_limiter = AdaptiveRateLimiter(base_delay=rate_limit_delay)

        # Health metrics
        self._total_tasks_executed = 0
        self._total_errors = 0
        self._start_time = time.time()

    def _get_batch_id(self) -> str:
        with self._lock:
            self._batch_counter += 1
            return f"batch_{self._batch_counter}_{int(time.time())}"

    def execute_parallel(
        self,
        tasks: List[Dict[str, Any]],
        executor_func: Callable[[Dict[str, Any]], Any],
        on_task_complete: Optional[Callable[[TaskResult], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> ParallelExecutionResult:
        """
        Execute multiple tasks concurrently.

        Args:
            tasks: List of task dictionaries with at least 'task_id' and task data
            executor_func: Function to execute each task, receives task dict
            on_task_complete: Optional callback for each completed task
            on_progress: Optional callback for progress updates (completed, total)

        Returns:
            ParallelExecutionResult with aggregated results
        """
        batch_id = self._get_batch_id()
        start_time = time.time()
        results: List[TaskResult] = []

        if not tasks:
            return ParallelExecutionResult(
                batch_id=batch_id,
                status=ExecutionStatus.COMPLETED,
                total_tasks=0,
            )

        logger.info(f"Starting parallel execution batch {batch_id} with {len(tasks)} tasks")

        # Calculate timeout with safety cap
        batch_timeout = min(
            self.timeout_per_task * len(tasks),
            MAX_TOTAL_TIMEOUT
        )
        logger.info(f"Batch timeout set to {batch_timeout:.1f}s (max: {MAX_TOTAL_TIMEOUT}s)")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            self._executor = executor
            futures: Dict[Future, str] = {}

            # Submit all tasks with adaptive rate limiting
            for i, task in enumerate(tasks):
                if self._shutdown_event.is_set():
                    logger.warning("Shutdown requested, stopping task submission")
                    break

                task_id = task.get("task_id", f"task_{i}")
                future = executor.submit(self._execute_single, task, executor_func)
                futures[future] = task_id

                with self._lock:
                    self._active_futures[task_id] = future

                # Adaptive rate limiting between submissions
                if i < len(tasks) - 1:
                    self._rate_limiter.wait()

            # Collect results as they complete
            completed = 0
            try:
                for future in as_completed(futures, timeout=batch_timeout):
                    task_id = futures[future]

                    try:
                        result = future.result(timeout=self.timeout_per_task)
                        results.append(result)

                        # Update rate limiter based on result
                        if result.success:
                            self._rate_limiter.on_success()
                        else:
                            self._rate_limiter.on_error()

                    except TimeoutError:
                        logger.error(f"Task {task_id} timed out after {self.timeout_per_task}s")
                        results.append(TaskResult(
                            task_id=task_id,
                            success=False,
                            error=f"Task timeout after {self.timeout_per_task}s",
                        ))
                        self._rate_limiter.on_error()
                    except Exception as e:
                        logger.error(f"Task {task_id} failed: {e}")
                        results.append(TaskResult(
                            task_id=task_id,
                            success=False,
                            error=str(e),
                        ))
                        self._rate_limiter.on_error()

                    completed += 1

                    if on_task_complete:
                        on_task_complete(results[-1])

                    if on_progress:
                        on_progress(completed, len(tasks))

                    with self._lock:
                        self._active_futures.pop(task_id, None)

            except TimeoutError:
                logger.error(f"Batch {batch_id} timed out after {batch_timeout}s")
                # Cancel remaining futures
                for future, task_id in futures.items():
                    if not future.done():
                        future.cancel()
                        results.append(TaskResult(
                            task_id=task_id,
                            success=False,
                            error=f"Batch timeout after {batch_timeout}s",
                        ))

        self._executor = None
        end_time = time.time()

        # Update health metrics
        with self._lock:
            self._total_tasks_executed += len(tasks)
            failed = sum(1 for r in results if not r.success)
            self._total_errors += failed

        # Aggregate results
        successful = sum(1 for r in results if r.success)

        status = ExecutionStatus.COMPLETED
        if failed == len(results):
            status = ExecutionStatus.FAILED
        elif failed > 0:
            status = ExecutionStatus.PARTIAL_FAILURE

        return ParallelExecutionResult(
            batch_id=batch_id,
            status=status,
            results=results,
            total_tasks=len(tasks),
            successful=successful,
            failed=failed,
            total_time=end_time - start_time,
        )

    def _execute_single(
        self,
        task: Dict[str, Any],
        executor_func: Callable[[Dict[str, Any]], Any],
    ) -> TaskResult:
        """Execute a single task and wrap result"""
        task_id = task.get("task_id", "unknown")
        start_time = time.time()

        try:
            # Use circuit breaker if enabled
            if self._circuit_breaker and self.enable_circuit_breaker:
                result = self._circuit_breaker.call(executor_func, task)
            else:
                result = executor_func(task)

            return TaskResult(
                task_id=task_id,
                success=True,
                result=result,
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            return TaskResult(
                task_id=task_id,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    def execute_phases(
        self,
        phases: List[List[Dict[str, Any]]],
        executor_func: Callable[[Dict[str, Any]], Any],
        on_phase_complete: Optional[Callable[[int, ParallelExecutionResult], None]] = None,
    ) -> List[ParallelExecutionResult]:
        """
        Execute tasks in dependency-ordered phases.

        Each phase contains independent tasks that can run in parallel.
        Phases are executed sequentially (phase N must complete before phase N+1).

        Args:
            phases: List of phases, each phase is a list of task dicts
            executor_func: Function to execute each task
            on_phase_complete: Optional callback after each phase completes

        Returns:
            List of ParallelExecutionResult, one per phase
        """
        phase_results: List[ParallelExecutionResult] = []

        for phase_num, phase_tasks in enumerate(phases):
            logger.info(f"Executing phase {phase_num + 1}/{len(phases)} with {len(phase_tasks)} tasks")

            result = self.execute_parallel(phase_tasks, executor_func)
            phase_results.append(result)

            if on_phase_complete:
                on_phase_complete(phase_num, result)

            # Stop if a critical phase fails completely
            if result.status == ExecutionStatus.FAILED:
                logger.error(f"Phase {phase_num + 1} failed completely, stopping execution")
                break

        return phase_results

    def cancel_all(self, timeout: float = 30.0):
        """
        Cancel all pending tasks and wait for running tasks to complete.

        Args:
            timeout: Maximum seconds to wait for tasks to complete (default: 30s)
        """
        logger.info(f"Cancelling all tasks with {timeout}s timeout")
        self._shutdown_event.set()

        start_time = time.time()

        with self._lock:
            active_futures = list(self._active_futures.items())

        # First, cancel all pending futures
        for task_id, future in active_futures:
            if not future.done():
                future.cancel()
                logger.info(f"Cancelled task {task_id}")

        # Wait for running tasks to complete or timeout
        elapsed = 0.0
        while elapsed < timeout:
            with self._lock:
                if not self._active_futures:
                    logger.info("All tasks completed or cancelled")
                    break

                running_count = sum(
                    1 for f in self._active_futures.values()
                    if not f.done()
                )

            if running_count == 0:
                break

            time.sleep(0.5)
            elapsed = time.time() - start_time

        # Force-clear any remaining futures after timeout
        with self._lock:
            if self._active_futures:
                logger.warning(
                    f"Force-terminating {len(self._active_futures)} tasks "
                    f"after {timeout}s timeout"
                )
                self._active_futures.clear()

        # Shutdown executor if active
        if self._executor:
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception as e:
                logger.error(f"Error shutting down executor: {e}")
            finally:
                self._executor = None

    def get_status(self) -> Dict[str, Any]:
        """Get current executor status"""
        with self._lock:
            return {
                "max_workers": self.max_workers,
                "active_tasks": len(self._active_futures),
                "active_task_ids": list(self._active_futures.keys()),
                "is_running": self._executor is not None,
                "shutdown_requested": self._shutdown_event.is_set(),
            }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check and return status information.

        Returns:
            Dictionary containing:
            - worker_count: Number of workers
            - active_tasks: Currently running tasks
            - error_rate: Overall error rate
            - total_tasks: Total tasks executed
            - total_errors: Total errors encountered
            - uptime: Seconds since executor creation
            - circuit_breaker_state: Circuit breaker state (if enabled)
            - rate_limiter_delay: Current rate limiter delay
        """
        with self._lock:
            total_tasks = self._total_tasks_executed
            total_errors = self._total_errors
            error_rate = total_errors / total_tasks if total_tasks > 0 else 0.0

            health = {
                "worker_count": self.max_workers,
                "active_tasks": len(self._active_futures),
                "error_rate": error_rate,
                "total_tasks": total_tasks,
                "total_errors": total_errors,
                "uptime": time.time() - self._start_time,
                "is_healthy": error_rate < 0.5,  # Healthy if error rate < 50%
            }

            if self._circuit_breaker:
                health["circuit_breaker_state"] = self._circuit_breaker.get_state().value

            health["rate_limiter_delay"] = self._rate_limiter.get_current_delay()

            return health


class DependencyAwareExecutor(ParallelExecutor):
    """
    Extended executor that handles task dependencies automatically.

    Tasks can specify dependencies on other tasks. The executor will
    automatically organize tasks into phases based on their dependencies.
    """

    def execute_with_dependencies(
        self,
        tasks: List[Dict[str, Any]],
        executor_func: Callable[[Dict[str, Any]], Any],
        dependency_key: str = "dependencies",
    ) -> List[ParallelExecutionResult]:
        """
        Execute tasks respecting their dependencies.

        Each task dict can have a 'dependencies' field listing task_ids
        that must complete before this task runs.

        Args:
            tasks: List of task dicts with optional dependencies field
            executor_func: Function to execute each task
            dependency_key: Key in task dict containing dependency list

        Returns:
            List of ParallelExecutionResult, one per auto-generated phase

        Raises:
            CircularDependencyError: If circular dependencies are detected
        """
        phases = self._topological_sort(tasks, dependency_key)
        return self.execute_phases(phases, executor_func)

    def _topological_sort(
        self,
        tasks: List[Dict[str, Any]],
        dependency_key: str,
    ) -> List[List[Dict[str, Any]]]:
        """
        Sort tasks into phases based on dependencies using Kahn's algorithm.

        Raises:
            CircularDependencyError: If circular dependencies are detected
        """
        # Build task lookup
        task_map = {t.get("task_id", f"task_{i}"): t for i, t in enumerate(tasks)}

        # Calculate in-degrees
        in_degree: Dict[str, int] = {tid: 0 for tid in task_map}
        for tid, task in task_map.items():
            deps = task.get(dependency_key, [])
            in_degree[tid] = len([d for d in deps if d in task_map])

        phases = []
        remaining = set(task_map.keys())
        initial_count = len(remaining)

        while remaining:
            # Find tasks with no pending dependencies
            ready = [tid for tid in remaining if in_degree[tid] == 0]

            if not ready:
                # Circular dependency detected - construct error message
                remaining_tasks = list(remaining)
                dependency_info = []
                for tid in remaining_tasks[:5]:  # Show first 5
                    deps = task_map[tid].get(dependency_key, [])
                    dependency_info.append(f"  {tid} -> {deps}")

                error_msg = (
                    f"Circular dependency detected in task graph. "
                    f"{len(remaining)} of {initial_count} tasks cannot be scheduled.\n"
                    f"Sample dependencies:\n" + "\n".join(dependency_info)
                )
                logger.error(error_msg)
                raise CircularDependencyError(error_msg)

            # Add ready tasks as a new phase
            phases.append([task_map[tid] for tid in ready])

            # Update in-degrees for dependent tasks
            for tid in ready:
                remaining.remove(tid)
                # Reduce in-degree for tasks that depend on completed tasks
                for other_tid in remaining:
                    deps = task_map[other_tid].get(dependency_key, [])
                    if tid in deps:
                        in_degree[other_tid] -= 1

        logger.info(f"Organized {len(tasks)} tasks into {len(phases)} dependency phases")
        return phases


if __name__ == "__main__":
    # Demo usage
    import random

    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Parallel Executor Demo")
    print("=" * 60)

    # Create sample tasks
    tasks = [
        {"task_id": f"task_{i}", "description": f"Task {i}", "data": i}
        for i in range(10)
    ]

    # Simple executor function with random failures
    def execute_task(task):
        time.sleep(random.uniform(0.1, 0.5))  # Simulate work
        if random.random() < 0.1:  # 10% failure rate
            raise RuntimeError(f"Random failure in {task['task_id']}")
        return f"Completed: {task['description']}"

    # Test 1: Basic parallel execution
    print("\n--- Test 1: Basic Parallel Execution ---")
    executor = ParallelExecutor(max_workers=3)

    def on_progress(completed, total):
        print(f"Progress: {completed}/{total}")

    result = executor.execute_parallel(
        tasks,
        execute_task,
        on_progress=on_progress,
    )

    print(f"\nBatch: {result.batch_id}")
    print(f"Status: {result.status.value}")
    print(f"Success rate: {result.success_rate:.1%}")
    print(f"Total time: {result.total_time:.2f}s")
    print(f"Successful: {result.successful}/{result.total_tasks}")

    # Test 2: Health check
    print("\n--- Test 2: Health Check ---")
    health = executor.health_check()
    for key, value in health.items():
        print(f"{key}: {value}")

    # Test 3: Dependency-aware execution
    print("\n--- Test 3: Dependency-Aware Execution ---")
    dep_tasks = [
        {"task_id": "task_a", "description": "Task A", "dependencies": []},
        {"task_id": "task_b", "description": "Task B", "dependencies": ["task_a"]},
        {"task_id": "task_c", "description": "Task C", "dependencies": ["task_a"]},
        {"task_id": "task_d", "description": "Task D", "dependencies": ["task_b", "task_c"]},
    ]

    dep_executor = DependencyAwareExecutor(max_workers=2)

    def simple_task(task):
        print(f"  Executing: {task['task_id']}")
        time.sleep(0.2)
        return f"Done: {task['task_id']}"

    dep_results = dep_executor.execute_with_dependencies(dep_tasks, simple_task)

    print(f"\nExecuted {len(dep_results)} phases:")
    for i, phase_result in enumerate(dep_results):
        print(f"  Phase {i+1}: {phase_result.total_tasks} tasks, "
              f"{phase_result.successful} successful")

    # Test 4: Circular dependency detection
    print("\n--- Test 4: Circular Dependency Detection ---")
    circular_tasks = [
        {"task_id": "task_x", "dependencies": ["task_y"]},
        {"task_id": "task_y", "dependencies": ["task_z"]},
        {"task_id": "task_z", "dependencies": ["task_x"]},
    ]

    try:
        dep_executor.execute_with_dependencies(circular_tasks, simple_task)
        print("ERROR: Should have raised CircularDependencyError")
    except CircularDependencyError as e:
        print(f"Correctly detected circular dependency: {str(e)[:100]}...")

    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)
