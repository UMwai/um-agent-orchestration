"""
Performance and Load Tests for CLI Integration

Tests concurrent session handling, WebSocket connection stress testing,
process spawning performance, and memory/resource usage validation.

Target performance metrics:
- 10+ concurrent sessions
- < 500ms session creation latency
- < 100ms message processing latency
- WebSocket connection stability under load
- Memory usage under acceptable limits
- Process cleanup efficiency
"""

import asyncio
import gc
import statistics
import time
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import psutil
import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketState

from orchestrator.app import app
from orchestrator.cli_session_manager import (
    CLISessionManager,
)
from orchestrator.cli_websocket import (
    CLIMessage,
    CLIWebSocketHandler,
    ConnectionState,
    MessageType,
    WebSocketConnection,
)


class PerformanceMetrics:
    """Helper class to collect and analyze performance metrics."""

    def __init__(self):
        self.timings: list[float] = []
        self.memory_usage: list[float] = []
        self.cpu_usage: list[float] = []
        self.error_count = 0
        self.success_count = 0
        self.start_time = None
        self.end_time = None

    def start_measurement(self):
        """Start performance measurement."""
        self.start_time = time.time()
        gc.collect()  # Force garbage collection before measurement

    def end_measurement(self):
        """End performance measurement."""
        self.end_time = time.time()

    def record_timing(self, duration: float):
        """Record timing measurement."""
        self.timings.append(duration)

    def record_memory(self):
        """Record current memory usage."""
        process = psutil.Process()
        self.memory_usage.append(process.memory_info().rss / 1024 / 1024)  # MB

    def record_cpu(self):
        """Record current CPU usage."""
        self.cpu_usage.append(psutil.cpu_percent())

    def record_success(self):
        """Record successful operation."""
        self.success_count += 1

    def record_error(self):
        """Record failed operation."""
        self.error_count += 1

    def get_summary(self) -> dict[str, Any]:
        """Get performance summary statistics."""
        total_time = (self.end_time - self.start_time) if self.start_time and self.end_time else 0

        timing_stats = {}
        if self.timings:
            timing_stats = {
                "min": min(self.timings) * 1000,  # ms
                "max": max(self.timings) * 1000,  # ms
                "mean": statistics.mean(self.timings) * 1000,  # ms
                "median": statistics.median(self.timings) * 1000,  # ms
                "p95": self._percentile(self.timings, 0.95) * 1000,  # ms
                "p99": self._percentile(self.timings, 0.99) * 1000,  # ms
            }

        memory_stats = {}
        if self.memory_usage:
            memory_stats = {
                "min_mb": min(self.memory_usage),
                "max_mb": max(self.memory_usage),
                "mean_mb": statistics.mean(self.memory_usage),
                "peak_mb": max(self.memory_usage) if self.memory_usage else 0,
            }

        cpu_stats = {}
        if self.cpu_usage:
            cpu_stats = {
                "min_percent": min(self.cpu_usage),
                "max_percent": max(self.cpu_usage),
                "mean_percent": statistics.mean(self.cpu_usage),
            }

        return {
            "total_time_seconds": total_time,
            "total_operations": self.success_count + self.error_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_count / max(1, self.success_count + self.error_count),
            "operations_per_second": (self.success_count + self.error_count)
            / max(0.001, total_time),
            "timing_stats_ms": timing_stats,
            "memory_stats": memory_stats,
            "cpu_stats": cpu_stats,
        }

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(percentile * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


@pytest.fixture
def performance_metrics():
    """Create performance metrics collector."""
    return PerformanceMetrics()


@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def session_manager():
    """Create fresh session manager."""
    return CLISessionManager()


@pytest.fixture
def websocket_handler():
    """Create fresh WebSocket handler."""
    return CLIWebSocketHandler()


class TestConcurrentSessionHandling:
    """Test concurrent CLI session management performance."""

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_session_creation(self, performance_metrics, session_manager):
        """Test creating multiple concurrent CLI sessions."""

        # Mock persistence to avoid Redis dependency in performance tests
        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager
            session_manager.persistence = mock_persistent_manager

            # Mock session creation
            def create_session_mock(*args, **kwargs):
                mock_session = MagicMock()
                mock_session.id = f"perf-session-{int(time.time() * 1000000) % 1000000}"
                return mock_session

            mock_persistent_manager.create_session = create_session_mock

            performance_metrics.start_measurement()

            # Target: Create 10 concurrent sessions
            num_sessions = 10
            tasks = []

            for i in range(num_sessions):
                task = asyncio.create_task(
                    self._create_session_with_timing(
                        session_manager, "claude", "interactive", performance_metrics
                    )
                )
                tasks.append(task)

            # Wait for all sessions to be created
            results = await asyncio.gather(*tasks, return_exceptions=True)

            performance_metrics.end_measurement()

            # Analyze results
            successful_sessions = [r for r in results if isinstance(r, str)]
            failed_sessions = [r for r in results if isinstance(r, Exception)]

            summary = performance_metrics.get_summary()

            # Performance assertions
            assert (
                len(successful_sessions) >= 8
            ), f"Expected at least 8 successful sessions, got {len(successful_sessions)}"
            assert len(failed_sessions) <= 2, f"Too many failed sessions: {len(failed_sessions)}"

            # Latency requirements
            if summary["timing_stats_ms"]:
                assert (
                    summary["timing_stats_ms"]["mean"] < 500
                ), f"Mean session creation time too high: {summary['timing_stats_ms']['mean']}ms"
                assert (
                    summary["timing_stats_ms"]["p95"] < 1000
                ), f"P95 session creation time too high: {summary['timing_stats_ms']['p95']}ms"

            print("Session Creation Performance Summary:")
            print(f"  Total sessions: {num_sessions}")
            print(f"  Successful: {len(successful_sessions)}")
            print(f"  Failed: {len(failed_sessions)}")
            print(f"  Mean latency: {summary['timing_stats_ms'].get('mean', 0):.2f}ms")
            print(f"  P95 latency: {summary['timing_stats_ms'].get('p95', 0):.2f}ms")

    async def _create_session_with_timing(self, session_manager, cli_tool, mode, metrics):
        """Create a session and record timing."""
        start_time = time.time()
        try:
            session_id = await session_manager.create_session(cli_tool, mode)
            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_success()
            return session_id
        except Exception as e:
            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_error()
            raise e

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_session_operations(self, performance_metrics, session_manager):
        """Test concurrent operations on multiple sessions."""

        # Set up mock persistence
        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager
            session_manager.persistence = mock_persistent_manager

            # Create mock sessions
            session_ids = []
            for i in range(5):
                mock_session = MagicMock()
                session_id = f"concurrent-session-{i}"
                mock_session.id = session_id
                mock_persistent_manager.create_session.return_value = mock_session

                session_id = await session_manager.create_session("claude", "cli")
                session_ids.append(session_id)

            performance_metrics.start_measurement()

            # Run concurrent operations
            operations = []
            for session_id in session_ids:
                # Multiple operations per session
                operations.extend(
                    [
                        self._perform_session_operation(
                            session_manager, session_id, "info", performance_metrics
                        ),
                        self._perform_session_operation(
                            session_manager, session_id, "input", performance_metrics
                        ),
                        self._perform_session_operation(
                            session_manager, session_id, "info", performance_metrics
                        ),
                    ]
                )

            results = await asyncio.gather(*operations, return_exceptions=True)

            performance_metrics.end_measurement()

            # Analyze results
            successful_ops = [r for r in results if not isinstance(r, Exception)]
            failed_ops = [r for r in results if isinstance(r, Exception)]

            summary = performance_metrics.get_summary()

            # Performance assertions
            assert len(successful_ops) >= len(operations) * 0.8, "Too many failed operations"

            if summary["timing_stats_ms"]:
                assert (
                    summary["timing_stats_ms"]["mean"] < 100
                ), f"Mean operation time too high: {summary['timing_stats_ms']['mean']}ms"

            print("Concurrent Operations Performance:")
            print(f"  Total operations: {len(operations)}")
            print(f"  Successful: {len(successful_ops)}")
            print(f"  Failed: {len(failed_ops)}")
            print(f"  Mean latency: {summary['timing_stats_ms'].get('mean', 0):.2f}ms")

    async def _perform_session_operation(self, session_manager, session_id, operation, metrics):
        """Perform a session operation and record timing."""
        start_time = time.time()
        try:
            if operation == "info":
                result = session_manager.get_session_info(session_id)
            elif operation == "input":
                # Mock the send_input_to_session to avoid actual CLI processes
                with patch.object(session_manager, "sessions", {session_id: MagicMock()}):
                    with patch.object(
                        session_manager.sessions[session_id], "send_input"
                    ) as mock_send:
                        mock_send.return_value = None
                        result = await session_manager.send_input_to_session(
                            session_id, "test command"
                        )

            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_success()
            return result
        except Exception as e:
            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_error()
            raise e


class TestWebSocketConnectionStress:
    """Test WebSocket connection handling under stress."""

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_multiple_websocket_connections(self, performance_metrics, websocket_handler):
        """Test handling multiple WebSocket connections simultaneously."""

        performance_metrics.start_measurement()

        # Create multiple mock WebSocket connections
        num_connections = 15
        connections = []

        for i in range(num_connections):
            start_time = time.time()

            mock_websocket = AsyncMock()
            mock_websocket.client_state = WebSocketState.CONNECTED

            connection = WebSocketConnection(
                websocket=mock_websocket,
                session_id=f"stress-session-{i}",
                user_id=f"stress-user-{i}",
                connection_id=f"stress-conn-{i}",
                connected_at=time.time(),
                last_activity=time.time(),
                state=ConnectionState.CONNECTED,
                authenticated=True,
            )

            # Register connection
            websocket_handler.active_connections[connection.connection_id] = connection
            if connection.session_id not in websocket_handler.session_connections:
                websocket_handler.session_connections[connection.session_id] = set()
            websocket_handler.session_connections[connection.session_id].add(
                connection.connection_id
            )

            connections.append(connection)

            duration = time.time() - start_time
            performance_metrics.record_timing(duration)
            performance_metrics.record_success()

        # Test broadcasting to all connections
        broadcast_start = time.time()

        test_message = CLIMessage(
            type=MessageType.OUTPUT,
            session_id="broadcast-test",
            data={"output": "Stress test broadcast"},
            timestamp=datetime.utcnow().isoformat(),
        )

        # Add all connections to same session for broadcast test
        websocket_handler.session_connections["broadcast-test"] = {
            conn.connection_id for conn in connections
        }

        await websocket_handler.broadcast_to_session("broadcast-test", test_message)

        broadcast_duration = time.time() - broadcast_start
        performance_metrics.record_timing(broadcast_duration)

        performance_metrics.end_measurement()

        # Verify all connections received the message
        for connection in connections:
            connection.websocket.send_text.assert_called()

        summary = performance_metrics.get_summary()

        # Performance assertions
        assert websocket_handler.get_handler_metrics()["active_connections"] == num_connections

        if summary["timing_stats_ms"]:
            assert (
                summary["timing_stats_ms"]["mean"] < 50
            ), f"Mean connection setup time too high: {summary['timing_stats_ms']['mean']}ms"

        print("WebSocket Stress Test Results:")
        print(f"  Connections created: {num_connections}")
        print(f"  Mean setup time: {summary['timing_stats_ms'].get('mean', 0):.2f}ms")
        print(f"  Broadcast time: {broadcast_duration * 1000:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_websocket_message_throughput(self, performance_metrics, websocket_handler):
        """Test WebSocket message processing throughput."""

        # Set up test connection
        mock_websocket = AsyncMock()
        mock_websocket.client_state = WebSocketState.CONNECTED

        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id="throughput-test",
            user_id="throughput-user",
            connection_id="throughput-conn",
            connected_at=time.time(),
            last_activity=time.time(),
            state=ConnectionState.CONNECTED,
            authenticated=True,
        )

        websocket_handler.active_connections[connection.connection_id] = connection
        websocket_handler.session_connections[connection.session_id] = {connection.connection_id}

        performance_metrics.start_measurement()

        # Send many messages rapidly
        num_messages = 100
        message_tasks = []

        for i in range(num_messages):
            test_message = CLIMessage(
                type=MessageType.OUTPUT,
                session_id=connection.session_id,
                data={"output": f"Throughput test message {i}"},
                timestamp=datetime.utcnow().isoformat(),
            )

            task = asyncio.create_task(
                self._send_message_with_timing(
                    websocket_handler, connection, test_message, performance_metrics
                )
            )
            message_tasks.append(task)

        # Wait for all messages to be processed
        await asyncio.gather(*message_tasks)

        performance_metrics.end_measurement()

        summary = performance_metrics.get_summary()

        # Performance assertions
        assert (
            summary["success_count"] == num_messages
        ), f"Not all messages processed successfully: {summary['success_count']}/{num_messages}"
        assert (
            summary["operations_per_second"] > 200
        ), f"Message throughput too low: {summary['operations_per_second']:.2f} ops/sec"

        if summary["timing_stats_ms"]:
            assert (
                summary["timing_stats_ms"]["mean"] < 10
            ), f"Mean message processing time too high: {summary['timing_stats_ms']['mean']}ms"

        print("Message Throughput Test Results:")
        print(f"  Messages processed: {summary['success_count']}")
        print(f"  Throughput: {summary['operations_per_second']:.2f} messages/sec")
        print(f"  Mean processing time: {summary['timing_stats_ms'].get('mean', 0):.2f}ms")

    async def _send_message_with_timing(self, handler, connection, message, metrics):
        """Send message and record timing."""
        start_time = time.time()
        try:
            await handler._send_message_to_connection(connection, message)
            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_success()
        except Exception as e:
            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_error()
            raise e


class TestResourceUsageValidation:
    """Test memory and resource usage under load."""

    @pytest.mark.performance
    def test_memory_usage_during_session_creation(self, performance_metrics):
        """Test memory usage during intensive session creation."""

        # Record baseline memory
        performance_metrics.record_memory()
        baseline_memory = performance_metrics.memory_usage[0]

        session_manager = CLISessionManager()

        # Mock persistence to avoid external dependencies
        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager
            session_manager.persistence = mock_persistent_manager

            # Create many sessions to test memory usage
            num_sessions = 50
            session_ids = []

            performance_metrics.start_measurement()

            for i in range(num_sessions):
                mock_session = MagicMock()
                mock_session.id = f"memory-test-session-{i}"
                mock_persistent_manager.create_session.return_value = mock_session

                # Create session (synchronous version for memory testing)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    session_id = loop.run_until_complete(
                        session_manager.create_session("claude", "cli")
                    )
                    session_ids.append(session_id)
                finally:
                    loop.close()

                # Record memory usage every 10 sessions
                if i % 10 == 0:
                    performance_metrics.record_memory()
                    performance_metrics.record_cpu()

            performance_metrics.record_memory()
            performance_metrics.end_measurement()

            # Cleanup sessions
            for session_id in session_ids:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(session_manager.terminate_session(session_id))
                finally:
                    loop.close()

            # Force garbage collection and record final memory
            gc.collect()
            performance_metrics.record_memory()

            summary = performance_metrics.get_summary()

            # Memory usage assertions
            peak_memory = summary["memory_stats"]["peak_mb"]
            final_memory = performance_metrics.memory_usage[-1]
            memory_growth = peak_memory - baseline_memory
            memory_retained = final_memory - baseline_memory

            # Should not use more than 200MB additional memory for 50 sessions
            assert memory_growth < 200, f"Memory usage too high: {memory_growth:.2f}MB additional"

            # Memory should be mostly cleaned up after session termination
            assert (
                memory_retained < 50
            ), f"Memory not properly cleaned up: {memory_retained:.2f}MB retained"

            print("Memory Usage Test Results:")
            print(f"  Baseline memory: {baseline_memory:.2f}MB")
            print(f"  Peak memory: {peak_memory:.2f}MB")
            print(f"  Final memory: {final_memory:.2f}MB")
            print(f"  Memory growth: {memory_growth:.2f}MB")
            print(f"  Memory retained: {memory_retained:.2f}MB")

    @pytest.mark.performance
    def test_websocket_handler_memory_efficiency(self, performance_metrics):
        """Test WebSocket handler memory efficiency."""

        performance_metrics.record_memory()
        baseline_memory = performance_metrics.memory_usage[0]

        websocket_handler = CLIWebSocketHandler()

        performance_metrics.start_measurement()

        # Create many WebSocket connections
        num_connections = 100
        connections = []

        for i in range(num_connections):
            mock_websocket = AsyncMock()
            mock_websocket.client_state = WebSocketState.CONNECTED

            connection = WebSocketConnection(
                websocket=mock_websocket,
                session_id=f"memory-session-{i % 10}",  # 10 unique sessions
                user_id=f"memory-user-{i}",
                connection_id=f"memory-conn-{i}",
                connected_at=time.time(),
                last_activity=time.time(),
                state=ConnectionState.CONNECTED,
                authenticated=True,
            )

            websocket_handler.active_connections[connection.connection_id] = connection

            session_id = connection.session_id
            if session_id not in websocket_handler.session_connections:
                websocket_handler.session_connections[session_id] = set()
            websocket_handler.session_connections[session_id].add(connection.connection_id)

            connections.append(connection)

            # Record memory every 20 connections
            if i % 20 == 0:
                performance_metrics.record_memory()

        performance_metrics.record_memory()

        # Cleanup connections
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for connection in connections:
                loop.run_until_complete(
                    websocket_handler._cleanup_connection(connection.connection_id)
                )
        finally:
            loop.close()

        # Force garbage collection and record final memory
        gc.collect()
        performance_metrics.record_memory()
        performance_metrics.end_measurement()

        summary = performance_metrics.get_summary()

        # Memory assertions
        peak_memory = summary["memory_stats"]["peak_mb"]
        final_memory = performance_metrics.memory_usage[-1]
        memory_growth = peak_memory - baseline_memory
        memory_retained = final_memory - baseline_memory

        # Should not use more than 100MB for 100 WebSocket connections
        assert memory_growth < 100, f"WebSocket memory usage too high: {memory_growth:.2f}MB"

        # Memory should be cleaned up after connection cleanup
        assert (
            memory_retained < 20
        ), f"WebSocket memory not cleaned up: {memory_retained:.2f}MB retained"

        print("WebSocket Memory Test Results:")
        print(f"  Baseline memory: {baseline_memory:.2f}MB")
        print(f"  Peak memory: {peak_memory:.2f}MB")
        print(f"  Final memory: {final_memory:.2f}MB")
        print(f"  Memory growth: {memory_growth:.2f}MB")
        print(f"  Memory retained: {memory_retained:.2f}MB")


class TestProcessCleanupEfficiency:
    """Test process cleanup and resource deallocation."""

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_session_cleanup_performance(self, performance_metrics, session_manager):
        """Test efficiency of session cleanup operations."""

        # Set up mock persistence
        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager
            session_manager.persistence = mock_persistent_manager

            # Create sessions to cleanup
            num_sessions = 20
            session_ids = []

            for i in range(num_sessions):
                mock_session = MagicMock()
                mock_session.id = f"cleanup-session-{i}"
                mock_persistent_manager.create_session.return_value = mock_session

                session_id = await session_manager.create_session("claude", "cli")

                # Mock CLI process for each session
                mock_process = MagicMock()
                session_manager.sessions[session_id] = mock_process

                session_ids.append(session_id)

            performance_metrics.start_measurement()

            # Cleanup all sessions concurrently
            cleanup_tasks = []
            for session_id in session_ids:
                task = asyncio.create_task(
                    self._cleanup_session_with_timing(
                        session_manager, session_id, performance_metrics
                    )
                )
                cleanup_tasks.append(task)

            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)

            performance_metrics.end_measurement()

            # Analyze cleanup results
            successful_cleanups = [r for r in results if r is True]
            failed_cleanups = [r for r in results if isinstance(r, Exception)]

            summary = performance_metrics.get_summary()

            # Performance assertions
            assert (
                len(successful_cleanups) >= num_sessions * 0.9
            ), f"Too many cleanup failures: {len(failed_cleanups)}"

            if summary["timing_stats_ms"]:
                assert (
                    summary["timing_stats_ms"]["mean"] < 200
                ), f"Mean cleanup time too high: {summary['timing_stats_ms']['mean']}ms"

            # Verify all sessions were cleaned up
            assert len(session_manager.sessions) == 0, "Not all sessions were cleaned up"
            assert len(session_manager.session_info) == 0, "Not all session info was cleaned up"

            print("Session Cleanup Performance:")
            print(f"  Sessions cleaned: {len(successful_cleanups)}")
            print(f"  Failed cleanups: {len(failed_cleanups)}")
            print(f"  Mean cleanup time: {summary['timing_stats_ms'].get('mean', 0):.2f}ms")
            print(f"  Cleanup rate: {summary['operations_per_second']:.2f} sessions/sec")

    async def _cleanup_session_with_timing(self, session_manager, session_id, metrics):
        """Cleanup session and record timing."""
        start_time = time.time()
        try:
            result = await session_manager.terminate_session(session_id, "Performance test cleanup")
            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_success()
            return result
        except Exception as e:
            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_error()
            raise e

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_websocket_cleanup_performance(self, performance_metrics, websocket_handler):
        """Test WebSocket connection cleanup efficiency."""

        # Create connections to cleanup
        num_connections = 30
        connection_ids = []

        for i in range(num_connections):
            mock_websocket = AsyncMock()
            mock_websocket.client_state = WebSocketState.CONNECTED

            connection = WebSocketConnection(
                websocket=mock_websocket,
                session_id=f"cleanup-ws-session-{i}",
                user_id=f"cleanup-user-{i}",
                connection_id=f"cleanup-conn-{i}",
                connected_at=time.time(),
                last_activity=time.time(),
                state=ConnectionState.CONNECTED,
                authenticated=True,
            )

            # Mock heartbeat task
            connection.heartbeat_task = AsyncMock()

            websocket_handler.active_connections[connection.connection_id] = connection
            websocket_handler.session_connections[connection.session_id] = {
                connection.connection_id
            }

            connection_ids.append(connection.connection_id)

        performance_metrics.start_measurement()

        # Cleanup all connections concurrently
        cleanup_tasks = []
        for conn_id in connection_ids:
            task = asyncio.create_task(
                self._cleanup_connection_with_timing(
                    websocket_handler, conn_id, performance_metrics
                )
            )
            cleanup_tasks.append(task)

        await asyncio.gather(*cleanup_tasks)

        performance_metrics.end_measurement()

        summary = performance_metrics.get_summary()

        # Verify cleanup efficiency
        assert len(websocket_handler.active_connections) == 0, "Not all connections cleaned up"
        assert (
            len(websocket_handler.session_connections) == 0
        ), "Not all session mappings cleaned up"

        if summary["timing_stats_ms"]:
            assert (
                summary["timing_stats_ms"]["mean"] < 100
            ), f"Mean connection cleanup time too high: {summary['timing_stats_ms']['mean']}ms"

        print("WebSocket Cleanup Performance:")
        print(f"  Connections cleaned: {summary['success_count']}")
        print(f"  Mean cleanup time: {summary['timing_stats_ms'].get('mean', 0):.2f}ms")
        print(f"  Cleanup rate: {summary['operations_per_second']:.2f} connections/sec")

    async def _cleanup_connection_with_timing(self, handler, connection_id, metrics):
        """Cleanup WebSocket connection and record timing."""
        start_time = time.time()
        try:
            await handler._cleanup_connection(connection_id)
            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_success()
        except Exception as e:
            duration = time.time() - start_time
            metrics.record_timing(duration)
            metrics.record_error()
            raise e


class TestEndToEndPerformance:
    """End-to-end performance testing scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_complete_workflow_performance(self, performance_metrics):
        """Test complete workflow performance under load."""

        performance_metrics.start_measurement()

        # Initialize managers
        session_manager = CLISessionManager()
        websocket_handler = CLIWebSocketHandler()

        # Mock external dependencies
        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager
            session_manager.persistence = mock_persistent_manager

            # Simulate complete workflow for multiple concurrent users
            num_users = 5
            workflow_tasks = []

            for user_id in range(num_users):
                task = asyncio.create_task(
                    self._simulate_user_workflow(
                        session_manager, websocket_handler, f"user_{user_id}", performance_metrics
                    )
                )
                workflow_tasks.append(task)

            # Wait for all workflows to complete
            results = await asyncio.gather(*workflow_tasks, return_exceptions=True)

            performance_metrics.end_measurement()

            # Analyze results
            successful_workflows = [r for r in results if not isinstance(r, Exception)]
            failed_workflows = [r for r in results if isinstance(r, Exception)]

            summary = performance_metrics.get_summary()

            # Performance assertions
            assert (
                len(successful_workflows) >= num_users * 0.8
            ), f"Too many failed workflows: {len(failed_workflows)}"
            assert (
                summary["operations_per_second"] > 10
            ), f"Workflow throughput too low: {summary['operations_per_second']:.2f}"

            print("End-to-End Performance Results:")
            print(f"  Concurrent users: {num_users}")
            print(f"  Successful workflows: {len(successful_workflows)}")
            print(f"  Failed workflows: {len(failed_workflows)}")
            print(f"  Overall throughput: {summary['operations_per_second']:.2f} operations/sec")
            print(f"  Mean operation time: {summary['timing_stats_ms'].get('mean', 0):.2f}ms")

    async def _simulate_user_workflow(self, session_manager, websocket_handler, user_id, metrics):
        """Simulate complete user workflow."""

        # Mock session creation
        mock_session = MagicMock()
        mock_session.id = f"workflow-{user_id}-session"
        session_manager.persistence.create_session.return_value = mock_session

        operations = []

        # 1. Create session
        operations.append(
            ("create_session", session_manager.create_session("claude", "interactive"))
        )

        # 2. Create WebSocket connection
        mock_websocket = AsyncMock()
        mock_websocket.client_state = WebSocketState.CONNECTED

        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id=mock_session.id,
            user_id=user_id,
            connection_id=f"workflow-{user_id}-conn",
            connected_at=time.time(),
            last_activity=time.time(),
            state=ConnectionState.CONNECTED,
            authenticated=True,
        )

        websocket_handler.active_connections[connection.connection_id] = connection
        websocket_handler.session_connections[connection.session_id] = {connection.connection_id}

        # 3. Send multiple messages
        for i in range(3):
            message = CLIMessage(
                type=MessageType.OUTPUT,
                session_id=connection.session_id,
                data={"output": f"Workflow message {i}"},
                timestamp=datetime.utcnow().isoformat(),
            )
            operations.append(
                ("send_message", websocket_handler._send_message_to_connection(connection, message))
            )

        # 4. Cleanup
        operations.append(
            ("cleanup_connection", websocket_handler._cleanup_connection(connection.connection_id))
        )
        operations.append(
            (
                "cleanup_session",
                session_manager.terminate_session(mock_session.id, "Workflow cleanup"),
            )
        )

        # Execute all operations and record timings
        for operation_name, operation_coroutine in operations:
            start_time = time.time()
            try:
                if asyncio.iscoroutine(operation_coroutine):
                    await operation_coroutine
                else:
                    # Handle non-coroutine operations
                    pass
                duration = time.time() - start_time
                metrics.record_timing(duration)
                metrics.record_success()
            except Exception as e:
                duration = time.time() - start_time
                metrics.record_timing(duration)
                metrics.record_error()
                raise e

        return f"Workflow completed for {user_id}"


# Custom pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "performance: mark test as performance test")


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-m", "performance", "--tb=short"])
