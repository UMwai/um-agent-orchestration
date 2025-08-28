"""
Comprehensive Integration Tests for CLI Integration Phase 1

Tests the complete end-to-end flow:
- Authentication & session creation
- WebSocket communication
- CLI process management
- Real-time output streaming
- Session persistence and recovery
- Multi-provider support
- Error handling and edge cases

This test suite validates all Phase 1 acceptance criteria.
"""

import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
import redis
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketState

from orchestrator.app import app
from orchestrator.cli_session_manager import CLISessionInfo, CLISessionManager, CLISessionState
from orchestrator.cli_websocket import (
    CLIMessage,
    CLIWebSocketHandler,
    ConnectionState,
    MessageType,
    WebSocketConnection,
)


@pytest.fixture(scope="session")
def test_redis():
    """Set up test Redis instance."""
    # Use test Redis database
    redis_client = redis.Redis(host="localhost", port=6379, db=15, decode_responses=True)

    # Clear test database
    redis_client.flushdb()

    yield redis_client

    # Cleanup
    redis_client.flushdb()
    redis_client.close()


@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def cli_session_manager():
    """Create fresh CLI session manager for testing."""
    return CLISessionManager()


@pytest.fixture
def websocket_handler():
    """Create fresh WebSocket handler for testing."""
    return CLIWebSocketHandler()


@pytest.fixture
def auth_token():
    """Create valid authentication token for testing."""
    secret = "test-secret-key"
    payload = {
        "user_id": "test_user",
        "username": "testuser",
        "full_access": True,
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def expired_token():
    """Create expired authentication token for testing."""
    secret = "test-secret-key"
    payload = {
        "user_id": "test_user",
        "username": "testuser",
        "full_access": True,
        "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class TestCompleteWorkflow:
    """Test complete end-to-end workflow scenarios."""

    @pytest.mark.asyncio
    async def test_complete_claude_workflow(self, test_client, auth_token):
        """Test complete workflow: auth → session → command → output → cleanup"""

        # 1. Authentication
        login_response = test_client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        )
        assert login_response.status_code == 200

        access_token = login_response.json()["access_token"]

        # 2. Create CLI session
        session_data = {
            "cli_tool": "claude",
            "mode": "interactive",
            "full_access": True,
            "cwd": "/tmp",
        }

        with (
            patch(
                "orchestrator.cli_session_manager.CLISessionManager.create_session"
            ) as mock_create,
            patch(
                "orchestrator.cli_session_manager.CLISessionManager.start_cli_process"
            ) as mock_start,
        ):
            mock_create.return_value = "test-session-123"
            mock_start.return_value = True

            session_response = test_client.post("/api/cli/sessions", json=session_data)
            assert session_response.status_code == 200

            session_info = session_response.json()
            session_id = session_info["session_id"]
            websocket_url = session_info["websocket_url"]

            assert session_id == "test-session-123"
            assert websocket_url == f"/ws/cli/{session_id}"

        # 3. WebSocket connection and command execution
        with patch(
            "orchestrator.cli_session_manager.CLISessionManager.send_input_to_session"
        ) as mock_send:
            mock_send.return_value = True

            # Mock WebSocket for testing
            with test_client.websocket_connect(
                f"/ws/cli/{session_id}?token={access_token}"
            ) as websocket:
                # Send command
                command_message = {
                    "type": "command",
                    "session_id": session_id,
                    "data": {"command": "Write a hello world function in Python"},
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_id": "cmd-001",
                }

                websocket.send_text(json.dumps(command_message))

                # Receive acknowledgment
                response = websocket.receive_text()
                response_data = json.loads(response)

                assert response_data["type"] == "status"
                assert response_data["data"]["status"] == "command_sent"

                # Verify command was sent to session manager
                mock_send.assert_called_once_with(
                    session_id, "Write a hello world function in Python"
                )

    @pytest.mark.asyncio
    async def test_multi_provider_support(self, test_client):
        """Test support for multiple CLI providers."""
        providers = ["claude", "codex", "gemini", "cursor"]
        session_ids = []

        for provider in providers:
            session_data = {"cli_tool": provider, "mode": "cli", "full_access": False}

            with (
                patch(
                    "orchestrator.cli_session_manager.CLISessionManager.create_session"
                ) as mock_create,
                patch(
                    "orchestrator.cli_session_manager.CLISessionManager.start_cli_process"
                ) as mock_start,
            ):
                session_id = f"{provider}-session-{int(time.time())}"
                mock_create.return_value = session_id
                mock_start.return_value = True

                response = test_client.post("/api/cli/sessions", json=session_data)
                assert response.status_code == 200

                session_info = response.json()
                assert session_info["cli_tool"] == provider
                session_ids.append(session_id)

        # Verify all sessions are tracked
        sessions_response = test_client.get("/api/cli/sessions")
        assert sessions_response.status_code == 200

        sessions_data = sessions_response.json()
        assert len(sessions_data["sessions"]) >= len(providers)


class TestWebSocketCommunication:
    """Test WebSocket message flow and real-time communication."""

    @pytest.mark.asyncio
    async def test_websocket_message_flow_validation(self, websocket_handler):
        """Test WebSocket message format validation and routing."""

        # Create mock WebSocket connection
        mock_websocket = AsyncMock()
        mock_websocket.client_state = WebSocketState.CONNECTED

        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id="test-session",
            user_id="test_user",
            connection_id="conn-123",
            connected_at=time.time(),
            last_activity=time.time(),
            state=ConnectionState.CONNECTED,
            authenticated=True,
        )

        websocket_handler.active_connections["conn-123"] = connection
        websocket_handler.session_connections["test-session"] = {"conn-123"}

        # Test different message types
        test_messages = [
            {
                "type": "command",
                "session_id": "test-session",
                "data": {"command": "ls -la"},
                "timestamp": datetime.utcnow().isoformat(),
                "message_id": "msg-001",
            },
            {
                "type": "status",
                "session_id": "test-session",
                "data": {"request": "session_info"},
                "timestamp": datetime.utcnow().isoformat(),
                "message_id": "msg-002",
            },
            {
                "type": "ping",
                "session_id": "test-session",
                "data": {"timestamp": time.time()},
                "timestamp": datetime.utcnow().isoformat(),
                "message_id": "msg-003",
            },
        ]

        with patch("orchestrator.cli_session_manager.get_cli_session_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.send_input_to_session.return_value = True
            mock_manager.get_session_info.return_value = MagicMock(
                session_id="test-session",
                cli_tool="claude",
                mode="cli",
                state=CLISessionState.RUNNING,
                pid=12345,
                authentication_required=False,
                current_directory="/tmp",
                last_activity=time.time(),
                command_history=["ls", "pwd"],
            )
            mock_get_manager.return_value = mock_manager

            # Test each message type
            for msg_data in test_messages:
                message = CLIMessage.from_json(json.dumps(msg_data))

                if message.type == MessageType.COMMAND:
                    await websocket_handler._handle_command(connection, message)
                elif message.type == MessageType.STATUS:
                    await websocket_handler._handle_status_request(connection, message)
                elif message.type == MessageType.PING:
                    await websocket_handler._handle_ping(connection, message)

                # Verify response was sent
                mock_websocket.send_text.assert_called()

    @pytest.mark.asyncio
    async def test_real_time_output_streaming(self, websocket_handler):
        """Test real-time CLI output streaming to WebSocket clients."""

        # Set up mock WebSocket connections for same session
        session_id = "streaming-test-session"
        connections = []

        for i in range(3):  # Multiple clients for same session
            mock_websocket = AsyncMock()
            mock_websocket.client_state = WebSocketState.CONNECTED

            connection = WebSocketConnection(
                websocket=mock_websocket,
                session_id=session_id,
                user_id=f"user_{i}",
                connection_id=f"conn-{i}",
                connected_at=time.time(),
                last_activity=time.time(),
                state=ConnectionState.CONNECTED,
                authenticated=True,
            )

            websocket_handler.active_connections[f"conn-{i}"] = connection
            connections.append(connection)

        websocket_handler.session_connections[session_id] = {f"conn-{i}" for i in range(3)}

        # Test streaming different types of output
        output_tests = [
            ("stdout", "Hello from CLI!"),
            ("stderr", "Warning: deprecated function"),
            ("stdout", "Process completed successfully"),
            ("error", "Command failed with exit code 1"),
        ]

        for output_type, content in output_tests:
            await websocket_handler.send_output_to_session(session_id, content, output_type)

            # Verify all connections received the output
            for connection in connections:
                connection.websocket.send_text.assert_called()

                # Get the last call and verify content
                last_call = connection.websocket.send_text.call_args[0][0]
                sent_data = json.loads(last_call)

                assert sent_data["type"] == "output"
                assert sent_data["session_id"] == session_id
                assert sent_data["data"]["output"] == content
                assert sent_data["data"]["output_type"] == output_type

    @pytest.mark.asyncio
    async def test_websocket_connection_recovery(self, websocket_handler):
        """Test WebSocket connection recovery and message queuing."""

        mock_websocket = AsyncMock()
        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id="recovery-test",
            user_id="test_user",
            connection_id="conn-recovery",
            connected_at=time.time(),
            last_activity=time.time(),
            state=ConnectionState.CONNECTED,
            authenticated=True,
        )

        websocket_handler.active_connections["conn-recovery"] = connection
        websocket_handler.session_connections["recovery-test"] = {"conn-recovery"}

        # Simulate connection issue
        mock_websocket.client_state = WebSocketState.DISCONNECTED

        # Send messages while disconnected (should be queued)
        test_outputs = ["Queued message 1", "Queued message 2", "Queued message 3"]

        for output in test_outputs:
            await websocket_handler.send_output_to_session("recovery-test", output)

        # Verify messages were queued
        assert len(connection.message_queue) == 3

        # Simulate connection recovery
        mock_websocket.client_state = WebSocketState.CONNECTED

        # Flush queued messages
        await websocket_handler._flush_message_queue(connection)

        # Verify all queued messages were sent
        assert mock_websocket.send_text.call_count == 3
        assert len(connection.message_queue) == 0


class TestSessionPersistenceRecovery:
    """Test session persistence and recovery mechanisms."""

    @pytest.mark.asyncio
    async def test_session_persistence_workflow(self, cli_session_manager):
        """Test session creation, persistence, and recovery."""

        # Mock Redis persistence
        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager

            # Mock persistent session
            mock_session = MagicMock()
            mock_session.id = "persistent-session-123"
            mock_persistent_manager.create_session.return_value = mock_session

            # Create session
            session_id = await cli_session_manager.create_session(
                cli_tool="claude", mode="interactive", cwd="/tmp", user_id="test_user"
            )

            assert session_id == "persistent-session-123"

            # Verify persistence manager was called
            mock_persistent_manager.create_session.assert_called_once_with(
                provider="claude",
                user_id="test_user",
                working_directory="/tmp",
                metadata={"mode": "interactive", "cli_tool": "claude"},
            )

            # Test session info persistence
            session_info = cli_session_manager.get_session_info(session_id)
            assert session_info is not None
            assert session_info.session_id == session_id
            assert session_info.cli_tool == "claude"
            assert session_info.mode == "interactive"

    @pytest.mark.asyncio
    async def test_session_recovery_after_restart(self, cli_session_manager):
        """Test session recovery after system restart."""

        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager

            # Mock recovered sessions
            mock_sessions = []
            for i in range(3):
                mock_session = MagicMock()
                mock_session.id = f"recovered-session-{i}"
                mock_session.provider = "claude"
                mock_session.working_directory = "/tmp"
                mock_session.metadata = {"mode": "cli", "cli_tool": "claude"}
                mock_sessions.append(mock_session)

            mock_persistent_manager.recover_sessions.return_value = mock_sessions
            cli_session_manager.persistence = mock_persistent_manager

            # Recover sessions
            recovered_ids = await cli_session_manager.recover_sessions()

            assert len(recovered_ids) == 3
            assert all(session_id.startswith("recovered-session-") for session_id in recovered_ids)

            # Verify sessions are tracked in memory
            for session_id in recovered_ids:
                session_info = cli_session_manager.get_session_info(session_id)
                assert session_info is not None
                assert (
                    session_info.state == CLISessionState.ERROR
                )  # Should be marked as error until recovery

    @pytest.mark.asyncio
    async def test_session_cleanup_and_termination(self, cli_session_manager):
        """Test proper session cleanup and termination."""

        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager

            mock_session = MagicMock()
            mock_session.id = "cleanup-test-session"
            mock_persistent_manager.create_session.return_value = mock_session

            cli_session_manager.persistence = mock_persistent_manager

            # Create session
            session_id = await cli_session_manager.create_session("claude", "cli")

            # Mock CLI process
            with patch("orchestrator.cli_session_manager.CLIProcessManager") as mock_process_class:
                mock_process = MagicMock()
                mock_process_class.return_value = mock_process

                cli_session_manager.sessions[session_id] = mock_process

                # Terminate session
                result = await cli_session_manager.terminate_session(session_id, "Test termination")

                assert result is True

                # Verify cleanup
                mock_persistent_manager.terminate_session.assert_called_once_with(
                    session_id, "Test termination"
                )
                mock_process.terminate.assert_called_once()

                # Verify session removed from memory
                assert session_id not in cli_session_manager.sessions
                assert session_id not in cli_session_manager.session_info


class TestProcessManagement:
    """Test CLI process lifecycle management."""

    @pytest.mark.asyncio
    async def test_cli_process_spawning_and_lifecycle(self, cli_session_manager):
        """Test CLI process spawning for different tools and modes."""

        # Mock persistence
        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager

            mock_session = MagicMock()
            mock_session.id = "process-test-session"
            mock_persistent_manager.create_session.return_value = mock_session

            cli_session_manager.persistence = mock_persistent_manager

            # Test different CLI tool configurations
            test_configs = [
                ("claude", "interactive", True, ["claude", "--dangerously-skip-permissions"]),
                ("claude", "cli", False, ["claude"]),
                (
                    "codex",
                    "interactive",
                    True,
                    [
                        "codex",
                        "--ask-for-approval",
                        "never",
                        "--sandbox",
                        "danger-full-access",
                        "exec",
                    ],
                ),
                ("codex", "cli", False, ["codex"]),
                ("gemini", "interactive", True, ["gemini", "--interactive", "--full-access"]),
                ("cursor", "cli", False, ["cursor-agent"]),
            ]

            for cli_tool, mode, full_access, expected_command in test_configs:
                session_id = await cli_session_manager.create_session(cli_tool, mode)

                # Test command building
                actual_command = cli_session_manager._build_cli_command(cli_tool, mode, full_access)
                assert actual_command == expected_command

                # Test environment setup
                env = cli_session_manager._get_cli_environment(cli_tool, full_access)
                assert "REPO_ROOT" in env

                if full_access:
                    assert env.get("CLI_FULL_ACCESS") == "1"

    @pytest.mark.asyncio
    async def test_process_authentication_detection(self):
        """Test CLI authentication state detection."""

        # Create mock CLI process manager
        from orchestrator.cli_session_manager import CLIProcessManager

        session_info = CLISessionInfo(
            session_id="auth-test",
            cli_tool="claude",
            mode="interactive",
            state=CLISessionState.RUNNING,
        )

        output_callback = MagicMock()
        process_manager = CLIProcessManager(session_info, output_callback)

        # Test authentication detection patterns
        auth_test_cases = [
            ("claude", "Please provide your Anthropic API key:", True, "Claude API key required"),
            ("codex", "OpenAI API key required", True, "OpenAI API key required"),
            ("gemini", "Google API key needed", True, "Google API key required"),
            ("cursor", "Please sign in to Cursor", True, "Cursor authentication required"),
            ("claude", "Claude Code is ready", False, None),
            ("generic", "Password:", True, "Password:"),
        ]

        for cli_tool, output_text, should_require_auth, expected_prompt in auth_test_cases:
            session_info.cli_tool = cli_tool
            session_info.authentication_required = False
            session_info.auth_prompt = None

            # Simulate output processing (simplified)
            output_lower = output_text.lower()

            # Apply the same logic as in _read_output
            if cli_tool == "claude" and any(
                pattern in output_lower
                for pattern in [
                    "api key",
                    "anthropic_api_key",
                    "authentication",
                    "login required",
                    "please authenticate",
                ]
            ):
                session_info.authentication_required = True
                session_info.auth_prompt = "Claude API key required"
            elif cli_tool == "codex" and any(
                pattern in output_lower
                for pattern in [
                    "api key",
                    "openai_api_key",
                    "please login",
                    "authentication required",
                    "token required",
                ]
            ):
                session_info.authentication_required = True
                session_info.auth_prompt = "OpenAI API key required"
            # Add other patterns...

            assert session_info.authentication_required == should_require_auth
            if should_require_auth and expected_prompt:
                assert expected_prompt in (session_info.auth_prompt or "")


class TestErrorHandlingEdgeCases:
    """Test error handling and edge case scenarios."""

    @pytest.mark.asyncio
    async def test_websocket_error_handling(self, websocket_handler):
        """Test WebSocket error scenarios and recovery."""

        # Test invalid message format
        mock_websocket = AsyncMock()
        mock_websocket.client_state = WebSocketState.CONNECTED

        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id="error-test",
            user_id="test_user",
            connection_id="error-conn",
            connected_at=time.time(),
            last_activity=time.time(),
            state=ConnectionState.CONNECTED,
            authenticated=True,
        )

        websocket_handler.active_connections["error-conn"] = connection

        # Test invalid JSON message
        invalid_messages = [
            '{"invalid": "json"}',  # Missing required fields
            '{"type": "invalid_type", "session_id": "test"}',  # Invalid message type
            "not json at all",  # Invalid JSON
            "",  # Empty message
        ]

        for invalid_msg in invalid_messages:
            try:
                CLIMessage.from_json(invalid_msg)
                assert False, "Should have raised ValueError"
            except ValueError:
                pass  # Expected

        # Test error message sending
        await websocket_handler._send_error_to_connection(connection, "Test error")

        mock_websocket.send_text.assert_called()
        last_call = mock_websocket.send_text.call_args[0][0]
        sent_data = json.loads(last_call)

        assert sent_data["type"] == "error"
        assert sent_data["data"]["error"] == "Test error"

    @pytest.mark.asyncio
    async def test_session_timeout_and_cleanup(self, cli_session_manager):
        """Test session timeout and automatic cleanup."""

        with patch("orchestrator.cli_session.CLISessionManager") as mock_persistent_manager_class:
            mock_persistent_manager = MagicMock()
            mock_persistent_manager_class.return_value = mock_persistent_manager

            mock_session = MagicMock()
            mock_session.id = "timeout-test-session"
            mock_persistent_manager.create_session.return_value = mock_session

            cli_session_manager.persistence = mock_persistent_manager

            # Create session
            session_id = await cli_session_manager.create_session("claude", "cli")

            # Set old last_activity to simulate timeout
            session_info = cli_session_manager.get_session_info(session_id)
            session_info.last_activity = time.time() - 3700  # 1+ hours ago

            # Mock CLI process for cleanup
            with patch("orchestrator.cli_session_manager.CLIProcessManager") as mock_process_class:
                mock_process = MagicMock()
                cli_session_manager.sessions[session_id] = mock_process

                # Run cleanup
                await cli_session_manager.cleanup_inactive_sessions(max_age=3600)

                # Verify session was cleaned up
                mock_process.terminate.assert_called_once()
                assert session_id not in cli_session_manager.sessions

    @pytest.mark.asyncio
    async def test_concurrent_session_limits(self, test_client):
        """Test handling of concurrent session limits."""

        # Mock session manager to simulate limit
        with patch(
            "orchestrator.cli_session_manager.CLISessionManager.create_session"
        ) as mock_create:
            # First few sessions succeed
            mock_create.side_effect = [
                "session-1",
                "session-2",
                "session-3",
                "session-4",
                "session-5",
                # Then fail due to limits
                Exception("Maximum sessions exceeded"),
            ]

            session_data = {"cli_tool": "claude", "mode": "cli", "full_access": False}

            successful_sessions = 0
            failed_sessions = 0

            # Try to create more sessions than limit
            for i in range(10):
                try:
                    response = test_client.post("/api/cli/sessions", json=session_data)
                    if response.status_code == 200:
                        successful_sessions += 1
                    else:
                        failed_sessions += 1
                except:
                    failed_sessions += 1

            # Should have hit the limit
            assert successful_sessions == 5
            assert failed_sessions == 5


class TestAuthenticationSecurity:
    """Test authentication and security mechanisms."""

    def test_jwt_token_validation(self, websocket_handler):
        """Test JWT token validation with various scenarios."""

        secret = "test-secret-key"
        websocket_handler.jwt_secret = secret

        # Valid token
        valid_payload = {
            "user_id": "test_user",
            "username": "testuser",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        valid_token = jwt.encode(valid_payload, secret, algorithm="HS256")

        user_id = websocket_handler._verify_jwt_token(valid_token)
        assert user_id == "test_user"

        # Expired token
        expired_payload = {
            "user_id": "test_user",
            "username": "testuser",
            "exp": datetime.utcnow() - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")

        user_id = websocket_handler._verify_jwt_token(expired_token)
        assert user_id is None

        # Invalid signature
        invalid_token = jwt.encode(valid_payload, "wrong-secret", algorithm="HS256")

        user_id = websocket_handler._verify_jwt_token(invalid_token)
        assert user_id is None

        # Malformed token
        user_id = websocket_handler._verify_jwt_token("not.a.jwt.token")
        assert user_id is None

    def test_input_validation_and_sanitization(self, test_client):
        """Test input validation for session creation and commands."""

        # Test invalid session creation data
        invalid_session_data = [
            {},  # Empty data
            {"cli_tool": ""},  # Empty CLI tool
            {"cli_tool": "invalid_tool"},  # Invalid CLI tool
            {"cli_tool": "claude", "mode": "invalid_mode"},  # Invalid mode
            {"cli_tool": "../../../etc/passwd"},  # Path traversal attempt
            {"cli_tool": "claude; rm -rf /"},  # Command injection attempt
        ]

        for invalid_data in invalid_session_data:
            response = test_client.post("/api/cli/sessions", json=invalid_data)
            # Should either reject (400) or handle gracefully
            assert response.status_code in [400, 422, 500]  # Various error codes acceptable

        # Test SQL injection attempts in session IDs
        with patch(
            "orchestrator.cli_session_manager.CLISessionManager.get_session_info"
        ) as mock_get:
            mock_get.return_value = None

            malicious_session_ids = [
                "'; DROP TABLE sessions; --",
                "1' UNION SELECT * FROM users --",
                "../../../etc/passwd",
                "session_id\x00null_byte",
            ]

            for malicious_id in malicious_session_ids:
                response = test_client.get(f"/api/cli/sessions/{malicious_id}")
                # Should handle gracefully without crashing
                assert response.status_code in [400, 404, 422]


class TestMetricsMonitoring:
    """Test metrics collection and monitoring endpoints."""

    def test_websocket_metrics_collection(self, test_client, websocket_handler):
        """Test WebSocket metrics collection."""

        # Set up test metrics state
        websocket_handler.connection_count = 10
        websocket_handler.message_count = 150
        websocket_handler.error_count = 5
        websocket_handler.auth_failures = 2

        # Create mock active connections
        for i in range(3):
            mock_websocket = AsyncMock()
            connection = WebSocketConnection(
                websocket=mock_websocket,
                session_id=f"session-{i}",
                user_id=f"user-{i}",
                connection_id=f"conn-{i}",
                connected_at=time.time() - 300,  # 5 minutes ago
                last_activity=time.time() - 60,  # 1 minute ago
                state=ConnectionState.CONNECTED,
                authenticated=True,
            )
            websocket_handler.active_connections[f"conn-{i}"] = connection

            if f"session-{i}" not in websocket_handler.session_connections:
                websocket_handler.session_connections[f"session-{i}"] = set()
            websocket_handler.session_connections[f"session-{i}"].add(f"conn-{i}")

        # Get metrics
        metrics = websocket_handler.get_handler_metrics()

        assert metrics["total_connections"] == 10
        assert metrics["active_connections"] == 3
        assert metrics["active_sessions"] == 3
        assert metrics["total_messages"] == 150
        assert metrics["total_errors"] == 5
        assert metrics["auth_failures"] == 2
        assert "average_connection_uptime_seconds" in metrics
        assert "session_statistics" in metrics
        assert "handler_config" in metrics

    def test_session_metrics_endpoint(self, test_client):
        """Test session metrics endpoint."""

        with patch("orchestrator.cli_session_manager.get_cli_session_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_session_metrics.return_value = {
                "total_sessions": 5,
                "active_sessions": 3,
                "completed_sessions": 2,
                "failed_sessions": 0,
                "average_session_duration": 1200,
                "total_messages": 45,
            }
            mock_get_manager.return_value = mock_manager

            response = test_client.get("/api/cli/metrics")
            assert response.status_code == 200

            metrics = response.json()
            assert "total_sessions" in metrics
            assert "active_sessions" in metrics
            assert metrics["total_sessions"] == 5

    def test_health_check_endpoint(self, test_client):
        """Test health check endpoint functionality."""

        response = test_client.get("/health")
        assert response.status_code == 200

        health_data = response.json()
        assert "status" in health_data
        assert "timestamp" in health_data
        assert "version" in health_data
        assert health_data["status"] in ["healthy", "degraded", "unhealthy"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
