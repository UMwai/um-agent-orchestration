"""
Claude Session Pool Manager

Maintains a pool of authenticated Claude CLI sessions that can be reused
across multiple requests, avoiding repeated authentication.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from orchestrator.cli_session_manager import CLIProcessManager, CLISessionInfo, CLISessionState

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Status of a pooled session"""

    AVAILABLE = "available"
    IN_USE = "in_use"
    AUTHENTICATING = "authenticating"
    ERROR = "error"


@dataclass
class PooledSession:
    """Represents a pooled Claude session"""

    session_id: str
    process_manager: CLIProcessManager
    status: SessionStatus
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    current_user: str | None = None
    is_authenticated: bool = False
    authentication_checked: bool = False


class ClaudeSessionPool:
    """Manages a pool of reusable Claude CLI sessions"""

    def __init__(self, pool_size: int = 3, reauth_interval_hours: int = 12):
        """
        Initialize the session pool.

        Args:
            pool_size: Maximum number of sessions to maintain
            reauth_interval_hours: Hours before requiring re-authentication check
        """
        self.pool_size = pool_size
        self.reauth_interval = timedelta(hours=reauth_interval_hours)
        self.sessions: dict[str, PooledSession] = {}
        self.lock = asyncio.Lock()
        self._master_session: PooledSession | None = None
        self._initialization_complete = False

    async def initialize(self):
        """Initialize the pool with a master authenticated session"""
        if self._initialization_complete:
            return

        async with self.lock:
            if self._initialization_complete:
                return

            logger.info("Initializing Claude session pool...")

            # Create and authenticate the master session
            master_session = await self._create_master_session()
            if master_session and master_session.is_authenticated:
                self._master_session = master_session
                self.sessions[master_session.session_id] = master_session
                logger.info(f"Master Claude session created: {master_session.session_id}")
            else:
                logger.warning("Failed to create authenticated master session")

            self._initialization_complete = True

    async def _create_master_session(self) -> PooledSession | None:
        """Create and authenticate the master Claude session"""
        try:
            # Create session info
            session_id = f"claude-master-{int(time.time())}"
            session_info = CLISessionInfo(
                session_id=session_id,
                cli_tool="claude",
                mode="cli",
                state=CLISessionState.INITIALIZING,
                current_directory=os.getcwd(),
            )

            # Create process manager
            process_manager = CLIProcessManager(session_info, self._output_callback)

            # Build command - use existing authenticated session
            command = ["claude", "--dangerously-skip-permissions"]
            env = os.environ.copy()

            # Ensure we use the existing Claude authentication
            env["HOME"] = os.path.expanduser("~")
            env["CLAUDE_CONFIG_DIR"] = os.path.expanduser("~/.claude")

            # Start the process
            await process_manager.start_process(command, env)

            # Wait for it to be ready
            await asyncio.sleep(2)  # Give it time to initialize

            # Check if authenticated by sending a test command
            is_auth = await self._check_authentication(process_manager)

            pooled_session = PooledSession(
                session_id=session_id,
                process_manager=process_manager,
                status=SessionStatus.AVAILABLE if is_auth else SessionStatus.ERROR,
                created_at=datetime.now(),
                last_used=datetime.now(),
                is_authenticated=is_auth,
                authentication_checked=True,
            )

            return pooled_session

        except Exception as e:
            logger.error(f"Failed to create master session: {e}")
            return None

    async def _check_authentication(self, process_manager: CLIProcessManager) -> bool:
        """Check if a session is authenticated"""
        try:
            # Send a simple test command
            test_response_received = asyncio.Event()
            test_response = {"authenticated": False}

            def check_response(session_id: str, data: dict):
                if data.get("type") == "output":
                    content = data.get("content", "").lower()
                    # If we get a real response (not auth prompt), we're authenticated
                    if "login" not in content and "authenticate" not in content:
                        test_response["authenticated"] = True
                test_response_received.set()

            # Temporarily set callback
            original_callback = process_manager.output_callback
            process_manager.output_callback = check_response

            # Send test
            await process_manager.send_input("echo test", add_newline=True)

            # Wait for response
            try:
                await asyncio.wait_for(test_response_received.wait(), timeout=5.0)
            except TimeoutError:
                pass

            # Restore callback
            process_manager.output_callback = original_callback

            return test_response["authenticated"]

        except Exception as e:
            logger.error(f"Authentication check failed: {e}")
            return False

    async def get_session(self, user_id: str = "default") -> PooledSession | None:
        """
        Get an available session from the pool.

        Args:
            user_id: ID of the user requesting the session

        Returns:
            An available session or None if none available
        """
        await self.initialize()

        async with self.lock:
            # First, try to use the master session if available
            if self._master_session and self._master_session.status == SessionStatus.AVAILABLE:
                self._master_session.status = SessionStatus.IN_USE
                self._master_session.current_user = user_id
                self._master_session.last_used = datetime.now()
                self._master_session.use_count += 1
                logger.info(
                    f"Assigning master session {self._master_session.session_id} to user {user_id}"
                )
                return self._master_session

            # Look for any available session
            for session in self.sessions.values():
                if session.status == SessionStatus.AVAILABLE and session.is_authenticated:
                    session.status = SessionStatus.IN_USE
                    session.current_user = user_id
                    session.last_used = datetime.now()
                    session.use_count += 1
                    logger.info(f"Assigning session {session.session_id} to user {user_id}")
                    return session

            # No available sessions
            logger.warning(f"No available sessions for user {user_id}")
            return None

    async def release_session(self, session_id: str):
        """
        Release a session back to the pool.

        Args:
            session_id: ID of the session to release
        """
        async with self.lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.status = SessionStatus.AVAILABLE
                session.current_user = None
                logger.info(f"Released session {session_id} back to pool")

    async def send_to_session(self, session_id: str, input_text: str) -> bool:
        """
        Send input to a specific session.

        Args:
            session_id: ID of the session
            input_text: Text to send

        Returns:
            True if successful, False otherwise
        """
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found in pool")
            return False

        session = self.sessions[session_id]
        if session.status != SessionStatus.IN_USE:
            logger.error(f"Session {session_id} is not in use")
            return False

        try:
            await session.process_manager.send_input(input_text, add_newline=True)
            return True
        except Exception as e:
            logger.error(f"Failed to send to session {session_id}: {e}")
            return False

    def _output_callback(self, session_id: str, data: dict):
        """Default output callback for pooled sessions"""
        logger.debug(f"Session {session_id} output: {data}")

    async def cleanup(self):
        """Clean up all sessions in the pool"""
        async with self.lock:
            for session in self.sessions.values():
                try:
                    await session.process_manager.terminate()
                except Exception as e:
                    logger.error(f"Failed to terminate session {session.session_id}: {e}")
            self.sessions.clear()
            self._master_session = None
            self._initialization_complete = False


# Global instance
_session_pool: ClaudeSessionPool | None = None


def get_session_pool() -> ClaudeSessionPool:
    """Get the global Claude session pool instance"""
    global _session_pool
    if _session_pool is None:
        _session_pool = ClaudeSessionPool()
    return _session_pool


async def initialize_session_pool():
    """Initialize the global session pool"""
    pool = get_session_pool()
    await pool.initialize()
