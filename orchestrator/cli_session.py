"""
CLI Session Management system with Redis persistence.

This module provides comprehensive session management for CLI tools including Claude,
Codex, Gemini, and Cursor. It handles session lifecycle, state transitions, history
tracking, recovery mechanisms, and Redis-based persistence.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any

from redis import Redis

from .models import Message, Session, SessionStatus
from .queue import _redis

logger = logging.getLogger(__name__)


class CLISessionError(Exception):
    """Base exception for CLI session operations."""

    pass


class SessionNotFoundError(CLISessionError):
    """Raised when a session is not found."""

    pass


class SessionStateError(CLISessionError):
    """Raised when an invalid state transition is attempted."""

    pass


class CLISessionManager:
    """
    Manages CLI sessions with Redis persistence, recovery, and monitoring.

    Features:
    - Session lifecycle management (create, update, terminate)
    - Redis persistence with TTL and key management
    - Session recovery after failures
    - History tracking with message storage
    - Metrics and monitoring integration
    - State transition validation
    """

    # Redis key patterns
    SESSION_KEY_PREFIX = "cli_session:"
    SESSION_INDEX_KEY = "cli_sessions:index"
    USER_SESSIONS_KEY_PREFIX = "cli_sessions:user:"
    PROVIDER_SESSIONS_KEY_PREFIX = "cli_sessions:provider:"

    # Session TTL (1 hour default, configurable)
    DEFAULT_TTL = 3600

    # Valid state transitions
    VALID_TRANSITIONS = {
        SessionStatus.INITIALIZING: [
            SessionStatus.READY,
            SessionStatus.ERROR,
            SessionStatus.TERMINATED,
        ],
        SessionStatus.READY: [
            SessionStatus.PROCESSING,
            SessionStatus.IDLE,
            SessionStatus.ERROR,
            SessionStatus.TERMINATED,
        ],
        SessionStatus.PROCESSING: [
            SessionStatus.READY,
            SessionStatus.IDLE,
            SessionStatus.ERROR,
            SessionStatus.TERMINATED,
        ],
        SessionStatus.IDLE: [
            SessionStatus.PROCESSING,
            SessionStatus.READY,
            SessionStatus.ERROR,
            SessionStatus.TERMINATED,
        ],
        SessionStatus.ERROR: [SessionStatus.READY, SessionStatus.TERMINATED],
        SessionStatus.TERMINATED: [],  # Terminal state
    }

    def __init__(self, redis_client: Redis | None = None, ttl: int = DEFAULT_TTL):
        """
        Initialize CLI Session Manager.

        Args:
            redis_client: Redis connection (uses shared connection if None)
            ttl: Session TTL in seconds
        """
        self.redis = redis_client or _redis
        self.ttl = ttl

        # Test Redis connection
        try:
            self.redis.ping()
            logger.info("CLI Session Manager initialized with Redis connection")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise CLISessionError(f"Redis connection failed: {e}")

    def create_session(
        self,
        provider: str,
        user_id: str = "default",
        working_directory: str | None = None,
        environment_vars: dict[str, str] | None = None,
        cli_arguments: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """
        Create a new CLI session.

        Args:
            provider: CLI provider name ("claude", "codex", "gemini", "cursor")
            user_id: User identifier
            working_directory: Session working directory
            environment_vars: Environment variables for the session
            cli_arguments: CLI arguments to use
            metadata: Additional session metadata

        Returns:
            Created session object

        Raises:
            CLISessionError: If session creation fails
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        session = Session(
            id=session_id,
            provider=provider,
            user_id=user_id,
            created_at=now,
            last_activity=now,
            status=SessionStatus.INITIALIZING,
            working_directory=working_directory or os.getcwd(),
            environment_vars=environment_vars or {},
            cli_arguments=cli_arguments or [],
            metadata=metadata or {},
        )

        try:
            # Store session in Redis
            self._store_session(session)

            # Add to indices
            self._add_to_indices(session)

            logger.info(f"Created CLI session {session_id} for provider {provider}")
            return session

        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            raise CLISessionError(f"Session creation failed: {e}")

    def get_session(self, session_id: str) -> Session | None:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session object if found, None otherwise
        """
        try:
            session_data = self.redis.get(self._session_key(session_id))
            if not session_data:
                return None

            data = json.loads(session_data.decode("utf-8"))
            return Session.parse_obj(data)

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    def update_session(self, session: Session) -> bool:
        """
        Update an existing session.

        Args:
            session: Updated session object

        Returns:
            True if successful, False otherwise
        """
        try:
            session.last_activity = datetime.utcnow()
            self._store_session(session)
            logger.debug(f"Updated session {session.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update session {session.id}: {e}")
            return False

    def update_session_status(
        self, session_id: str, new_status: SessionStatus, error_message: str | None = None
    ) -> bool:
        """
        Update session status with validation.

        Args:
            session_id: Session identifier
            new_status: New status to set
            error_message: Error message if status is ERROR

        Returns:
            True if successful, False otherwise

        Raises:
            SessionStateError: If invalid state transition
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for status update")
            return False

        # Validate state transition
        if new_status not in self.VALID_TRANSITIONS.get(session.status, []):
            raise SessionStateError(
                f"Invalid transition from {session.status} to {new_status} "
                f"for session {session_id}"
            )

        # Update session
        old_status = session.status
        session.status = new_status

        if new_status == SessionStatus.ERROR and error_message:
            session.last_error = error_message
            session.error_count += 1

        if new_status == SessionStatus.TERMINATED:
            # Add termination message to history
            self.add_message(
                session_id,
                Message(
                    type="system",
                    content=f"Session terminated from status {old_status}",
                    timestamp=datetime.utcnow(),
                    direction="output",
                ),
            )

        success = self.update_session(session)
        if success:
            logger.info(f"Session {session_id} status: {old_status} -> {new_status}")

        return success

    def add_message(self, session_id: str, message: Message) -> bool:
        """
        Add a message to session history.

        Args:
            session_id: Session identifier
            message: Message to add

        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for message add")
            return False

        try:
            # Add message to history
            session.history.append(message)

            # Update command count if it's an input command
            if message.direction == "input" and message.type == "command":
                session.command_count += 1

            # Limit history size (keep last 1000 messages)
            if len(session.history) > 1000:
                session.history = session.history[-1000:]

            return self.update_session(session)

        except Exception as e:
            logger.error(f"Failed to add message to session {session_id}: {e}")
            return False

    def get_session_history(
        self, session_id: str, limit: int | None = None, message_type: str | None = None
    ) -> list[Message]:
        """
        Get session message history.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            message_type: Filter by message type

        Returns:
            List of messages
        """
        session = self.get_session(session_id)
        if not session:
            return []

        messages = session.history

        # Filter by type if specified
        if message_type:
            messages = [msg for msg in messages if msg.type == message_type]

        # Apply limit
        if limit:
            messages = messages[-limit:]

        return messages

    def list_sessions(
        self,
        user_id: str | None = None,
        provider: str | None = None,
        status: SessionStatus | None = None,
        include_terminated: bool = False,
    ) -> list[Session]:
        """
        List sessions with optional filters.

        Args:
            user_id: Filter by user ID
            provider: Filter by provider
            status: Filter by status
            include_terminated: Include terminated sessions

        Returns:
            List of matching sessions
        """
        try:
            # Get all session IDs from index
            session_ids = self.redis.smembers(self.SESSION_INDEX_KEY)
            if not session_ids:
                return []

            sessions = []
            for session_id in session_ids:
                session = self.get_session(session_id.decode("utf-8"))
                if not session:
                    continue

                # Apply filters
                if user_id and session.user_id != user_id:
                    continue

                if provider and session.provider != provider:
                    continue

                if status and session.status != status:
                    continue

                if not include_terminated and session.status == SessionStatus.TERMINATED:
                    continue

                sessions.append(session)

            # Sort by creation time (newest first)
            sessions.sort(key=lambda s: s.created_at, reverse=True)
            return sessions

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    def terminate_session(self, session_id: str, reason: str = "Manual termination") -> bool:
        """
        Terminate a session.

        Args:
            session_id: Session identifier
            reason: Termination reason

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update status to terminated
            success = self.update_session_status(session_id, SessionStatus.TERMINATED)

            if success:
                # Add termination message
                self.add_message(
                    session_id,
                    Message(
                        type="system",
                        content=f"Session terminated: {reason}",
                        timestamp=datetime.utcnow(),
                        direction="output",
                    ),
                )

                logger.info(f"Terminated session {session_id}: {reason}")

            return success

        except Exception as e:
            logger.error(f"Failed to terminate session {session_id}: {e}")
            return False

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        try:
            cleaned_count = 0
            cutoff_time = datetime.utcnow() - timedelta(seconds=self.ttl)

            sessions = self.list_sessions(include_terminated=True)

            for session in sessions:
                # Check if session is expired
                if session.last_activity < cutoff_time:
                    if self.delete_session(session.id):
                        cleaned_count += 1

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired sessions")

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session completely.

        Args:
            session_id: Session identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove from Redis
            session_key = self._session_key(session_id)
            self.redis.delete(session_key)

            # Remove from indices
            self._remove_from_indices(session_id)

            logger.info(f"Deleted session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def recover_sessions(self) -> list[Session]:
        """
        Recover sessions that may have been interrupted.

        Returns:
            List of recovered sessions
        """
        try:
            recovered = []

            # Find sessions in non-terminal states
            sessions = self.list_sessions(include_terminated=False)

            for session in sessions:
                # Check if session needs recovery
                if self._needs_recovery(session):
                    # Update to ERROR status
                    self.update_session_status(
                        session.id, SessionStatus.ERROR, "Session recovered after interruption"
                    )
                    recovered.append(session)

            if recovered:
                logger.info(f"Recovered {len(recovered)} interrupted sessions")

            return recovered

        except Exception as e:
            logger.error(f"Failed to recover sessions: {e}")
            return []

    def get_session_metrics(self) -> dict[str, Any]:
        """
        Get session metrics for monitoring.

        Returns:
            Dictionary of metrics
        """
        try:
            sessions = self.list_sessions(include_terminated=True)

            # Count by status
            status_counts = {}
            for status in SessionStatus:
                status_counts[status.value] = 0

            # Count by provider
            provider_counts = {}

            # Calculate totals
            total_sessions = len(sessions)
            active_sessions = 0
            total_messages = 0
            total_commands = 0

            for session in sessions:
                # Status counts
                status_counts[session.status.value] += 1

                # Provider counts
                provider_counts[session.provider] = provider_counts.get(session.provider, 0) + 1

                # Active sessions
                if session.status not in [SessionStatus.TERMINATED, SessionStatus.ERROR]:
                    active_sessions += 1

                # Message and command counts
                total_messages += len(session.history)
                total_commands += session.command_count

            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "status_counts": status_counts,
                "provider_counts": provider_counts,
                "total_messages": total_messages,
                "total_commands": total_commands,
                "redis_keys": self.redis.dbsize(),
            }

        except Exception as e:
            logger.error(f"Failed to get session metrics: {e}")
            return {}

    # Private helper methods

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{self.SESSION_KEY_PREFIX}{session_id}"

    def _store_session(self, session: Session) -> None:
        """Store session in Redis with TTL."""
        session_key = self._session_key(session.id)
        session_data = session.json()

        # Store with TTL
        self.redis.setex(session_key, self.ttl, session_data)

    def _add_to_indices(self, session: Session) -> None:
        """Add session to various indices."""
        # Main index
        self.redis.sadd(self.SESSION_INDEX_KEY, session.id)
        self.redis.expire(self.SESSION_INDEX_KEY, self.ttl * 2)  # Index TTL longer than session TTL

        # User index
        user_key = f"{self.USER_SESSIONS_KEY_PREFIX}{session.user_id}"
        self.redis.sadd(user_key, session.id)
        self.redis.expire(user_key, self.ttl * 2)

        # Provider index
        provider_key = f"{self.PROVIDER_SESSIONS_KEY_PREFIX}{session.provider}"
        self.redis.sadd(provider_key, session.id)
        self.redis.expire(provider_key, self.ttl * 2)

    def _remove_from_indices(self, session_id: str) -> None:
        """Remove session from indices."""
        # Get session to find user and provider
        session = self.get_session(session_id)
        if session:
            # Remove from user index
            user_key = f"{self.USER_SESSIONS_KEY_PREFIX}{session.user_id}"
            self.redis.srem(user_key, session_id)

            # Remove from provider index
            provider_key = f"{self.PROVIDER_SESSIONS_KEY_PREFIX}{session.provider}"
            self.redis.srem(provider_key, session_id)

        # Remove from main index
        self.redis.srem(self.SESSION_INDEX_KEY, session_id)

    def _needs_recovery(self, session: Session) -> bool:
        """Check if session needs recovery."""
        # Sessions that have been inactive for more than 30 minutes might need recovery
        inactive_threshold = timedelta(minutes=30)
        return (datetime.utcnow() - session.last_activity) > inactive_threshold
