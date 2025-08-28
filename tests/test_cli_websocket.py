"""
Enhanced Tests for CLI WebSocket Handler integration.

Comprehensive unit tests covering:
- Message creation, validation, and serialization
- WebSocket connection management and lifecycle
- Authentication and authorization
- Real-time message handling and routing
- Error handling and recovery
- Heartbeat and connection monitoring
- Multi-session support
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketState

from orchestrator.app import app
from orchestrator.cli_websocket import (
    CLIMessage,
    CLIWebSocketHandler,
    ConnectionState,
    MessageType,
    WebSocketConnection,
    get_cli_websocket_handler,
)


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def websocket_handler():
    """Create a fresh WebSocket handler for testing."""
    return CLIWebSocketHandler()


class TestCLIMessage:
    """Test CLI message creation and parsing."""

    def test_message_creation(self):
        """Test creating a CLI message."""
        message = CLIMessage(
            type=MessageType.COMMAND, session_id="test-session", data={"command": "echo hello"}
        )

        assert message.type == MessageType.COMMAND
        assert message.session_id == "test-session"
        assert message.data["command"] == "echo hello"
        assert message.message_id is not None
        assert message.timestamp is not None

    def test_message_serialization(self):
        """Test message to_json and from_json methods."""
        original = CLIMessage(
            type=MessageType.OUTPUT,
            session_id="test-session",
            data={"output": "Hello World", "output_type": "stdout"},
        )

        # Serialize to JSON
        json_str = original.to_json()
        parsed_data = json.loads(json_str)

        assert parsed_data["type"] == "output"
        assert parsed_data["session_id"] == "test-session"
        assert parsed_data["data"]["output"] == "Hello World"

        # Deserialize from JSON
        reconstructed = CLIMessage.from_json(json_str)
        assert reconstructed.type == original.type
        assert reconstructed.session_id == original.session_id
        assert reconstructed.data == original.data

    def test_invalid_message_parsing(self):
        """Test parsing invalid JSON messages."""
        with pytest.raises(ValueError):
            CLIMessage.from_json('{"invalid": "json"}')

        with pytest.raises(ValueError):
            CLIMessage.from_json('{"type": "invalid_type", "session_id": "test"}')


class TestWebSocketHandler:
    """Test WebSocket handler functionality."""

    def test_handler_initialization(self, websocket_handler):
        """Test WebSocket handler initialization."""
        assert len(websocket_handler.active_connections) == 0
        assert len(websocket_handler.session_connections) == 0
        assert websocket_handler.connection_count == 0
        assert websocket_handler.message_count == 0
        assert websocket_handler.error_count == 0

    def test_handler_metrics(self, websocket_handler):
        """Test handler metrics generation."""
        metrics = websocket_handler.get_handler_metrics()

        assert "total_connections" in metrics
        assert "active_connections" in metrics
        assert "total_messages" in metrics
        assert "handler_config" in metrics
        assert metrics["total_connections"] == 0
        assert metrics["active_connections"] == 0

    @pytest.mark.asyncio
    async def test_message_broadcasting(self, websocket_handler):
        """Test message broadcasting to session."""
        # Mock WebSocket connections
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()

        # Create mock connections
        websocket_handler.active_connections["conn1"] = MagicMock()
        websocket_handler.active_connections["conn1"].websocket = mock_websocket1
        websocket_handler.active_connections["conn1"].session_id = "test-session"
        websocket_handler.active_connections["conn1"].message_queue = []

        websocket_handler.active_connections["conn2"] = MagicMock()
        websocket_handler.active_connections["conn2"].websocket = mock_websocket2
        websocket_handler.active_connections["conn2"].session_id = "test-session"
        websocket_handler.active_connections["conn2"].message_queue = []

        websocket_handler.session_connections["test-session"] = {"conn1", "conn2"}

        # Mock WebSocket state
        mock_websocket1.client_state = "connected"
        mock_websocket2.client_state = "connected"

        # Test broadcasting
        test_message = CLIMessage(
            type=MessageType.OUTPUT, session_id="test-session", data={"output": "Test output"}
        )

        await websocket_handler.broadcast_to_session("test-session", test_message)

        # Verify both connections received the message
        mock_websocket1.send_text.assert_called_once()
        mock_websocket2.send_text.assert_called_once()

        # Verify the message content
        sent_data1 = json.loads(mock_websocket1.send_text.call_args[0][0])
        sent_data2 = json.loads(mock_websocket2.send_text.call_args[0][0])

        assert sent_data1["type"] == "output"
        assert sent_data2["type"] == "output"
        assert sent_data1["data"]["output"] == "Test output"
        assert sent_data2["data"]["output"] == "Test output"


class TestAuthenticationIntegration:
    """Test authentication integration with WebSocket handler."""

    def test_login_endpoint(self, test_client):
        """Test the login endpoint for CLI access."""
        credentials = {"username": "admin", "password": "secret", "session_id": "test-session"}

        response = test_client.post("/api/auth/login", json=credentials)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "user_info" in data
        assert data["user_info"]["username"] == "admin"
        assert data["user_info"]["full_access"] is True

    def test_login_invalid_credentials(self, test_client):
        """Test login with invalid credentials."""
        credentials = {"username": "admin", "password": "wrong_password"}

        response = test_client.post("/api/auth/login", json=credentials)
        assert response.status_code == 401

    def test_verify_token_endpoint(self, test_client):
        """Test token verification endpoint."""
        # First get a token
        credentials = {"username": "admin", "password": "secret"}
        login_response = test_client.post("/api/auth/login", json=credentials)
        token = login_response.json()["access_token"]

        # Verify the token
        verify_response = test_client.post("/api/auth/verify", json={"token": token})
        assert verify_response.status_code == 200

        data = verify_response.json()
        assert data["valid"] is True
        assert data["user_info"]["username"] == "admin"


class TestCLISessionIntegration:
    """Test integration with CLI session manager."""

    def test_session_creation_endpoint(self, test_client):
        """Test CLI session creation endpoint."""
        session_data = {"cli_tool": "claude", "mode": "cli", "full_access": False, "cwd": "/tmp"}

        with (
            patch(
                "orchestrator.cli_session_manager.CLISessionManager.create_session"
            ) as mock_create,
            patch(
                "orchestrator.cli_session_manager.CLISessionManager.start_cli_process"
            ) as mock_start,
            patch(
                "orchestrator.cli_session_manager.CLISessionManager.get_session_info"
            ) as mock_info,
        ):
            mock_create.return_value = "test-session-id"
            mock_start.return_value = True
            mock_info.return_value = MagicMock()
            mock_info.return_value.state.value = "running"

            response = test_client.post("/api/cli/sessions", json=session_data)
            assert response.status_code == 200

            data = response.json()
            assert data["session_id"] == "test-session-id"
            assert data["cli_tool"] == "claude"
            assert data["websocket_url"] == "/ws/cli/test-session-id"

    def test_session_list_endpoint(self, test_client):
        """Test CLI session list endpoint."""
        with patch("orchestrator.cli_session_manager.CLISessionManager.list_sessions") as mock_list:
            mock_session = MagicMock()
            mock_session.session_id = "test-session"
            mock_session.cli_tool = "claude"
            mock_session.state.value = "running"
            mock_session.pid = 12345
            mock_list.return_value = [mock_session]

            response = test_client.get("/api/cli/sessions")
            assert response.status_code == 200

            data = response.json()
            assert len(data["sessions"]) == 1
            assert data["sessions"][0]["session_id"] == "test-session"


class TestMetricsEndpoints:
    """Test metrics and monitoring endpoints."""

    def test_websocket_metrics_endpoint(self, test_client):
        """Test WebSocket metrics endpoint."""
        response = test_client.get("/api/websocket/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "total_connections" in data
        assert "active_connections" in data
        assert "total_messages" in data
        assert "handler_config" in data

    def test_websocket_connections_endpoint(self, test_client):
        """Test WebSocket connections endpoint."""
        response = test_client.get("/api/websocket/connections")
        assert response.status_code == 200

        data = response.json()
        assert "connections" in data
        assert "total_active" in data
        assert "by_session" in data

    def test_auth_sessions_endpoint(self, test_client):
        """Test auth sessions endpoint."""
        response = test_client.get("/api/auth/sessions")
        assert response.status_code == 200

        data = response.json()
        assert "auth_sessions" in data
        assert "websocket_connections" in data
        assert "summary" in data


@pytest.mark.asyncio
class TestRealTimeStreaming:
    """Test real-time output streaming functionality."""

    async def test_output_streaming_integration(self, websocket_handler):
        """Test integration between session manager and WebSocket handler."""
        # Mock a CLI session manager callback
        session_id = "test-session"

        # Mock WebSocket connection
        mock_websocket = AsyncMock()
        mock_websocket.client_state = "connected"

        connection = MagicMock()
        connection.websocket = mock_websocket
        connection.session_id = session_id
        connection.message_queue = []

        websocket_handler.active_connections["conn1"] = connection
        websocket_handler.session_connections[session_id] = {"conn1"}

        # Test output streaming
        await websocket_handler.send_output_to_session(session_id, "Hello from CLI!", "stdout")

        # Verify message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])

        assert sent_data["type"] == "output"
        assert sent_data["data"]["output"] == "Hello from CLI!"
        assert sent_data["data"]["output_type"] == "stdout"


class TestWebSocketConnection:
    """Test WebSocketConnection dataclass and functionality."""

    def test_connection_creation(self):
        """Test WebSocket connection creation."""
        mock_websocket = MagicMock()

        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id="test-session",
            user_id="test_user",
            connection_id="test-conn",
            connected_at=1000.0,
            last_activity=2000.0,
            state=ConnectionState.CONNECTED,
            authenticated=True,
        )

        assert connection.websocket == mock_websocket
        assert connection.session_id == "test-session"
        assert connection.user_id == "test_user"
        assert connection.connection_id == "test-conn"
        assert connection.connected_at == 1000.0
        assert connection.last_activity == 2000.0
        assert connection.state == ConnectionState.CONNECTED
        assert connection.authenticated is True
        assert connection.message_queue == []
        assert connection.heartbeat_task is None

    def test_connection_defaults(self):
        """Test WebSocket connection with default values."""
        mock_websocket = MagicMock()

        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id="test-session",
            user_id="test_user",
            connection_id="",
            connected_at=0.0,
            last_activity=0.0,
            state=ConnectionState.CONNECTING,
        )

        assert connection.connection_id != ""  # Should generate UUID
        assert connection.connected_at > 0  # Should set current time
        assert connection.last_activity > 0  # Should set current time
        assert connection.message_queue == []
        assert connection.authenticated is False  # Default


class TestEnhancedWebSocketHandler:
    """Enhanced tests for WebSocket handler functionality."""

    @pytest.fixture
    def handler(self):
        """Create fresh WebSocket handler."""
        return CLIWebSocketHandler()

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        mock = AsyncMock()
        mock.client_state = WebSocketState.CONNECTED
        return mock

    @pytest.fixture
    def test_connection(self, mock_websocket):
        """Create test WebSocket connection."""
        return WebSocketConnection(
            websocket=mock_websocket,
            session_id="test-session",
            user_id="test_user",
            connection_id="test-conn",
            connected_at=time.time(),
            last_activity=time.time(),
            state=ConnectionState.CONNECTED,
            authenticated=True,
        )

    def test_handler_initialization_comprehensive(self, handler):
        """Test comprehensive handler initialization."""
        assert len(handler.active_connections) == 0
        assert len(handler.session_connections) == 0
        assert len(handler.message_handlers) == 5  # COMMAND, CANCEL, STATUS, PING, AUTH
        assert handler.jwt_secret is not None
        assert handler.heartbeat_interval == 30
        assert handler.max_message_queue_size == 100
        assert handler.connection_count == 0
        assert handler.message_count == 0
        assert handler.error_count == 0
        assert handler.auth_failures == 0

    @pytest.mark.asyncio
    async def test_connection_registration(self, handler, test_connection):
        """Test connection registration and tracking."""
        connection_id = test_connection.connection_id
        session_id = test_connection.session_id

        # Register connection
        handler.active_connections[connection_id] = test_connection
        if session_id not in handler.session_connections:
            handler.session_connections[session_id] = set()
        handler.session_connections[session_id].add(connection_id)

        # Verify registration
        assert connection_id in handler.active_connections
        assert session_id in handler.session_connections
        assert connection_id in handler.session_connections[session_id]
        assert len(handler.active_connections) == 1
        assert len(handler.session_connections) == 1

    @pytest.mark.asyncio
    async def test_message_queue_functionality(self, handler, test_connection):
        """Test message queuing when connection is unavailable."""
        # Simulate disconnected WebSocket
        test_connection.websocket.client_state = WebSocketState.DISCONNECTED

        test_message = CLIMessage(
            type=MessageType.OUTPUT,
            session_id=test_connection.session_id,
            data={"output": "Test output"},
            timestamp=datetime.utcnow().isoformat(),
        )

        # Send message (should be queued)
        await handler._send_message_to_connection(test_connection, test_message)

        # Verify message was queued
        assert len(test_connection.message_queue) == 1
        assert test_connection.message_queue[0] == test_message

        # Simulate reconnection
        test_connection.websocket.client_state = WebSocketState.CONNECTED

        # Flush queue
        await handler._flush_message_queue(test_connection)

        # Verify message was sent and queue cleared
        test_connection.websocket.send_text.assert_called_once()
        assert len(test_connection.message_queue) == 0

    @pytest.mark.asyncio
    async def test_message_queue_overflow(self, handler, test_connection):
        """Test message queue overflow handling."""
        # Set small queue size for testing
        handler.max_message_queue_size = 3

        # Simulate disconnected WebSocket
        test_connection.websocket.client_state = WebSocketState.DISCONNECTED

        # Send more messages than queue can handle
        for i in range(5):
            test_message = CLIMessage(
                type=MessageType.OUTPUT,
                session_id=test_connection.session_id,
                data={"output": f"Message {i}"},
                timestamp=datetime.utcnow().isoformat(),
            )
            await handler._send_message_to_connection(test_connection, test_message)

        # Queue should not exceed max size
        assert len(test_connection.message_queue) == 3

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_connections(self, handler):
        """Test broadcasting message to multiple connections in same session."""
        session_id = "broadcast-test-session"
        connections = []

        # Create multiple connections for same session
        for i in range(3):
            mock_websocket = AsyncMock()
            mock_websocket.client_state = WebSocketState.CONNECTED

            connection = WebSocketConnection(
                websocket=mock_websocket,
                session_id=session_id,
                user_id=f"user_{i}",
                connection_id=f"conn_{i}",
                connected_at=time.time(),
                last_activity=time.time(),
                state=ConnectionState.CONNECTED,
                authenticated=True,
            )

            handler.active_connections[f"conn_{i}"] = connection
            connections.append(connection)

        handler.session_connections[session_id] = {f"conn_{i}" for i in range(3)}

        # Broadcast message
        test_message = CLIMessage(
            type=MessageType.OUTPUT,
            session_id=session_id,
            data={"output": "Broadcast test"},
            timestamp=datetime.utcnow().isoformat(),
        )

        await handler.broadcast_to_session(session_id, test_message)

        # Verify all connections received the message
        for connection in connections:
            connection.websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_authentication_flow(self, handler, mock_websocket):
        """Test authentication message flow."""
        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id="auth-test",
            user_id="anonymous",
            connection_id="auth-conn",
            connected_at=time.time(),
            last_activity=time.time(),
            state=ConnectionState.CONNECTED,
            authenticated=False,
        )

        # Mock JWT verification
        handler.jwt_secret = "test-secret"

        # Valid token
        valid_payload = {
            "user_id": "authenticated_user",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        valid_token = jwt.encode(valid_payload, "test-secret", algorithm="HS256")

        auth_message = CLIMessage(
            type=MessageType.AUTH,
            session_id=connection.session_id,
            data={"token": valid_token},
            timestamp=datetime.utcnow().isoformat(),
        )

        await handler._handle_auth(connection, auth_message)

        # Verify authentication success
        assert connection.authenticated is True
        assert connection.user_id == "authenticated_user"
        assert connection.state == ConnectionState.AUTHENTICATED

        # Verify response sent
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "status"
        assert sent_data["data"]["authenticated"] is True

    @pytest.mark.asyncio
    async def test_heartbeat_functionality(self, handler):
        """Test heartbeat mechanism."""
        mock_websocket = AsyncMock()
        mock_websocket.client_state = WebSocketState.CONNECTED

        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id="heartbeat-test",
            user_id="test_user",
            connection_id="heartbeat-conn",
            connected_at=time.time(),
            last_activity=time.time() - 70,  # 70 seconds ago (older than 2 * heartbeat_interval)
            state=ConnectionState.CONNECTED,
            authenticated=True,
        )

        # Start heartbeat (short timeout for testing)
        heartbeat_task = asyncio.create_task(handler._heartbeat_loop(connection))

        # Wait briefly for heartbeat to trigger
        await asyncio.sleep(0.1)

        # Cancel the heartbeat task
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        # Verify ping was sent due to inactive connection
        mock_websocket.send_text.assert_called()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data["type"] == "ping"

    @pytest.mark.asyncio
    async def test_command_handling_with_session_manager(self, handler, test_connection):
        """Test command handling integration with session manager."""
        handler.active_connections[test_connection.connection_id] = test_connection

        command_message = CLIMessage(
            type=MessageType.COMMAND,
            session_id=test_connection.session_id,
            data={"command": "ls -la"},
            timestamp=datetime.utcnow().isoformat(),
        )

        with patch("orchestrator.cli_session_manager.get_cli_session_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.send_input_to_session = AsyncMock(return_value=True)
            mock_get_manager.return_value = mock_manager

            await handler._handle_command(test_connection, command_message)

            # Verify session manager was called
            mock_manager.send_input_to_session.assert_called_once_with(
                test_connection.session_id, "ls -la"
            )

            # Verify acknowledgment sent
            test_connection.websocket.send_text.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_command_handling(self, handler, test_connection):
        """Test command cancellation handling."""
        handler.active_connections[test_connection.connection_id] = test_connection

        cancel_message = CLIMessage(
            type=MessageType.CANCEL,
            session_id=test_connection.session_id,
            data={},
            timestamp=datetime.utcnow().isoformat(),
        )

        with patch("orchestrator.cli_session_manager.get_cli_session_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.send_input_to_session = AsyncMock(return_value=True)
            mock_get_manager.return_value = mock_manager

            await handler._handle_cancel(test_connection, cancel_message)

            # Verify interrupt signal (Ctrl+C) was sent
            mock_manager.send_input_to_session.assert_called_once_with(
                test_connection.session_id, "\x03"
            )

    @pytest.mark.asyncio
    async def test_status_request_handling(self, handler, test_connection):
        """Test status request handling."""
        handler.active_connections[test_connection.connection_id] = test_connection

        status_message = CLIMessage(
            type=MessageType.STATUS,
            session_id=test_connection.session_id,
            data={},
            timestamp=datetime.utcnow().isoformat(),
        )

        with patch("orchestrator.cli_session_manager.get_cli_session_manager") as mock_get_manager:
            from orchestrator.cli_session_manager import CLISessionState

            mock_manager = MagicMock()
            mock_session_info = MagicMock()
            mock_session_info.session_id = test_connection.session_id
            mock_session_info.cli_tool = "claude"
            mock_session_info.mode = "interactive"
            mock_session_info.state = CLISessionState.RUNNING
            mock_session_info.pid = 12345
            mock_session_info.authentication_required = False
            mock_session_info.current_directory = "/tmp"
            mock_session_info.last_activity = time.time()
            mock_session_info.command_history = ["ls", "pwd", "echo hello"]

            mock_manager.get_session_info.return_value = mock_session_info
            mock_get_manager.return_value = mock_manager

            await handler._handle_status_request(test_connection, status_message)

            # Verify status response sent
            test_connection.websocket.send_text.assert_called()
            sent_data = json.loads(test_connection.websocket.send_text.call_args[0][0])

            assert sent_data["type"] == "status"
            assert sent_data["data"]["session_id"] == test_connection.session_id
            assert sent_data["data"]["cli_tool"] == "claude"
            assert sent_data["data"]["pid"] == 12345

    @pytest.mark.asyncio
    async def test_ping_pong_mechanism(self, handler, test_connection):
        """Test ping-pong mechanism."""
        handler.active_connections[test_connection.connection_id] = test_connection

        ping_message = CLIMessage(
            type=MessageType.PING,
            session_id=test_connection.session_id,
            data={"timestamp": time.time()},
            timestamp=datetime.utcnow().isoformat(),
            message_id="ping-123",
        )

        await handler._handle_ping(test_connection, ping_message)

        # Verify pong response
        test_connection.websocket.send_text.assert_called_once()
        sent_data = json.loads(test_connection.websocket.send_text.call_args[0][0])

        assert sent_data["type"] == "pong"
        assert sent_data["data"]["message_id"] == "ping-123"

    @pytest.mark.asyncio
    async def test_error_handling_in_message_processing(self, handler, test_connection):
        """Test error handling during message processing."""
        handler.active_connections[test_connection.connection_id] = test_connection

        # Create message that will cause handler to fail
        problematic_message = CLIMessage(
            type=MessageType.COMMAND,
            session_id=test_connection.session_id,
            data={"command": "test"},
            timestamp=datetime.utcnow().isoformat(),
        )

        with patch("orchestrator.cli_session_manager.get_cli_session_manager") as mock_get_manager:
            # Make session manager throw an exception
            mock_manager = MagicMock()
            mock_manager.send_input_to_session = AsyncMock(side_effect=Exception("Test error"))
            mock_get_manager.return_value = mock_manager

            await handler._handle_command(test_connection, problematic_message)

            # Verify error response sent
            test_connection.websocket.send_text.assert_called()
            sent_data = json.loads(test_connection.websocket.send_text.call_args[0][0])
            assert sent_data["type"] == "error"
            assert "Command execution failed" in sent_data["data"]["error"]

    def test_jwt_token_verification_edge_cases(self, handler):
        """Test JWT token verification with various edge cases."""
        handler.jwt_secret = "test-secret-key"

        # Test cases: (token_data, expected_result)
        test_cases = [
            # Valid token
            (
                {"user_id": "valid_user", "exp": datetime.utcnow() + timedelta(hours=1)},
                "valid_user",
            ),
            # Expired token
            ({"user_id": "expired_user", "exp": datetime.utcnow() - timedelta(hours=1)}, None),
            # Token without user_id
            ({"username": "no_user_id", "exp": datetime.utcnow() + timedelta(hours=1)}, None),
            # Token without expiration
            ({"user_id": "no_exp"}, None),
        ]

        for token_data, expected_result in test_cases:
            if token_data:
                token = jwt.encode(token_data, "test-secret-key", algorithm="HS256")
                result = handler._verify_jwt_token(token)
            else:
                result = handler._verify_jwt_token("invalid-token")

            assert result == expected_result

        # Test malformed token
        assert handler._verify_jwt_token("not.a.jwt") is None
        assert handler._verify_jwt_token("") is None

        # Test token with wrong secret
        wrong_secret_token = jwt.encode(
            {"user_id": "test", "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong-secret",
            algorithm="HS256",
        )
        assert handler._verify_jwt_token(wrong_secret_token) is None

    def test_handler_metrics_comprehensive(self, handler):
        """Test comprehensive handler metrics collection."""
        current_time = time.time()

        # Set up test state
        handler.connection_count = 15
        handler.message_count = 200
        handler.error_count = 5
        handler.auth_failures = 3

        # Add mock connections
        for i in range(4):
            mock_websocket = AsyncMock()
            connection = WebSocketConnection(
                websocket=mock_websocket,
                session_id=f"session-{i % 2}",  # 2 unique sessions
                user_id=f"user-{i}",
                connection_id=f"conn-{i}",
                connected_at=current_time - (i * 100),  # Different connection times
                last_activity=current_time - (i * 10),
                state=ConnectionState.CONNECTED,
                authenticated=i % 2 == 0,  # Half authenticated
            )

            # Add some queued messages
            for j in range(i):
                connection.message_queue.append(
                    CLIMessage(
                        type=MessageType.OUTPUT,
                        session_id=connection.session_id,
                        data={"test": f"message-{j}"},
                        timestamp=datetime.utcnow().isoformat(),
                    )
                )

            handler.active_connections[f"conn-{i}"] = connection

            session_id = connection.session_id
            if session_id not in handler.session_connections:
                handler.session_connections[session_id] = set()
            handler.session_connections[session_id].add(f"conn-{i}")

        # Get metrics
        metrics = handler.get_handler_metrics()

        # Verify core metrics
        assert metrics["total_connections"] == 15
        assert metrics["active_connections"] == 4
        assert metrics["active_sessions"] == 2
        assert metrics["total_messages"] == 200
        assert metrics["total_errors"] == 5
        assert metrics["auth_failures"] == 3

        # Verify session statistics
        assert "session_statistics" in metrics
        assert len(metrics["session_statistics"]) == 2

        for session_stats in metrics["session_statistics"].values():
            assert "active_connections" in session_stats
            assert "authenticated_connections" in session_stats
            assert "total_queued_messages" in session_stats

        # Verify handler config
        assert "handler_config" in metrics
        config = metrics["handler_config"]
        assert config["heartbeat_interval"] == 30
        assert config["max_message_queue_size"] == 100

        # Verify average uptime calculation
        assert "average_connection_uptime_seconds" in metrics
        assert metrics["average_connection_uptime_seconds"] > 0

    @pytest.mark.asyncio
    async def test_connection_cleanup(self, handler):
        """Test proper connection cleanup."""
        mock_websocket = AsyncMock()

        # Create connection with heartbeat task
        connection = WebSocketConnection(
            websocket=mock_websocket,
            session_id="cleanup-test",
            user_id="test_user",
            connection_id="cleanup-conn",
            connected_at=time.time(),
            last_activity=time.time(),
            state=ConnectionState.CONNECTED,
            authenticated=True,
        )

        # Mock heartbeat task
        mock_task = AsyncMock()
        connection.heartbeat_task = mock_task

        # Register connection
        handler.active_connections["cleanup-conn"] = connection
        handler.session_connections["cleanup-test"] = {"cleanup-conn"}

        # Cleanup connection
        await handler._cleanup_connection("cleanup-conn")

        # Verify cleanup
        mock_task.cancel.assert_called_once()
        assert "cleanup-conn" not in handler.active_connections
        assert "cleanup-test" not in handler.session_connections


class TestSingletonWebSocketHandler:
    """Test singleton WebSocket handler functionality."""

    def test_get_websocket_handler_singleton(self):
        """Test singleton pattern for WebSocket handler."""
        handler1 = get_cli_websocket_handler()
        handler2 = get_cli_websocket_handler()

        assert handler1 is handler2
        assert isinstance(handler1, CLIWebSocketHandler)

    def test_singleton_state_preservation(self):
        """Test that singleton preserves state across calls."""
        handler1 = get_cli_websocket_handler()

        # Modify state
        handler1.connection_count = 100

        handler2 = get_cli_websocket_handler()
        assert handler2.connection_count == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
