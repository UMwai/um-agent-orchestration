"""
CLI Process Manager for um-agent-orchestration

This module provides comprehensive management of CLI processes (claude, codex, gemini)
with proper lifecycle management, resource limits, process isolation, and async output streaming.
"""

from __future__ import annotations

import asyncio
import logging
import os
import resource
import subprocess
import threading
import time
from asyncio import Queue
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import psutil

from orchestrator.settings import ProviderCfg

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a managed CLI process."""

    id: str
    provider_name: str
    binary: str
    args: list[str]
    process: subprocess.Popen | None = None
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    cwd: str | None = None
    session_mode: bool = False  # True for interactive/session processes
    output_queue: Queue | None = None
    error_queue: Queue | None = None
    resource_usage: dict[str, Any] = field(default_factory=dict)

    @property
    def is_alive(self) -> bool:
        """Check if the process is still running."""
        return self.process is not None and self.process.poll() is None

    @property
    def idle_time(self) -> float:
        """Get the time since last access in seconds."""
        return time.time() - self.last_accessed

    def update_access_time(self) -> None:
        """Update the last accessed timestamp."""
        self.last_accessed = time.time()


@dataclass
class ResourceLimits:
    """Resource limits for CLI processes."""

    max_memory_mb: int = 2048  # 2GB memory limit per process
    max_cpu_percent: float = 80.0  # 80% CPU limit
    max_file_descriptors: int = 1024
    max_execution_time: int = 300  # 5 minutes default timeout


class ProcessPoolError(Exception):
    """Base exception for process pool errors."""

    pass


class ProcessLimitError(ProcessPoolError):
    """Raised when process limit is exceeded."""

    pass


class ProcessTimeoutError(ProcessPoolError):
    """Raised when process times out."""

    pass


class ResourceLimitError(ProcessPoolError):
    """Raised when resource limits are exceeded."""

    pass


class CLIProcessManager:
    """
    Manages CLI processes with lifecycle management, resource limits, and process isolation.

    Features:
    - Process pool management with configurable limits
    - Resource limit enforcement (memory, CPU, file descriptors)
    - Async output streaming with proper buffering
    - Process isolation and sandboxing
    - Graceful shutdown and cleanup
    - Health monitoring and idle timeout
    """

    def __init__(
        self,
        max_processes: int = 20,
        idle_timeout: int = 300,  # 5 minutes
        resource_limits: ResourceLimits | None = None,
        enable_monitoring: bool = True,
    ):
        self.max_processes = max_processes
        self.idle_timeout = idle_timeout
        self.resource_limits = resource_limits or ResourceLimits()
        self.enable_monitoring = enable_monitoring

        # Process tracking
        self.processes: dict[str, ProcessInfo] = {}
        self.provider_processes: dict[str, set[str]] = defaultdict(set)
        self._lock = threading.RLock()

        # Monitoring and cleanup
        self._monitoring_task: asyncio.Task | None = None
        self._shutdown_event = threading.Event()

        logger.info(
            f"CLI Process Manager initialized: max_processes={max_processes}, "
            f"idle_timeout={idle_timeout}s, monitoring={enable_monitoring}"
        )

    async def start_monitoring(self) -> None:
        """Start background monitoring tasks."""
        if not self.enable_monitoring or self._monitoring_task:
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Process monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop background monitoring tasks."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            logger.info("Process monitoring stopped")

    async def spawn_process(
        self,
        provider_name: str,
        cfg: ProviderCfg,
        cwd: str | None = None,
        session_mode: bool = False,
        timeout: int | None = None,
    ) -> str:
        """
        Spawn a new CLI process.

        Args:
            provider_name: Name of the provider (e.g., 'claude_cli', 'codex_cli')
            cfg: Provider configuration
            cwd: Working directory for the process
            session_mode: True for interactive/session processes
            timeout: Process timeout in seconds

        Returns:
            Process ID for the spawned process

        Raises:
            ProcessLimitError: If max processes limit is exceeded
            ProcessPoolError: If process spawning fails
        """
        with self._lock:
            # Check process limits
            if len(self.processes) >= self.max_processes:
                await self._cleanup_idle_processes()
                if len(self.processes) >= self.max_processes:
                    raise ProcessLimitError(
                        f"Maximum process limit ({self.max_processes}) exceeded"
                    )

            # Generate unique process ID
            process_id = str(uuid4())

            # Prepare process arguments
            binary = cfg.binary or provider_name.replace("_cli", "")
            args = cfg.args or []

            logger.info(f"Spawning process {process_id}: {binary} {' '.join(args)}")

            try:
                # Set up resource limits
                preexec_fn = self._setup_resource_limits if os.name == "posix" else None

                # Create process info
                process_info = ProcessInfo(
                    id=process_id,
                    provider_name=provider_name,
                    binary=binary,
                    args=args,
                    cwd=cwd,
                    session_mode=session_mode,
                )

                # Set up async queues for output streaming
                if session_mode:
                    process_info.output_queue = Queue()
                    process_info.error_queue = Queue()

                # Start the process
                if session_mode:
                    # Interactive process - keep stdin open
                    process = subprocess.Popen(
                        [binary] + args,
                        cwd=cwd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=0,
                        preexec_fn=preexec_fn,
                    )

                    # Start output streaming tasks
                    asyncio.create_task(
                        self._stream_output(process, process_info.output_queue, "stdout")
                    )
                    asyncio.create_task(
                        self._stream_output(process, process_info.error_queue, "stderr")
                    )
                else:
                    # One-shot process - will be used with send_command
                    process = None  # Will be created when needed

                process_info.process = process

                # Register the process
                self.processes[process_id] = process_info
                self.provider_processes[provider_name].add(process_id)

                logger.info(f"Process {process_id} spawned successfully")
                return process_id

            except Exception as e:
                logger.error(f"Failed to spawn process {process_id}: {e}")
                raise ProcessPoolError(f"Process spawning failed: {e}") from e

    async def send_command(
        self, process_id: str, command: str, timeout: int | None = None
    ) -> tuple[str, str]:
        """
        Send a command to a managed process.

        Args:
            process_id: ID of the target process
            command: Command to send
            timeout: Command timeout in seconds

        Returns:
            Tuple of (stdout, stderr)

        Raises:
            ProcessPoolError: If process not found or command fails
            ProcessTimeoutError: If command times out
        """
        with self._lock:
            if process_id not in self.processes:
                raise ProcessPoolError(f"Process {process_id} not found")

            process_info = self.processes[process_id]
            process_info.update_access_time()

        timeout = timeout or self.resource_limits.max_execution_time

        try:
            if process_info.session_mode:
                # Interactive process - send command to stdin
                return await self._send_interactive_command(process_info, command, timeout)
            else:
                # One-shot process - create new process for this command
                return await self._run_oneshot_command(process_info, command, timeout)

        except TimeoutError:
            logger.error(f"Command timeout for process {process_id}")
            raise ProcessTimeoutError(f"Command timed out after {timeout}s")
        except Exception as e:
            logger.error(f"Command failed for process {process_id}: {e}")
            raise ProcessPoolError(f"Command execution failed: {e}") from e

    async def terminate_process(self, process_id: str, force: bool = False) -> bool:
        """
        Terminate a managed process.

        Args:
            process_id: ID of the process to terminate
            force: If True, use SIGKILL instead of SIGTERM

        Returns:
            True if process was terminated, False if not found
        """
        with self._lock:
            if process_id not in self.processes:
                return False

            process_info = self.processes[process_id]
            provider_name = process_info.provider_name

        logger.info(f"Terminating process {process_id} (force={force})")

        try:
            if process_info.process and process_info.is_alive:
                if force:
                    process_info.process.kill()
                else:
                    process_info.process.terminate()

                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(process_info.process.wait), timeout=5.0
                    )
                except TimeoutError:
                    logger.warning(f"Process {process_id} didn't exit gracefully, killing")
                    process_info.process.kill()
                    await asyncio.to_thread(process_info.process.wait)

            # Clean up
            with self._lock:
                if process_id in self.processes:
                    del self.processes[process_id]
                if process_id in self.provider_processes[provider_name]:
                    self.provider_processes[provider_name].remove(process_id)

            logger.info(f"Process {process_id} terminated successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to terminate process {process_id}: {e}")
            return False

    def get_process(self, process_id: str) -> ProcessInfo | None:
        """
        Get information about a managed process.

        Args:
            process_id: ID of the process

        Returns:
            ProcessInfo if found, None otherwise
        """
        with self._lock:
            process_info = self.processes.get(process_id)
            if process_info:
                process_info.update_access_time()
            return process_info

    def list_processes(
        self, provider_name: str | None = None, include_dead: bool = False
    ) -> list[ProcessInfo]:
        """
        List managed processes.

        Args:
            provider_name: Filter by provider name
            include_dead: Include terminated processes

        Returns:
            List of ProcessInfo objects
        """
        with self._lock:
            processes = []

            for process_info in self.processes.values():
                # Filter by provider if specified
                if provider_name and process_info.provider_name != provider_name:
                    continue

                # Filter dead processes if requested
                if not include_dead and not process_info.is_alive:
                    continue

                processes.append(process_info)

            return processes

    async def health_check(self, process_id: str | None = None) -> dict[str, Any]:
        """
        Perform health check on processes.

        Args:
            process_id: Check specific process, or all if None

        Returns:
            Health status information
        """
        with self._lock:
            if process_id:
                processes_to_check = [self.processes.get(process_id)]
                if not processes_to_check[0]:
                    return {"error": f"Process {process_id} not found"}
            else:
                processes_to_check = list(self.processes.values())

        health_data = {
            "total_processes": len(processes_to_check),
            "alive_processes": 0,
            "dead_processes": 0,
            "resource_usage": {},
            "processes": [],
        }

        for process_info in processes_to_check:
            if not process_info:
                continue

            is_alive = process_info.is_alive
            if is_alive:
                health_data["alive_processes"] += 1
                # Get resource usage
                try:
                    if process_info.process:
                        proc = psutil.Process(process_info.process.pid)
                        memory_mb = proc.memory_info().rss / 1024 / 1024
                        cpu_percent = proc.cpu_percent()

                        process_info.resource_usage = {
                            "memory_mb": memory_mb,
                            "cpu_percent": cpu_percent,
                            "num_fds": proc.num_fds() if hasattr(proc, "num_fds") else 0,
                        }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    is_alive = False

            if not is_alive:
                health_data["dead_processes"] += 1

            health_data["processes"].append(
                {
                    "id": process_info.id,
                    "provider": process_info.provider_name,
                    "alive": is_alive,
                    "idle_time": process_info.idle_time,
                    "session_mode": process_info.session_mode,
                    "resource_usage": process_info.resource_usage,
                }
            )

        return health_data

    async def shutdown(self, timeout: int = 30) -> None:
        """
        Shutdown all managed processes gracefully.

        Args:
            timeout: Maximum time to wait for graceful shutdown
        """
        logger.info("Starting CLI Process Manager shutdown")
        self._shutdown_event.set()

        # Stop monitoring
        await self.stop_monitoring()

        # Terminate all processes
        with self._lock:
            process_ids = list(self.processes.keys())

        # First try graceful termination
        tasks = []
        for process_id in process_ids:
            tasks.append(asyncio.create_task(self.terminate_process(process_id, force=False)))

        if tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
                )
            except TimeoutError:
                logger.warning("Graceful shutdown timed out, forcing termination")

                # Force kill remaining processes
                with self._lock:
                    remaining_ids = list(self.processes.keys())

                force_tasks = []
                for process_id in remaining_ids:
                    force_tasks.append(
                        asyncio.create_task(self.terminate_process(process_id, force=True))
                    )

                if force_tasks:
                    await asyncio.gather(*force_tasks, return_exceptions=True)

        logger.info("CLI Process Manager shutdown complete")

    # Private methods

    def _setup_resource_limits(self) -> None:
        """Set up resource limits for the process (POSIX only)."""
        try:
            # Memory limit
            memory_bytes = self.resource_limits.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

            # File descriptor limit
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (
                    self.resource_limits.max_file_descriptors,
                    self.resource_limits.max_file_descriptors,
                ),
            )

            # CPU time limit (wall clock time is handled separately)
            resource.setrlimit(resource.RLIMIT_CPU, (300, 300))  # 5 minutes

        except Exception as e:
            logger.warning(f"Failed to set resource limits: {e}")

    async def _stream_output(
        self, process: subprocess.Popen, queue: Queue, stream_name: str
    ) -> None:
        """Stream process output to async queue."""
        stream = getattr(process, stream_name)

        try:
            while process.poll() is None:
                line = await asyncio.to_thread(stream.readline)
                if line:
                    await queue.put(line.rstrip())
                else:
                    await asyncio.sleep(0.01)  # Prevent busy waiting
        except Exception as e:
            logger.error(f"Error streaming {stream_name}: {e}")
        finally:
            await queue.put(None)  # Signal end of stream

    async def _send_interactive_command(
        self, process_info: ProcessInfo, command: str, timeout: int
    ) -> tuple[str, str]:
        """Send command to interactive process."""
        if not process_info.process or not process_info.is_alive:
            raise ProcessPoolError("Interactive process is not running")

        # Send command
        process_info.process.stdin.write(command + "\n")
        process_info.process.stdin.flush()

        # Collect output with timeout
        stdout_lines = []
        stderr_lines = []
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Check for stdout
                stdout_line = await asyncio.wait_for(process_info.output_queue.get(), timeout=0.1)
                if stdout_line is None:
                    break
                stdout_lines.append(stdout_line)

                # Check for stderr
                try:
                    stderr_line = await asyncio.wait_for(
                        process_info.error_queue.get(), timeout=0.01
                    )
                    if stderr_line is not None:
                        stderr_lines.append(stderr_line)
                except TimeoutError:
                    pass

            except TimeoutError:
                # Check if we have a complete response
                if stdout_lines or stderr_lines:
                    break
                continue

        return "\n".join(stdout_lines), "\n".join(stderr_lines)

    async def _run_oneshot_command(
        self, process_info: ProcessInfo, command: str, timeout: int
    ) -> tuple[str, str]:
        """Run one-shot command with the configured binary and args."""
        cmd = [process_info.binary] + process_info.args + [command]

        # Set up resource limits
        preexec_fn = self._setup_resource_limits if os.name == "posix" else None

        process = subprocess.Popen(
            cmd,
            cwd=process_info.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=preexec_fn,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                asyncio.to_thread(process.communicate), timeout=timeout
            )

            if process.returncode != 0:
                raise ProcessPoolError(
                    f"Command failed with return code {process.returncode}: {stderr}"
                )

            return stdout, stderr

        except TimeoutError:
            process.kill()
            await asyncio.to_thread(process.wait)
            raise

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop for cleanup and health checks."""
        logger.info("Process monitoring loop started")

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Clean up idle processes
                await self._cleanup_idle_processes()

                # Check resource usage
                await self._check_resource_usage()

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

    async def _cleanup_idle_processes(self) -> None:
        """Clean up idle processes that exceed the timeout."""
        with self._lock:
            idle_processes = [
                pid
                for pid, pinfo in self.processes.items()
                if pinfo.idle_time > self.idle_timeout and not pinfo.session_mode
            ]

        if idle_processes:
            logger.info(f"Cleaning up {len(idle_processes)} idle processes")

            for process_id in idle_processes:
                await self.terminate_process(process_id)

    async def _check_resource_usage(self) -> None:
        """Monitor and enforce resource usage limits."""
        with self._lock:
            processes_to_check = list(self.processes.items())

        for process_id, process_info in processes_to_check:
            if not process_info.is_alive:
                continue

            try:
                proc = psutil.Process(process_info.process.pid)
                memory_mb = proc.memory_info().rss / 1024 / 1024
                cpu_percent = proc.cpu_percent()

                # Check memory limit
                if memory_mb > self.resource_limits.max_memory_mb:
                    logger.warning(
                        f"Process {process_id} exceeds memory limit: {memory_mb:.1f}MB > {self.resource_limits.max_memory_mb}MB"
                    )
                    await self.terminate_process(process_id, force=True)
                    continue

                # Check CPU limit (over time average)
                if cpu_percent > self.resource_limits.max_cpu_percent:
                    logger.warning(
                        f"Process {process_id} exceeds CPU limit: {cpu_percent:.1f}% > {self.resource_limits.max_cpu_percent}%"
                    )
                    # Don't kill immediately, but log for monitoring

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process already dead
                with self._lock:
                    if process_id in self.processes:
                        del self.processes[process_id]


# Singleton instance
_cli_manager: CLIProcessManager | None = None


def get_cli_manager() -> CLIProcessManager:
    """Get the singleton CLI Process Manager instance."""
    global _cli_manager
    if _cli_manager is None:
        _cli_manager = CLIProcessManager()
    return _cli_manager


async def initialize_cli_manager(**kwargs) -> CLIProcessManager:
    """Initialize and start the CLI Process Manager with custom options."""
    global _cli_manager
    if _cli_manager is not None:
        await _cli_manager.shutdown()

    _cli_manager = CLIProcessManager(**kwargs)
    await _cli_manager.start_monitoring()
    return _cli_manager


async def shutdown_cli_manager() -> None:
    """Shutdown the CLI Process Manager."""
    global _cli_manager
    if _cli_manager:
        await _cli_manager.shutdown()
        _cli_manager = None
