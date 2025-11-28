"""
WebSocket Handler for Real-time CLI Communication
Handles bidirectional communication between dashboard and CLI processes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import jwt
from fastapi import WebSocket, WebSocketDisconnect, status
from fastapi.websockets import WebSocketState

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configure specific log levels for components
logging.getLogger("fastapi").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)


class MessageType(Enum):
    """WebSocket message types for CLI communication."""

    COMMAND = "command"
    OUTPUT = "output"
    STATUS = "status"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    CANCEL = "cancel"
    AUTH = "auth"


class ConnectionState(Enum):
    """WebSocket connection states."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class CLIMessage:
    """Structured message for CLI WebSocket communication."""

    type: MessageType
    session_id: str
    data: dict[str, Any]
    timestamp: str
    message_id: str = None

    def __post_init__(self):
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "data": self.data,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> CLIMessage:
        """Create CLIMessage from JSON string with validation."""
        try:
            data = json.loads(json_str)
            return cls(
                type=MessageType(data.get("type")),
                session_id=data.get("session_id", ""),
                data=data.get("data", {}),
                timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
                message_id=data.get("message_id"),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            raise ValueError(f"Invalid message format: {e}")


@dataclass
class WebSocketConnection:
    """Represents an active WebSocket connection."""

    websocket: WebSocket
    session_id: str
    user_id: str
    connection_id: str
    connected_at: float
    last_activity: float
    state: ConnectionState
    authenticated: bool = False
    message_queue: list[CLIMessage] = None
    heartbeat_task: asyncio.Task | None = None

    def __post_init__(self):
        if self.message_queue is None:
            self.message_queue = []
        if not self.connected_at:
            self.connected_at = time.time()
        if not self.last_activity:
            self.last_activity = time.time()
        if not self.connection_id:
            self.connection_id = str(uuid.uuid4())


class CLIWebSocketHandler:
    """
    Handles WebSocket connections for real-time CLI communication.

    Features:
    - Message routing and processing
    - Real-time output streaming
    - Connection management with heartbeat
    - Authentication via JWT tokens
    - Message queuing during disconnections
    - Proper error handling and logging
    """

    def __init__(self):
        self.active_connections: dict[str, WebSocketConnection] = {}
        self.session_connections: dict[str, set[str]] = {}  # session_id -> connection_ids
        self.message_handlers: dict[MessageType, Callable] = {
            MessageType.COMMAND: self._handle_command,
            MessageType.CANCEL: self._handle_cancel,
            MessageType.STATUS: self._handle_status_request,
            MessageType.PING: self._handle_ping,
            MessageType.AUTH: self._handle_auth,
        }
        self.jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-here")
        self.heartbeat_interval = 30  # seconds
        self.max_message_queue_size = 100

        # Error tracking and metrics
        self.connection_count = 0
        self.message_count = 0
        self.error_count = 0
        self.auth_failures = 0

        # Log startup
        logger.info(
            f"CLI WebSocket Handler initialized with JWT secret: {'***' if self.jwt_secret != 'your-secret-key-here' else 'DEFAULT (CHANGE IN PRODUCTION)'}"
        )
        logger.info(
            f"Heartbeat interval: {self.heartbeat_interval}s, Max queue size: {self.max_message_queue_size}"
        )

    async def handle_connection(self, websocket: WebSocket, session_id: str, token: str = None):
        """Handle new WebSocket connection with authentication."""
        connection_id = str(uuid.uuid4())

        try:
            # Accept WebSocket connection
            await websocket.accept()

            # Verify authentication token if provided
            user_id = "anonymous"
            if token:
                try:
                    user_id = self._verify_jwt_token(token)
                    if not user_id:
                        self.auth_failures += 1
                        logger.warning(
                            f"Authentication failed for session {session_id}: Invalid token"
                        )
                        await self._send_error(websocket, "Invalid authentication token")
                        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                        return
                    logger.info(
                        f"Authentication successful for user {user_id} in session {session_id}"
                    )
                except Exception as e:
                    self.auth_failures += 1
                    logger.error(f"Authentication error for session {session_id}: {e}")
                    await self._send_error(websocket, "Authentication error")
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return

            # Create connection object
            connection = WebSocketConnection(
                websocket=websocket,
                session_id=session_id,
                user_id=user_id,
                connection_id=connection_id,
                connected_at=time.time(),
                last_activity=time.time(),
                state=ConnectionState.CONNECTED,
                authenticated=bool(token and user_id != "anonymous"),
            )

            # Register connection
            self.active_connections[connection_id] = connection
            if session_id not in self.session_connections:
                self.session_connections[session_id] = set()
            self.session_connections[session_id].add(connection_id)

            # Update metrics
            self.connection_count += 1

            logger.info(
                f"WebSocket connection established: {connection_id} for session {session_id} "
                f"(user: {user_id}, authenticated: {connection.authenticated}, "
                f"total active: {len(self.active_connections)})"
            )

            # Start heartbeat
            connection.heartbeat_task = asyncio.create_task(self._heartbeat_loop(connection))

            # Send connection status
            await self._send_status_update(
                connection,
                {
                    "connected": True,
                    "session_id": session_id,
                    "authenticated": connection.authenticated,
                    "connection_id": connection_id,
                },
            )

            # Flush any queued messages
            await self._flush_message_queue(connection)

            # Handle incoming messages
            await self._handle_messages(connection)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        finally:
            await self._cleanup_connection(connection_id)

    async def _handle_messages(self, connection: WebSocketConnection):
        """Main message handling loop."""
        try:
            while connection.websocket.client_state == WebSocketState.CONNECTED:
                try:
                    # Receive message with timeout
                    data = await asyncio.wait_for(
                        connection.websocket.receive_text(),
                        timeout=60.0,  # 60 second timeout
                    )

                    # Parse and validate message
                    try:
                        message = CLIMessage.from_json(data)
                        self.message_count += 1
                        logger.debug(
                            f"Received message from {connection.connection_id}: {message.type.value}"
                        )
                    except ValueError as e:
                        self.error_count += 1
                        logger.warning(f"Invalid message from {connection.connection_id}: {e}")
                        await self._send_error_to_connection(
                            connection, f"Invalid message format: {e}"
                        )
                        continue

                    # Update activity timestamp
                    connection.last_activity = time.time()

                    # Route message to appropriate handler
                    handler = self.message_handlers.get(message.type)
                    if handler:
                        try:
                            await handler(connection, message)
                        except Exception as e:
                            self.error_count += 1
                            logger.error(
                                f"Handler error for {message.type.value} from {connection.connection_id}: {e}",
                                exc_info=True,
                            )
                            await self._send_error_to_connection(
                                connection, f"Handler error: {e!s}"
                            )
                    else:
                        self.error_count += 1
                        logger.warning(
                            f"Unknown message type from {connection.connection_id}: {message.type.value}"
                        )
                        await self._send_error_to_connection(
                            connection, f"Unknown message type: {message.type.value}"
                        )

                except TimeoutError:
                    # Send ping to check if connection is still alive
                    await self._send_ping(connection)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error handling message from {connection.connection_id}: {e}")
                    await self._send_error_to_connection(
                        connection, f"Error processing message: {e}"
                    )

        except Exception as e:
            logger.error(f"Fatal error in message handling for {connection.connection_id}: {e}")

    async def _handle_command(self, connection: WebSocketConnection, message: CLIMessage):
        """Handle command execution request."""
        try:
            # Accept both `command` (preferred) and legacy `prompt`
            command = message.data.get("command") or message.data.get("prompt") or ""

            # Get CLI session manager to check if this is an interactive session
            from orchestrator.cli_session_manager import get_cli_session_manager

            manager = get_cli_session_manager()
            session_info = manager.get_session_info(connection.session_id)

            # Allow empty commands in interactive mode (for authentication prompts, Enter key, etc.)
            is_interactive = session_info and session_info.mode == "interactive"
            if not command.strip() and not is_interactive:
                await self._send_error_to_connection(connection, "Empty command")
                return

            logger.info(
                f"Executing command for session {connection.session_id}: {repr(command)[:100]}..."
            )

            # Send command to CLI process
            success = await manager.send_input_to_session(connection.session_id, command)

            if not success:
                await self._send_error_to_connection(
                    connection, "Failed to send command to CLI session"
                )
                return

            # Send acknowledgment
            await self._send_message_to_connection(
                connection,
                CLIMessage(
                    type=MessageType.STATUS,
                    session_id=connection.session_id,
                    data={
                        "status": "command_sent",
                        "command": command,
                        "message_id": message.message_id,
                    },
                    timestamp=datetime.utcnow().isoformat(),
                ),
            )

        except Exception as e:
            logger.error(f"Error handling command: {e}")
            await self._send_error_to_connection(connection, f"Command execution failed: {e}")

    async def _handle_cancel(self, connection: WebSocketConnection, message: CLIMessage):
        """Handle command cancellation request."""
        try:
            logger.info(f"Cancelling command for session {connection.session_id}")

            # Get CLI session manager
            from orchestrator.cli_session_manager import get_cli_session_manager

            manager = get_cli_session_manager()

            # Send interrupt signal (Ctrl+C)
            success = await manager.send_input_to_session(connection.session_id, "\x03")

            if success:
                await self._send_message_to_connection(
                    connection,
                    CLIMessage(
                        type=MessageType.STATUS,
                        session_id=connection.session_id,
                        data={"status": "cancelled", "message_id": message.message_id},
                        timestamp=datetime.utcnow().isoformat(),
                    ),
                )
            else:
                await self._send_error_to_connection(connection, "Failed to cancel command")

        except Exception as e:
            logger.error(f"Error handling cancel: {e}")
            await self._send_error_to_connection(connection, f"Cancel failed: {e}")

    async def _handle_status_request(self, connection: WebSocketConnection, message: CLIMessage):
        """Handle status information request."""
        try:
            # Get CLI session manager
            from orchestrator.cli_session_manager import get_cli_session_manager

            manager = get_cli_session_manager()

            session_info = manager.get_session_info(connection.session_id)

            if session_info:
                status_data = {
                    "session_id": session_info.session_id,
                    "cli_tool": session_info.cli_tool,
                    "mode": session_info.mode,
                    "state": session_info.state.value,
                    "pid": session_info.pid,
                    "authentication_required": session_info.authentication_required,
                    "current_directory": session_info.current_directory,
                    "last_activity": session_info.last_activity,
                    "command_history": session_info.command_history[-5:],  # Last 5 commands
                }
            else:
                status_data = {"session_id": connection.session_id, "error": "Session not found"}

            await self._send_message_to_connection(
                connection,
                CLIMessage(
                    type=MessageType.STATUS,
                    session_id=connection.session_id,
                    data=status_data,
                    timestamp=datetime.utcnow().isoformat(),
                ),
            )

        except Exception as e:
            logger.error(f"Error handling status request: {e}")
            await self._send_error_to_connection(connection, f"Status request failed: {e}")

    async def _handle_ping(self, connection: WebSocketConnection, message: CLIMessage):
        """Handle ping message."""
        await self._send_message_to_connection(
            connection,
            CLIMessage(
                type=MessageType.PONG,
                session_id=connection.session_id,
                data={"message_id": message.message_id},
                timestamp=datetime.utcnow().isoformat(),
            ),
        )

    async def _handle_auth(self, connection: WebSocketConnection, message: CLIMessage):
        """Handle authentication message."""
        try:
            token = message.data.get("token", "")
            if not token:
                await self._send_error_to_connection(connection, "No token provided")
                return

            user_id = self._verify_jwt_token(token)
            if not user_id:
                await self._send_error_to_connection(connection, "Invalid token")
                return

            connection.user_id = user_id
            connection.authenticated = True
            connection.state = ConnectionState.AUTHENTICATED

            await self._send_message_to_connection(
                connection,
                CLIMessage(
                    type=MessageType.STATUS,
                    session_id=connection.session_id,
                    data={
                        "authenticated": True,
                        "user_id": user_id,
                        "message_id": message.message_id,
                    },
                    timestamp=datetime.utcnow().isoformat(),
                ),
            )

        except Exception as e:
            logger.error(f"Error handling auth: {e}")
            await self._send_error_to_connection(connection, f"Authentication failed: {e}")

    async def _send_message_to_connection(
        self, connection: WebSocketConnection, message: CLIMessage
    ):
        """Send message to a specific connection."""
        try:
            if connection.websocket.client_state == WebSocketState.CONNECTED:
                await connection.websocket.send_text(message.to_json())
            else:
                # Queue message if connection is temporarily unavailable
                if len(connection.message_queue) < self.max_message_queue_size:
                    connection.message_queue.append(message)
                else:
                    logger.warning(f"Message queue full for connection {connection.connection_id}")

        except Exception as e:
            logger.error(f"Error sending message to connection {connection.connection_id}: {e}")

    async def _send_error_to_connection(self, connection: WebSocketConnection, error_message: str):
        """Send error message to connection."""
        error_msg = CLIMessage(
            type=MessageType.ERROR,
            session_id=connection.session_id,
            data={"error": error_message},
            timestamp=datetime.utcnow().isoformat(),
        )
        await self._send_message_to_connection(connection, error_msg)

    async def _send_status_update(
        self, connection: WebSocketConnection, status_data: dict[str, Any]
    ):
        """Send status update to connection."""
        status_msg = CLIMessage(
            type=MessageType.STATUS,
            session_id=connection.session_id,
            data=status_data,
            timestamp=datetime.utcnow().isoformat(),
        )
        await self._send_message_to_connection(connection, status_msg)

    async def _send_ping(self, connection: WebSocketConnection):
        """Send ping message to check connection."""
        ping_msg = CLIMessage(
            type=MessageType.PING,
            session_id=connection.session_id,
            data={"timestamp": time.time()},
            timestamp=datetime.utcnow().isoformat(),
        )
        await self._send_message_to_connection(connection, ping_msg)

    async def _flush_message_queue(self, connection: WebSocketConnection):
        """Flush queued messages to connection."""
        if not connection.message_queue:
            return

        messages_to_send = connection.message_queue.copy()
        connection.message_queue.clear()

        for message in messages_to_send:
            await self._send_message_to_connection(connection, message)

    async def _heartbeat_loop(self, connection: WebSocketConnection):
        """Heartbeat loop to keep connection alive."""
        try:
            while connection.websocket.client_state == WebSocketState.CONNECTED:
                await asyncio.sleep(self.heartbeat_interval)

                # Check if connection is still active
                if time.time() - connection.last_activity > self.heartbeat_interval * 2:
                    logger.info(f"Sending heartbeat to connection {connection.connection_id}")
                    await self._send_ping(connection)

        except asyncio.CancelledError:
            pass  # Task was cancelled, this is expected
        except Exception as e:
            logger.error(f"Heartbeat error for connection {connection.connection_id}: {e}")

    async def _cleanup_connection(self, connection_id: str):
        """Clean up connection resources."""
        try:
            connection = self.active_connections.get(connection_id)
            if connection:
                # Cancel heartbeat task
                if connection.heartbeat_task:
                    connection.heartbeat_task.cancel()
                    try:
                        await connection.heartbeat_task
                    except asyncio.CancelledError:
                        pass

                # Remove from session connections
                if connection.session_id in self.session_connections:
                    self.session_connections[connection.session_id].discard(connection_id)
                    if not self.session_connections[connection.session_id]:
                        del self.session_connections[connection.session_id]

                # Remove from active connections
                del self.active_connections[connection_id]

                logger.info(f"Cleaned up connection: {connection_id}")

        except Exception as e:
            logger.error(f"Error cleaning up connection {connection_id}: {e}")

    def _verify_jwt_token(self, token: str) -> str | None:
        """Verify JWT token and return user ID.

        Supports HS256 with shared secret (default) and RS256 when
        JWT_PUBLIC_KEY is provided in the environment.
        """
        try:
            public_key = os.getenv("JWT_PUBLIC_KEY")
            if public_key:
                # RS256 verification
                payload = jwt.decode(token, public_key, algorithms=["RS256"])
            else:
                # HS256 verification
                payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload.get("user_id")
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None

    async def broadcast_to_session(self, session_id: str, message: CLIMessage):
        """Broadcast message to all connections for a session."""
        if session_id not in self.session_connections:
            return

        connection_ids = self.session_connections[session_id].copy()

        for connection_id in connection_ids:
            connection = self.active_connections.get(connection_id)
            if connection:
                await self._send_message_to_connection(connection, message)

    async def send_output_to_session(
        self, session_id: str, output: str, output_type: str = "stdout"
    ):
        """Send CLI output to all connections for a session."""
        output_msg = CLIMessage(
            type=MessageType.OUTPUT,
            session_id=session_id,
            data={"output": output, "output_type": output_type, "timestamp": time.time()},
            timestamp=datetime.utcnow().isoformat(),
        )
        await self.broadcast_to_session(session_id, output_msg)

    async def send_error_to_session(self, session_id: str, error: str):
        """Send error message to all connections for a session."""
        error_msg = CLIMessage(
            type=MessageType.ERROR,
            session_id=session_id,
            data={"error": error},
            timestamp=datetime.utcnow().isoformat(),
        )
        await self.broadcast_to_session(session_id, error_msg)

    def get_active_connections(self) -> dict[str, dict[str, Any]]:
        """Get information about all active connections."""
        return {
            conn_id: {
                "session_id": conn.session_id,
                "user_id": conn.user_id,
                "connected_at": conn.connected_at,
                "last_activity": conn.last_activity,
                "authenticated": conn.authenticated,
                "state": conn.state.value,
                "queued_messages": len(conn.message_queue),
            }
            for conn_id, conn in self.active_connections.items()
        }

    def get_handler_metrics(self) -> dict[str, Any]:
        """Get WebSocket handler metrics."""
        current_time = time.time()

        # Calculate session statistics
        session_stats = {}
        for session_id, connection_ids in self.session_connections.items():
            active_conns = [
                self.active_connections.get(conn_id)
                for conn_id in connection_ids
                if conn_id in self.active_connections
            ]
            session_stats[session_id] = {
                "active_connections": len(active_conns),
                "authenticated_connections": sum(
                    1 for conn in active_conns if conn and conn.authenticated
                ),
                "total_queued_messages": sum(
                    len(conn.message_queue) for conn in active_conns if conn
                ),
            }

        # Calculate uptime for active connections
        connection_uptimes = []
        for conn in self.active_connections.values():
            uptime = current_time - conn.connected_at
            connection_uptimes.append(uptime)

        avg_uptime = sum(connection_uptimes) / len(connection_uptimes) if connection_uptimes else 0

        return {
            "total_connections": self.connection_count,
            "active_connections": len(self.active_connections),
            "active_sessions": len(self.session_connections),
            "total_messages": self.message_count,
            "total_errors": self.error_count,
            "auth_failures": self.auth_failures,
            "average_connection_uptime_seconds": round(avg_uptime, 2),
            "session_statistics": session_stats,
            "handler_config": {
                "heartbeat_interval": self.heartbeat_interval,
                "max_message_queue_size": self.max_message_queue_size,
                "jwt_configured": self.jwt_secret != "your-secret-key-here",
            },
            "timestamp": current_time,
        }

    async def _send_error(self, websocket: WebSocket, error_message: str):
        """Send error message to websocket (used before connection is established)."""
        try:
            error_data = {
                "type": "error",
                "data": {"error": error_message},
                "timestamp": datetime.utcnow().isoformat(),
            }
            await websocket.send_text(json.dumps(error_data))
        except Exception:
            pass  # Connection might already be closed


# Global WebSocket handler instance
_cli_websocket_handler = None


def get_cli_websocket_handler() -> CLIWebSocketHandler:
    """Get the global CLI WebSocket handler instance."""
    global _cli_websocket_handler
    if _cli_websocket_handler is None:
        _cli_websocket_handler = CLIWebSocketHandler()
    return _cli_websocket_handler
