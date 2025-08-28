"""
CLI Session Manager for real-time CLI process management and WebSocket streaming.
Handles spawning, managing, and streaming output from actual CLI processes with Redis persistence.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pty
import select
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .cli_session import CLISessionManager as PersistentCLISessionManager
from .models import Message, Session

# Set up logging
logger = logging.getLogger(__name__)


class CLISessionState(Enum):
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class CLISessionInfo:
    session_id: str
    cli_tool: str  # claude, codex, gemini, cursor
    mode: str  # cli, interactive, api
    state: CLISessionState
    pid: int | None = None
    created_at: float = 0.0
    last_activity: float = 0.0
    command_history: list[str] = None
    current_directory: str = ""
    authentication_required: bool = False
    auth_prompt: str | None = None

    def __post_init__(self):
        if self.command_history is None:
            self.command_history = []
        if not self.current_directory:
            self.current_directory = os.getcwd()
        if not self.created_at:
            self.created_at = time.time()
        if not self.last_activity:
            self.last_activity = time.time()


class CLIProcessManager:
    """Manages a single CLI process with real-time I/O streaming."""

    def __init__(self, session_info: CLISessionInfo, output_callback: Callable[[str, str], None]):
        self.session_info = session_info
        self.output_callback = output_callback  # callback(session_id, output)
        self.process: subprocess.Popen | None = None
        self.pty_master: int | None = None
        self.pty_slave: int | None = None
        self.output_thread: threading.Thread | None = None
        self.running = False
        self.prompt_ready = asyncio.Event()
        self.current_output_buffer = ""
        self.response_ready = asyncio.Event()
        self.last_prompt_time = 0

    async def start_process(self, command: list[str], env: dict[str, str] = None):
        """Start a persistent CLI process using PTY for real-time interaction."""
        try:
            logger.info(
                f"Starting persistent CLI session {self.session_info.session_id} for tool: {self.session_info.cli_tool}"
            )
            self.session_info.state = CLISessionState.STARTING

            # Create PTY pair for interactive communication
            self.pty_master, self.pty_slave = pty.openpty()

            # Start the CLI process with PTY
            self.process = subprocess.Popen(
                command,
                stdin=self.pty_slave,
                stdout=self.pty_slave,
                stderr=self.pty_slave,
                env=env,
                cwd=self.session_info.current_directory,
                preexec_fn=os.setsid,  # Create new process group
            )

            # Close slave fd in parent process
            os.close(self.pty_slave)
            self.pty_slave = None

            # Start output reading thread
            self.running = True
            self.output_thread = threading.Thread(target=self._read_output, daemon=True)
            self.output_thread.start()

            # Wait for initial prompt with shorter timeout since we improved detection
            try:
                await asyncio.wait_for(self.prompt_ready.wait(), timeout=15.0)
                self.session_info.state = CLISessionState.RUNNING
                logger.info(f"CLI session {self.session_info.session_id} is ready for commands")

                # Send welcome message
                tool_name = self.session_info.cli_tool.title()
                welcome_msg = f"\n🤖 {tool_name} interactive session ready\n\nResponse time should be under 2 seconds per message.\n\nTry: 'Hello!' or ask me anything.\n\n"
                await self._send_output(welcome_msg, "stdout")

            except TimeoutError:
                logger.warning(
                    f"CLI session {self.session_info.session_id} did not become ready within 15 seconds"
                )

                # For Claude, check if we have any interface indicators even without full detection
                if self.session_info.cli_tool == "claude":
                    buffer_check = (
                        self.current_output_buffer[-1000:]
                        if len(self.current_output_buffer) > 1000
                        else self.current_output_buffer
                    )
                    if (
                        "Welcome to Claude Code!" in buffer_check
                        and len(self.current_output_buffer) > 200
                    ):
                        logger.info(
                            f"Claude interface detected in buffer, proceeding anyway for session {self.session_info.session_id}"
                        )
                        self.session_info.state = CLISessionState.RUNNING
                        await self._send_output(
                            "Claude interface detected - ready to proceed", "stdout"
                        )
                        return  # Don't raise exception

                # Check if process is still running - if so, continue anyway
                if self.process and self.process.poll() is None:
                    logger.info(
                        f"CLI process is still running for session {self.session_info.session_id}, setting to running state anyway"
                    )
                    self.session_info.state = CLISessionState.RUNNING
                    await self._send_output(
                        "CLI started but prompt not fully detected - continuing anyway", "stdout"
                    )
                else:
                    self.session_info.state = CLISessionState.ERROR
                    await self._send_output(
                        "CLI process failed to start properly (timeout waiting for prompt)", "error"
                    )
                    raise Exception("CLI process initialization timeout")

            # Send initial status
            await self._send_status_update()

        except Exception as e:
            logger.error(
                f"Error starting CLI session {self.session_info.session_id}: {e}", exc_info=True
            )
            self.session_info.state = CLISessionState.ERROR
            await self._send_output(f"Error starting CLI session: {e}", "error")
            await self._cleanup_process()
            raise

    def _read_output(self):
        """Read output from PTY in separate thread with prompt detection."""
        logger.info(f"Starting output reading thread for session {self.session_info.session_id}")

        while self.running and self.pty_master:
            try:
                # Use select to check for available data with short timeout
                ready, _, _ = select.select([self.pty_master], [], [], 0.1)
                if ready:
                    data = os.read(self.pty_master, 4096)  # Larger buffer for better performance
                    if data:
                        output = data.decode("utf-8", errors="replace")
                        logger.debug(
                            f"Session {self.session_info.session_id} received: {output[:200]!r}..."
                        )

                        # Add to output buffer for prompt detection
                        self.current_output_buffer += output

                        # Check for prompt patterns to know when CLI is ready
                        if self._detect_prompt_ready(output):
                            if not self.prompt_ready.is_set():
                                logger.info(
                                    f"Session {self.session_info.session_id}: Detected CLI prompt ready"
                                )
                                self.prompt_ready.set()

                            # Signal response completion for interactive commands
                            if self.session_info.state == CLISessionState.PROCESSING:
                                logger.info(
                                    f"Session {self.session_info.session_id}: Command processing complete"
                                )
                                self.session_info.state = CLISessionState.RUNNING
                                self.response_ready.set()

                        # Enhanced response detection for Claude - look for response completion patterns
                        elif (
                            self.session_info.cli_tool == "claude"
                            and self.session_info.state == CLISessionState.PROCESSING
                        ):
                            # Claude response is complete when we see the cursor indicator and interface is ready again
                            if "◯" in output:  # Primary completion indicator
                                logger.info(
                                    f"Session {self.session_info.session_id}: Claude response completion detected (cursor)"
                                )
                                self.session_info.state = CLISessionState.RUNNING
                                self.response_ready.set()
                            elif "⏵⏵ bypass permissions on" in output:  # Status line ready
                                logger.info(
                                    f"Session {self.session_info.session_id}: Claude response completion detected (status)"
                                )
                                self.session_info.state = CLISessionState.RUNNING
                                self.response_ready.set()
                            elif "│" in output and (
                                ">" in output or len(output.strip()) == 0
                            ):  # Interface with input ready
                                # Check if this looks like the end of a response (empty line after interface)
                                lines = output.split("\n")
                                if len(lines) > 1 and any(
                                    "│" in line and ">" in line for line in lines[-3:]
                                ):
                                    logger.info(
                                        f"Session {self.session_info.session_id}: Claude response completion detected (interface ready)"
                                    )
                                    self.session_info.state = CLISessionState.RUNNING
                                    self.response_ready.set()

                        # Detect authentication patterns
                        self._detect_auth_patterns(output)

                        # Send output to callback asynchronously
                        self._schedule_output_callback(output, "stdout")
                        self.session_info.last_activity = time.time()

            except (OSError, ValueError) as e:
                if self.running:  # Only log if we expect it to be running
                    logger.error(f"Session {self.session_info.session_id}: PTY read error: {e}")
                    self._schedule_output_callback(f"PTY read error: {e}", "error")
                break
            except Exception as e:
                logger.error(
                    f"Session {self.session_info.session_id}: Unexpected error in output thread: {e}"
                )
                self._schedule_output_callback(f"Unexpected error: {e}", "error")

        logger.info(f"Output reading thread for session {self.session_info.session_id} terminated")

    def _detect_prompt_ready(self, output: str) -> bool:
        """Detect if CLI prompt is ready for next command."""
        # Claude CLI uses a complex TUI interface, so we need to look for specific patterns
        if self.session_info.cli_tool == "claude":
            # Look for the cursor position indicator that shows Claude is ready
            if "◯" in output:  # The circular cursor indicator
                logger.info(
                    f"Session {self.session_info.session_id}: Detected Claude ready indicator ◯"
                )
                return True

            # Look for bypass permissions indicator - this shows Claude is ready
            if "⏵⏵ bypass permissions on" in output:
                logger.info(
                    f"Session {self.session_info.session_id}: Detected bypass permissions indicator"
                )
                return True

            # Look for the input box border patterns with proper escape sequence handling
            if ("╭─" in output and "│" in output and ">" in output) or (
                "╭──────────────────" in output and ">" in output
            ):
                logger.info(
                    f"Session {self.session_info.session_id}: Detected Claude input box ready"
                )
                return True

            # Welcome screen with complete interface
            if "Welcome to Claude Code!" in output and ("╰─" in output or "│" in output):
                # Need to check if the full interface is ready, not just welcome
                buffer_check = (
                    self.current_output_buffer[-1000:]
                    if len(self.current_output_buffer) > 1000
                    else self.current_output_buffer
                )
                if (
                    "bypass permissions on" in buffer_check
                    or "◯" in buffer_check
                    or (
                        "╭─" in buffer_check
                        and "│" in buffer_check
                        and (">" in buffer_check or "⏵⏵" in buffer_check)
                    )
                ):
                    logger.info(
                        f"Session {self.session_info.session_id}: Detected Claude welcome screen complete"
                    )
                    return True

        elif self.session_info.cli_tool == "codex":
            # Codex prompt patterns
            if "codex>" in output or "codex$" in output:
                return True
            if "Ready for commands" in output or "What can I help" in output:
                return True

        elif self.session_info.cli_tool == "bash":
            # Bash prompt patterns
            if output.strip().endswith("$ ") or output.strip().endswith("$"):
                return True

        elif self.session_info.cli_tool == "mock":
            # Mock CLI patterns
            if "Mock CLI ready for commands!" in output:
                return True

        # Look at the last portion of the buffer for general patterns
        lines = self.current_output_buffer.split("\n")
        recent_lines = lines[-10:]  # Check more lines for better detection

        for line in recent_lines:
            line_clean = line.strip()
            # Generic prompt patterns
            if line_clean.endswith("$ ") or line_clean.endswith("$") or line_clean.endswith("> "):
                return True
            if "Ready" in line_clean and (">" in line_clean or "$" in line_clean):
                return True
            # Mock CLI ready
            if "Mock CLI ready" in line_clean:
                return True

        # Enhanced buffer check for Claude - check larger buffer for stability
        if self.session_info.cli_tool == "claude":
            buffer_end = (
                self.current_output_buffer[-1000:]
                if len(self.current_output_buffer) > 1000
                else self.current_output_buffer
            )

            # Check for multiple patterns that indicate ready state
            has_bypass = "bypass permissions on" in buffer_end
            has_cursor = "◯" in buffer_end
            has_box = "│" in buffer_end and (">" in buffer_end or "⏵⏵" in buffer_end)
            has_welcome = "Welcome to Claude Code!" in buffer_end

            # Claude is ready if we have the bypass indicator OR cursor with interface
            if has_bypass and (has_cursor or has_box):
                logger.info(
                    f"Session {self.session_info.session_id}: Detected Claude ready via buffer check (bypass+cursor/box)"
                )
                return True
            elif (
                has_welcome and has_box and len(self.current_output_buffer) > 500
            ):  # Interface should be substantial
                logger.info(
                    f"Session {self.session_info.session_id}: Detected Claude ready via buffer check (welcome+box)"
                )
                return True

        return False

    def _detect_auth_patterns(self, output: str):
        """Detect authentication requirements and handle automatic authentication."""
        output_lower = output.lower()

        # Claude CLI specific patterns
        if self.session_info.cli_tool == "claude":
            # Detect login requirement and handle automatically
            if any(
                pattern in output_lower
                for pattern in [
                    "select login method",
                    "claude code can now be used",
                    "api key",
                    "anthropic_api_key",
                    "authentication required",
                    "please authenticate",
                    "login required",
                    "browser to authenticate",
                ]
            ):
                logger.info(
                    f"Session {self.session_info.session_id}: Claude authentication required detected"
                )

                # Try to handle authentication automatically if credentials exist
                if self._attempt_auto_authentication():
                    logger.info(
                        f"Session {self.session_info.session_id}: Attempting automatic Claude authentication"
                    )
                    self.session_info.state = CLISessionState.PROCESSING
                else:
                    self.session_info.state = CLISessionState.WAITING_INPUT
                    self.session_info.authentication_required = True
                    self.session_info.auth_prompt = "Claude authentication required"

            elif any(
                pattern in output_lower
                for pattern in [
                    "claude code is ready",
                    "logged in successfully",
                    "authentication successful",
                    "welcome to claude code",  # This indicates successful auth
                ]
            ):
                logger.info(
                    f"Session {self.session_info.session_id}: Claude authentication successful"
                )
                self.session_info.state = CLISessionState.RUNNING
                self.session_info.authentication_required = False

        # Codex CLI specific patterns
        elif self.session_info.cli_tool == "codex":
            if any(
                pattern in output_lower
                for pattern in [
                    "api key",
                    "openai_api_key",
                    "please login",
                    "authentication required",
                    "token required",
                ]
            ):
                self.session_info.state = CLISessionState.WAITING_INPUT
                self.session_info.authentication_required = True
                self.session_info.auth_prompt = "OpenAI API key required"
            elif any(
                pattern in output_lower
                for pattern in ["ready for commands", "logged in", "authenticated"]
            ):
                self.session_info.state = CLISessionState.RUNNING
                self.session_info.authentication_required = False

        # General auth patterns
        elif any(
            keyword in output_lower
            for keyword in [
                "password:",
                "login:",
                "authenticate",
                "api key required",
                "token:",
                "please enter",
                "credentials required",
            ]
        ):
            self.session_info.state = CLISessionState.WAITING_INPUT
            self.session_info.authentication_required = True
            self.session_info.auth_prompt = output.strip()

    def _schedule_output_callback(self, output: str, output_type: str):
        """Schedule output callback in thread-safe manner."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self._send_output(output, output_type), loop)
            else:
                asyncio.run(self._send_output(output, output_type))
        except RuntimeError:
            try:
                asyncio.run(self._send_output(output, output_type))
            except Exception as e:
                logger.error(f"Failed to send output callback: {e}")

    async def send_input(self, text: str, add_newline: bool = True):
        """Send input to the persistent CLI process via PTY."""
        logger.info(
            f"Session {self.session_info.session_id}: Sending input to persistent CLI: {text[:50]!r}..."
        )

        if not self.running or not self.pty_master or not self.process:
            logger.error(f"Session {self.session_info.session_id}: CLI process not running")
            await self._send_output("CLI process not running", "error")
            return

        try:
            self.session_info.state = CLISessionState.PROCESSING

            # Add to command history
            if text.strip():
                self.session_info.command_history.append(text.strip())

            # Clear response ready event
            self.response_ready.clear()

            # Send input to PTY - different approaches for different CLI tools
            if self.session_info.cli_tool == "claude":
                # For Claude CLI, we need to type the text directly into the interface
                # No need to clear first - Claude's interface handles overwrites

                # Send the text character by character for better compatibility
                for char in text:
                    os.write(self.pty_master, char.encode("utf-8"))
                    await asyncio.sleep(0.01)  # Small delay between characters

                # Send Enter to submit the message
                await asyncio.sleep(0.1)
                os.write(self.pty_master, b"\r")

            else:
                # For other CLI tools, use standard input with newline
                input_text = text
                if add_newline and not input_text.endswith("\n"):
                    input_text += "\n"
                os.write(self.pty_master, input_text.encode("utf-8"))

            logger.debug(
                f"Session {self.session_info.session_id}: Sent input to {self.session_info.cli_tool}"
            )

            # Wait for response completion with timeout
            try:
                await asyncio.wait_for(
                    self.response_ready.wait(), timeout=120.0
                )  # 2 minute timeout
                logger.info(
                    f"Session {self.session_info.session_id}: Command completed successfully"
                )
            except TimeoutError:
                logger.warning(f"Session {self.session_info.session_id}: Command response timeout")
                self.session_info.state = CLISessionState.RUNNING  # Reset to running state
                await self._send_output(
                    "\n[Response timeout - CLI may still be processing]\n", "stderr"
                )

        except (OSError, ValueError) as e:
            logger.error(f"Session {self.session_info.session_id}: PTY write error: {e}")
            self.session_info.state = CLISessionState.ERROR
            await self._send_output(f"PTY write error: {e}", "error")
        except Exception as e:
            logger.error(
                f"Session {self.session_info.session_id}: Error sending input: {e}", exc_info=True
            )
            self.session_info.state = CLISessionState.ERROR
            await self._send_output(f"Error sending input: {e}", "error")

    async def _cleanup_process(self):
        """Clean up process and PTY resources."""
        try:
            if self.process and self.process.poll() is None:
                # Try graceful termination first
                self.process.terminate()
                try:
                    await asyncio.wait_for(asyncio.to_thread(self.process.wait), timeout=5.0)
                except TimeoutError:
                    # Force kill if graceful termination fails
                    self.process.kill()
                    await asyncio.to_thread(self.process.wait)

            if self.pty_master:
                os.close(self.pty_master)
                self.pty_master = None

            if self.pty_slave:
                os.close(self.pty_slave)
                self.pty_slave = None

        except Exception as e:
            logger.error(f"Session {self.session_info.session_id}: Error cleaning up process: {e}")

    async def terminate(self):
        """Terminate the CLI session and cleanup resources."""
        logger.info(f"Terminating CLI session {self.session_info.session_id}")
        self.running = False
        self.session_info.state = CLISessionState.TERMINATED

        # Clean up process and PTY resources
        await self._cleanup_process()

        # Wait for output thread to finish
        if self.output_thread and self.output_thread.is_alive():
            self.output_thread.join(timeout=5.0)

        await self._send_status_update()

    async def send_interrupt(self) -> bool:
        """Send an interrupt (Ctrl+C) to the CLI process.

        Attempts both a PTY Ctrl-C (\x03) and a SIGINT to the process group.
        """
        if not self.running or not self.process:
            await self._send_output("CLI process not running", "error")
            return False
        try:
            # Send Ctrl-C via PTY if available
            if self.pty_master:
                try:
                    os.write(self.pty_master, b"\x03")
                except Exception:
                    pass
            # Send SIGINT to the process group
            try:
                pgid = os.getpgid(self.process.pid)
                os.killpg(pgid, signal.SIGINT)
            except Exception:
                pass
            await self._send_output("\n[Interrupt signal sent]\n", "stderr")
            return True
        except Exception as e:
            await self._send_output(f"Error sending interrupt: {e}", "error")
            return False

    async def _send_output(self, output: str, output_type: str):
        """Send output through callback."""
        if self.output_callback:
            try:
                logger.debug(
                    f"Session {self.session_info.session_id}: Sending output via callback: {output_type} - {len(output)} chars"
                )
                self.output_callback(
                    self.session_info.session_id,
                    {
                        "type": "output",
                        "output_type": output_type,
                        "content": output,
                        "timestamp": time.time(),
                    },
                )
            except Exception as e:
                logger.error(
                    f"Session {self.session_info.session_id}: Output callback error: {e}",
                    exc_info=True,
                )

    def _attempt_auto_authentication(self) -> bool:
        """Check if automatic authentication is possible for Claude."""
        if self.session_info.cli_tool != "claude":
            return False

        # Check if Claude credentials exist
        import os

        credentials_path = os.path.expanduser("~/.claude/.credentials.json")
        if os.path.exists(credentials_path):
            try:
                with open(credentials_path) as f:
                    credentials = json.load(f)

                # Check if OAuth token exists and is not expired
                oauth_data = credentials.get("claudeAiOauth", {})
                access_token = oauth_data.get("accessToken")
                expires_at = oauth_data.get("expiresAt", 0)

                if (
                    access_token and expires_at > time.time() * 1000
                ):  # expires_at is in milliseconds
                    logger.info(
                        f"Session {self.session_info.session_id}: Found valid Claude credentials"
                    )
                    return True
                else:
                    logger.warning(
                        f"Session {self.session_info.session_id}: Claude credentials expired or invalid"
                    )

            except Exception as e:
                logger.error(
                    f"Session {self.session_info.session_id}: Error reading Claude credentials: {e}"
                )
        else:
            logger.warning(
                f"Session {self.session_info.session_id}: No Claude credentials file found"
            )

        return False

    async def _send_status_update(self):
        """Send status update through callback."""
        if self.output_callback:
            try:
                self.output_callback(
                    self.session_info.session_id,
                    {
                        "type": "status",
                        "session": asdict(self.session_info),
                        "timestamp": time.time(),
                    },
                )
            except Exception:
                pass


class CLISessionManager:
    """Manages multiple CLI sessions with WebSocket integration and Redis persistence."""

    def __init__(self):
        self.sessions: dict[str, CLIProcessManager] = {}
        self.session_info: dict[str, CLISessionInfo] = {}
        self.websocket_callbacks: dict[str, Callable] = {}

        # Store reference to the main event loop for thread-safe async operations
        self.main_loop = None  # Will be set by set_main_loop() when FastAPI starts

        # Initialize persistence manager
        self.persistence = PersistentCLISessionManager()

    def register_websocket_callback(self, session_id: str, callback: Callable):
        """Register WebSocket callback for session updates."""
        self.websocket_callbacks[session_id] = callback

    def unregister_websocket_callback(self, session_id: str):
        """Unregister WebSocket callback."""
        self.websocket_callbacks.pop(session_id, None)

    async def create_session(
        self,
        cli_tool: str,
        mode: str = "cli",
        cwd: str = None,
        user_id: str = "default",
        start_immediately: bool = True,
    ) -> str:
        """Create a new CLI session with Redis persistence."""
        # Create persistent session first
        persistent_session = self.persistence.create_session(
            provider=cli_tool,
            user_id=user_id,
            working_directory=cwd or os.getcwd(),
            metadata={"mode": mode, "cli_tool": cli_tool},
        )

        # Use the persistent session ID for consistency
        session_id = persistent_session.id

        session_info = CLISessionInfo(
            session_id=session_id,
            cli_tool=cli_tool,
            mode=mode,
            state=CLISessionState.INITIALIZING,
            current_directory=cwd or os.getcwd(),
        )

        # Enhanced output callback with Redis persistence (simplified for performance)
        def output_callback(sid: str, data: dict):
            # Store in Redis persistence
            try:
                if data.get("type") == "output":
                    message = Message(
                        type=data.get("output_type", "stdout"),
                        content=data.get("content", ""),
                        timestamp=datetime.utcnow(),
                        direction="output",
                        metadata={"websocket_data": data},
                    )
                    self.persistence.add_message(sid, message)
            except Exception:
                # Don't let persistence errors break the session
                pass

        process_manager = CLIProcessManager(session_info, output_callback)

        self.sessions[session_id] = process_manager
        self.session_info[session_id] = session_info

        return session_id

    async def start_cli_process(self, session_id: str, full_access: bool = False) -> bool:
        """Start the actual CLI process for a session."""
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found in sessions dict")
            return False

        session = self.sessions[session_id]
        info = self.session_info[session_id]

        # Build command based on CLI tool and mode
        command = self._build_cli_command(info.cli_tool, info.mode, full_access)
        logger.info(f"Session {session_id}: Built command: {' '.join(command)}")

        # Set up environment
        env = self._get_cli_environment(info.cli_tool, full_access)
        logger.debug(f"Session {session_id}: Environment has {len(env)} variables")

        try:
            await session.start_process(command, env)
            logger.info(f"Session {session_id}: CLI process started successfully")
            return True
        except Exception as e:
            logger.error(f"Session {session_id}: Failed to start CLI process: {e}", exc_info=True)
            return False

    def _build_cli_command(self, cli_tool: str, mode: str, full_access: bool) -> list[str]:
        """Build the CLI command based on tool and configuration."""

        if cli_tool == "claude":
            if full_access:
                return ["claude", "--dangerously-skip-permissions"]
            else:
                return ["claude"]

        elif cli_tool == "codex":
            if full_access:
                return [
                    "codex",
                    "--ask-for-approval",
                    "never",
                    "--sandbox",
                    "danger-full-access",
                    "exec",
                ]
            else:
                return ["codex", "exec"]

        elif cli_tool == "gemini":
            if full_access:
                return ["gemini", "--interactive", "--full-access"]
            else:
                return ["gemini", "--interactive"]

        elif cli_tool == "cursor":
            if full_access:
                return ["cursor-agent", "--full-access", "--auto-approve"]
            else:
                return ["cursor-agent"]

        elif cli_tool == "bash":
            # Simple bash for testing PTY functionality
            return ["bash"]

        elif cli_tool == "mock":
            # Mock CLI for testing - uses python to simulate a CLI
            return [
                "python3",
                "-c",
                """
import sys
import time
print('Mock CLI ready for commands!')
sys.stdout.flush()
while True:
    try:
        line = input()
        print(f'Mock response to: {line}')
        sys.stdout.flush()
    except (EOFError, KeyboardInterrupt):
        break
""",
            ]

        # Fallback for unknown CLI tools - assume interactive mode
        return [cli_tool, "--interactive"]

    def _get_cli_environment(self, cli_tool: str, full_access: bool) -> dict[str, str]:
        """Get environment variables for CLI tool with proper authentication inheritance."""
        # Start with a COPY of the current environment to inherit authentication
        env = os.environ.copy()

        # Ensure HOME and USER are properly set for CLI config access
        env["HOME"] = os.path.expanduser("~")
        env["USER"] = os.getenv("USER", "")

        # Remove placeholder API keys that interfere with CLI authentication
        # Only keep them if they're real (not 'replace_me')
        if cli_tool == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if api_key == "replace_me" or not api_key:
                # Remove to let Claude use its own auth
                env.pop("ANTHROPIC_API_KEY", None)
            # Ensure Claude can access its config directory
            claude_config_dir = os.path.expanduser("~/.claude")
            if os.path.exists(claude_config_dir):
                env["CLAUDE_CONFIG_DIR"] = claude_config_dir

        elif cli_tool == "codex":
            api_key = os.getenv("OPENAI_API_KEY", "")
            if api_key == "replace_me" or not api_key:
                # Remove to let Codex use its own auth
                env.pop("OPENAI_API_KEY", None)
            # Ensure Codex can access its config directory
            codex_config_dir = os.path.expanduser("~/.codex")
            if os.path.exists(codex_config_dir):
                env["CODEX_CONFIG_DIR"] = codex_config_dir

        elif cli_tool == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY", "")
            if api_key == "replace_me" or not api_key:
                env.pop("GOOGLE_API_KEY", None)
                env.pop("GOOGLE_GENAI_API_KEY", None)

        # Add repository context
        env["REPO_ROOT"] = os.getcwd()

        # Ensure the CLI knows it's in an interactive session if needed
        if full_access:
            env["CLI_FULL_ACCESS"] = "1"

        # Pass terminal type for proper CLI behavior
        if "TERM" not in env:
            env["TERM"] = "xterm-256color"

        return env

    async def send_input_to_session(self, session_id: str, input_text: str) -> bool:
        """Send input to a CLI session with persistence."""
        if session_id not in self.sessions:
            return False

        try:
            # Store input message in persistence
            message = Message(
                type="command", content=input_text, timestamp=datetime.utcnow(), direction="input"
            )
            self.persistence.add_message(session_id, message)

            # Send to CLI process
            await self.sessions[session_id].send_input(input_text)
            return True
        except Exception:
            return False

    async def terminate_session(self, session_id: str, reason: str = "Manual termination") -> bool:
        """Terminate a CLI session with persistence update."""
        if session_id not in self.sessions:
            return False

        try:
            # Update persistence
            self.persistence.terminate_session(session_id, reason)

            # Terminate CLI process
            await self.sessions[session_id].terminate()

            # Cleanup
            del self.sessions[session_id]
            del self.session_info[session_id]
            self.websocket_callbacks.pop(session_id, None)

            return True
        except Exception:
            return False

    async def interrupt_session(self, session_id: str) -> bool:
        """Send interrupt (Ctrl+C) to a running CLI session."""
        if session_id not in self.sessions:
            return False
        try:
            return await self.sessions[session_id].send_interrupt()
        except Exception:
            return False

    def get_session_info(self, session_id: str) -> CLISessionInfo | None:
        """Get information about a CLI session."""
        return self.session_info.get(session_id)

    def list_sessions(self) -> list[CLISessionInfo]:
        """List all active CLI sessions."""
        return list(self.session_info.values())

    async def cleanup_inactive_sessions(self, max_age: int = 3600):
        """Clean up sessions that have been inactive for too long."""
        current_time = time.time()
        to_cleanup = []

        for session_id, info in self.session_info.items():
            if current_time - info.last_activity > max_age:
                to_cleanup.append(session_id)

        for session_id in to_cleanup:
            await self.terminate_session(session_id, "Inactive session cleanup")

        # Also cleanup expired sessions from Redis persistence
        self.persistence.cleanup_expired_sessions()

    async def recover_sessions(self) -> list[str]:
        """Recover sessions from Redis persistence after restart."""
        try:
            recovered_session_ids = []

            # Get persistent sessions that were interrupted
            persistent_sessions = self.persistence.recover_sessions()

            for persistent_session in persistent_sessions:
                session_id = persistent_session.id

                # Create CLISessionInfo from persistent session
                session_info = CLISessionInfo(
                    session_id=session_id,
                    cli_tool=persistent_session.provider,
                    mode=persistent_session.metadata.get("mode", "cli"),
                    state=CLISessionState.ERROR,  # Mark as error until recovery
                    current_directory=persistent_session.working_directory or os.getcwd(),
                )

                # Add to in-memory tracking
                self.session_info[session_id] = session_info
                recovered_session_ids.append(session_id)

            return recovered_session_ids

        except Exception:
            return []

    def get_session_metrics(self) -> dict[str, Any]:
        """Get session metrics combining WebSocket and persistence data."""
        try:
            # Get persistence metrics
            persistence_metrics = self.persistence.get_session_metrics()

            # Add WebSocket-specific metrics
            websocket_metrics = {
                "active_websocket_sessions": len(self.sessions),
                "websocket_callbacks_registered": len(self.websocket_callbacks),
                "sessions_with_active_processes": sum(
                    1
                    for info in self.session_info.values()
                    if info.state not in [CLISessionState.TERMINATED, CLISessionState.ERROR]
                ),
            }

            # Combine metrics
            return {**persistence_metrics, **websocket_metrics}

        except Exception as e:
            return {"error": str(e)}

    def get_persistent_session(self, session_id: str) -> Session | None:
        """Get persistent session data from Redis."""
        return self.persistence.get_session(session_id)

    def get_session_history(
        self, session_id: str, limit: int | None = None, message_type: str | None = None
    ) -> list[Message]:
        """Get session history from Redis persistence."""
        return self.persistence.get_session_history(session_id, limit, message_type)

    def set_main_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the main event loop reference for thread-safe async operations."""
        self.main_loop = loop
        logger.info(f"CLI Session Manager main event loop set: {loop}")


# Global session manager instance
_cli_session_manager = None


def get_cli_session_manager() -> CLISessionManager:
    """Get the global CLI session manager instance."""
    global _cli_session_manager
    if _cli_session_manager is None:
        _cli_session_manager = CLISessionManager()
    return _cli_session_manager
