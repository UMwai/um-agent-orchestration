"""Legacy CLI session manager tests (skipped for simplified orchestrator)."""

import pytest


pytest.skip(
    "Legacy CLI session manager module is not available in the simplified orchestrator.",
    allow_module_level=True,
)


class TestCLISessionInfo:
    """Test CLISessionInfo dataclass functionality."""

    def test_session_info_creation(self):
        """Test CLISessionInfo creation with default values."""
        session_info = CLISessionInfo(
            session_id="test-session-123",
            cli_tool="claude",
            mode="interactive",
            state=CLISessionState.INITIALIZING,
        )

        assert session_info.session_id == "test-session-123"
        assert session_info.cli_tool == "claude"
        assert session_info.mode == "interactive"
        assert session_info.state == CLISessionState.INITIALIZING
        assert session_info.pid is None
        assert session_info.created_at > 0
        assert session_info.last_activity > 0
        assert session_info.command_history == []
        assert session_info.current_directory == os.getcwd()
        assert session_info.authentication_required is False
        assert session_info.auth_prompt is None

    def test_session_info_with_custom_values(self):
        """Test CLISessionInfo creation with custom values."""
        command_history = ["ls", "pwd", "echo hello"]
        custom_dir = "/tmp/custom"

        session_info = CLISessionInfo(
            session_id="custom-session",
            cli_tool="codex",
            mode="cli",
            state=CLISessionState.RUNNING,
            pid=12345,
            created_at=1000.0,
            last_activity=2000.0,
            command_history=command_history,
            current_directory=custom_dir,
            authentication_required=True,
            auth_prompt="Enter API key",
        )

        assert session_info.pid == 12345
        assert session_info.created_at == 1000.0
        assert session_info.last_activity == 2000.0
        assert session_info.command_history == command_history
        assert session_info.current_directory == custom_dir
        assert session_info.authentication_required is True
        assert session_info.auth_prompt == "Enter API key"


class TestCLIProcessManager:
    """Test CLIProcessManager functionality."""

    @pytest.fixture
    def session_info(self):
        """Create test session info."""
        return CLISessionInfo(
            session_id="process-test",
            cli_tool="claude",
            mode="interactive",
            state=CLISessionState.INITIALIZING,
        )

    @pytest.fixture
    def output_callback(self):
        """Create mock output callback."""
        return MagicMock()

    @pytest.fixture
    def process_manager(self, session_info, output_callback):
        """Create CLIProcessManager instance."""
        return CLIProcessManager(session_info, output_callback)

    def test_process_manager_initialization(
        self, process_manager, session_info, output_callback
    ):
        """Test process manager initialization."""
        assert process_manager.session_info == session_info
        assert process_manager.output_callback == output_callback
        assert process_manager.process is None
        assert process_manager.pty_master is None
        assert process_manager.pty_slave is None
        assert process_manager.output_thread is None
        assert process_manager.running is False

    @pytest.mark.asyncio
    async def test_start_process_success(self, process_manager):
        """Test successful process startup."""
        command = ["echo", "test"]
        env = {"TEST_VAR": "value"}

        with (
            patch("pty.openpty") as mock_openpty,
            patch("subprocess.Popen") as mock_popen,
            patch("os.close"),
            patch("threading.Thread") as mock_thread,
        ):
            # Mock PTY pair
            mock_openpty.return_value = (10, 11)  # master, slave

            # Mock process
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            # Mock thread
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            await process_manager.start_process(command, env)

            # Verify process setup
            assert process_manager.session_info.state == CLISessionState.RUNNING
            assert process_manager.session_info.pid == 12345
            assert process_manager.pty_master == 10
            assert process_manager.process == mock_process
            assert process_manager.running is True

            # Verify subprocess call
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            assert call_args[0][0] == command

            # Verify thread started
            mock_thread_instance.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_process_failure(self, process_manager):
        """Test process startup failure handling."""
        command = ["nonexistent-command"]

        with patch("pty.openpty") as mock_openpty, patch(
            "subprocess.Popen"
        ) as mock_popen:
            mock_openpty.return_value = (10, 11)
            mock_popen.side_effect = FileNotFoundError("Command not found")

            with pytest.raises(FileNotFoundError):
                await process_manager.start_process(command)

            assert process_manager.session_info.state == CLISessionState.ERROR

    @pytest.mark.asyncio
    async def test_send_input_success(self, process_manager):
        """Test sending input to CLI process."""
        # Set up process as running
        process_manager.pty_master = 10
        process_manager.running = True
        process_manager.session_info.state = CLISessionState.RUNNING

        with patch("os.write") as mock_write:
            await process_manager.send_input("test command")

            # Verify input was written to PTY
            mock_write.assert_called_once_with(10, b"test command\n")

            # Verify command added to history
            assert "test command" in process_manager.session_info.command_history

            # Verify state change
            assert process_manager.session_info.state == CLISessionState.PROCESSING

    @pytest.mark.asyncio
    async def test_send_input_authentication(self, process_manager):
        """Test sending authentication input."""
        # Set up process as waiting for auth
        process_manager.pty_master = 10
        process_manager.running = True
        process_manager.session_info.state = CLISessionState.WAITING_INPUT
        process_manager.session_info.authentication_required = True
        process_manager.session_info.auth_prompt = "Enter API key"

        with patch("os.write") as mock_write:
            await process_manager.send_input("sk-test-key")

            # Verify auth state cleared
            assert process_manager.session_info.authentication_required is False
            assert process_manager.session_info.auth_prompt is None

            # Auth input should not be added to command history
            assert "sk-test-key" not in process_manager.session_info.command_history

    @pytest.mark.asyncio
    async def test_send_input_not_running(self, process_manager):
        """Test sending input when process is not running."""
        process_manager.pty_master = None
        process_manager.running = False

        with pytest.raises(RuntimeError, match="CLI process not running"):
            await process_manager.send_input("test")

    @pytest.mark.asyncio
    async def test_terminate_process(self, process_manager):
        """Test process termination."""
        # Set up running process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.wait.return_value = 0

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        process_manager.process = mock_process
        process_manager.pty_master = 10
        process_manager.output_thread = mock_thread
        process_manager.running = True

        with (
            patch("os.killpg") as mock_killpg,
            patch("os.getpgid") as mock_getpgid,
            patch("os.close") as mock_close,
        ):
            mock_getpgid.return_value = 12345

            await process_manager.terminate()

            # Verify termination steps
            assert process_manager.running is False
            mock_killpg.assert_called_with(12345, 15)  # SIGTERM
            mock_process.wait.assert_called_with(timeout=5)
            mock_close.assert_called_with(10)
            mock_thread.join.assert_called_with(timeout=2)

            assert process_manager.session_info.state == CLISessionState.TERMINATED

    def test_authentication_pattern_detection(self, process_manager, output_callback):
        """Test CLI-specific authentication pattern detection."""

        # Test cases: (cli_tool, output, should_detect_auth, expected_prompt)
        test_cases = [
            # Claude patterns
            (
                "claude",
                "Please provide your Anthropic API key:",
                True,
                "Claude API key required",
            ),
            ("claude", "Authentication required", True, "Claude API key required"),
            ("claude", "Claude Code is ready", False, None),
            ("claude", "logged in successfully", False, None),
            # Codex patterns
            ("codex", "OpenAI API key required", True, "OpenAI API key required"),
            ("codex", "Please login to continue", True, "OpenAI API key required"),
            ("codex", "ready for commands", False, None),
            # Gemini patterns
            ("gemini", "Google API key needed", True, "Google API key required"),
            (
                "gemini",
                "Please authenticate with Google",
                True,
                "Google API key required",
            ),
            ("gemini", "Gemini ready to process requests", False, None),
            # Cursor patterns
            (
                "cursor",
                "Please sign in to Cursor",
                True,
                "Cursor authentication required",
            ),
            (
                "cursor",
                "Cursor account required",
                True,
                "Cursor authentication required",
            ),
            ("cursor", "Cursor agent ready", False, None),
            # Generic patterns
            ("unknown", "Password:", True, "Password:"),
            ("unknown", "Please enter credentials:", True, "Please enter credentials:"),
            ("unknown", "Ready for input$", False, None),
        ]

        for cli_tool, output_text, should_detect_auth, expected_prompt in test_cases:
            # Reset state
            process_manager.session_info.cli_tool = cli_tool
            process_manager.session_info.authentication_required = False
            process_manager.session_info.auth_prompt = None
            output_callback.reset_mock()

            # Simulate the authentication detection logic from _read_output
            output_lower = output_text.lower()

            if cli_tool == "claude":
                if any(
                    pattern in output_lower
                    for pattern in [
                        "api key",
                        "anthropic_api_key",
                        "authentication",
                        "login required",
                        "please authenticate",
                    ]
                ):
                    process_manager.session_info.state = CLISessionState.WAITING_INPUT
                    process_manager.session_info.authentication_required = True
                    process_manager.session_info.auth_prompt = "Claude API key required"
                elif (
                    "claude code is ready" in output_lower
                    or "logged in" in output_lower
                ):
                    process_manager.session_info.state = CLISessionState.RUNNING
                    process_manager.session_info.authentication_required = False

            elif cli_tool == "codex":
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
                    process_manager.session_info.state = CLISessionState.WAITING_INPUT
                    process_manager.session_info.authentication_required = True
                    process_manager.session_info.auth_prompt = "OpenAI API key required"
                elif (
                    "ready for commands" in output_lower or "logged in" in output_lower
                ):
                    process_manager.session_info.state = CLISessionState.RUNNING
                    process_manager.session_info.authentication_required = False

            elif cli_tool == "gemini":
                if any(
                    pattern in output_lower
                    for pattern in [
                        "api key",
                        "google_api_key",
                        "please authenticate",
                        "login required",
                        "credentials needed",
                    ]
                ):
                    process_manager.session_info.state = CLISessionState.WAITING_INPUT
                    process_manager.session_info.authentication_required = True
                    process_manager.session_info.auth_prompt = "Google API key required"
                elif "gemini ready" in output_lower or "authenticated" in output_lower:
                    process_manager.session_info.state = CLISessionState.RUNNING
                    process_manager.session_info.authentication_required = False

            elif cli_tool == "cursor":
                if any(
                    pattern in output_lower
                    for pattern in [
                        "login required",
                        "please sign in",
                        "authentication",
                        "cursor account",
                        "subscription required",
                    ]
                ):
                    process_manager.session_info.state = CLISessionState.WAITING_INPUT
                    process_manager.session_info.authentication_required = True
                    process_manager.session_info.auth_prompt = (
                        "Cursor authentication required"
                    )
                elif (
                    "cursor agent ready" in output_lower or "signed in" in output_lower
                ):
                    process_manager.session_info.state = CLISessionState.RUNNING
                    process_manager.session_info.authentication_required = False

            # Generic patterns (fallback)
            elif any(
                keyword in output_lower
                for keyword in [
                    "password:",
                    "login:",
                    "authenticate",
                    "api key",
                    "token:",
                    "please enter",
                    "credentials",
                    "authorization",
                ]
            ):
                process_manager.session_info.state = CLISessionState.WAITING_INPUT
                process_manager.session_info.authentication_required = True
                process_manager.session_info.auth_prompt = output_text.strip()

            elif (
                output_text.strip().endswith("$")
                or output_text.strip().endswith(">")
                or "Ready" in output_text
            ):
                process_manager.session_info.state = CLISessionState.RUNNING
                process_manager.session_info.authentication_required = False

            # Verify detection results
            assert (
                process_manager.session_info.authentication_required
                == should_detect_auth
            ), f"Auth detection failed for {cli_tool}: '{output_text}'"

            if should_detect_auth and expected_prompt:
                assert (
                    expected_prompt in (process_manager.session_info.auth_prompt or "")
                ), f"Auth prompt mismatch for {cli_tool}: expected '{expected_prompt}', got '{process_manager.session_info.auth_prompt}'"


class TestCLISessionManager:
    """Test CLISessionManager functionality."""

    @pytest.fixture
    def session_manager(self):
        """Create fresh session manager."""
        return CLISessionManager()

    @pytest.fixture
    def mock_persistence_manager(self):
        """Create mock persistence manager."""
        mock = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "persistent-session-id"
        mock.create_session.return_value = mock_session
        return mock

    def test_session_manager_initialization(self, session_manager):
        """Test session manager initialization."""
        assert len(session_manager.sessions) == 0
        assert len(session_manager.session_info) == 0
        assert len(session_manager.websocket_callbacks) == 0
        assert session_manager.persistence is not None

    def test_websocket_callback_registration(self, session_manager):
        """Test WebSocket callback registration and unregistration."""
        callback = MagicMock()
        session_id = "test-session"

        # Register callback
        session_manager.register_websocket_callback(session_id, callback)
        assert session_manager.websocket_callbacks[session_id] == callback

        # Unregister callback
        session_manager.unregister_websocket_callback(session_id)
        assert session_id not in session_manager.websocket_callbacks

    @pytest.mark.asyncio
    async def test_create_session_success(
        self, session_manager, mock_persistence_manager
    ):
        """Test successful session creation."""
        session_manager.persistence = mock_persistence_manager

        session_id = await session_manager.create_session(
            cli_tool="claude", mode="interactive", cwd="/tmp/test", user_id="test_user"
        )

        assert session_id == "persistent-session-id"
        assert session_id in session_manager.sessions
        assert session_id in session_manager.session_info

        # Verify persistence manager was called correctly
        mock_persistence_manager.create_session.assert_called_once_with(
            provider="claude",
            user_id="test_user",
            working_directory="/tmp/test",
            metadata={"mode": "interactive", "cli_tool": "claude"},
        )

        # Verify session info
        session_info = session_manager.session_info[session_id]
        assert session_info.session_id == session_id
        assert session_info.cli_tool == "claude"
        assert session_info.mode == "interactive"
        assert session_info.state == CLISessionState.INITIALIZING
        assert session_info.current_directory == "/tmp/test"

    @pytest.mark.asyncio
    async def test_create_session_default_values(
        self, session_manager, mock_persistence_manager
    ):
        """Test session creation with default values."""
        session_manager.persistence = mock_persistence_manager

        session_id = await session_manager.create_session(cli_tool="codex")

        session_info = session_manager.session_info[session_id]
        assert session_info.mode == "cli"  # default
        assert session_info.current_directory == os.getcwd()  # default

    def test_cli_command_building(self, session_manager):
        """Test CLI command building for different tools and modes."""

        test_cases = [
            # (cli_tool, mode, full_access, expected_command)
            (
                "claude",
                "interactive",
                True,
                ["claude", "--dangerously-skip-permissions"],
            ),
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
            (
                "gemini",
                "interactive",
                True,
                ["gemini", "--interactive", "--full-access"],
            ),
            ("gemini", "cli", False, ["gemini"]),
            (
                "cursor",
                "interactive",
                True,
                ["cursor-agent", "--full-access", "--auto-approve"],
            ),
            ("cursor", "cli", False, ["cursor-agent"]),
            ("unknown", "cli", False, ["unknown"]),  # fallback
        ]

        for cli_tool, mode, full_access, expected_command in test_cases:
            actual_command = session_manager._build_cli_command(
                cli_tool, mode, full_access
            )
            assert (
                actual_command == expected_command
            ), f"Command mismatch for {cli_tool}/{mode}/{full_access}: expected {expected_command}, got {actual_command}"

    def test_cli_environment_setup(self, session_manager):
        """Test CLI environment variable setup."""

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "claude-key",
                "OPENAI_API_KEY": "openai-key",
                "GOOGLE_API_KEY": "google-key",
            },
        ):
            # Test Claude environment
            env = session_manager._get_cli_environment("claude", full_access=True)
            assert env["ANTHROPIC_API_KEY"] == "claude-key"
            assert env["REPO_ROOT"] == os.getcwd()
            assert env["CLI_FULL_ACCESS"] == "1"

            # Test Codex environment
            env = session_manager._get_cli_environment("codex", full_access=False)
            assert env["OPENAI_API_KEY"] == "openai-key"
            assert env["REPO_ROOT"] == os.getcwd()
            assert "CLI_FULL_ACCESS" not in env

            # Test Gemini environment
            env = session_manager._get_cli_environment("gemini", full_access=True)
            assert env["GOOGLE_API_KEY"] == "google-key"
            assert env["CLI_FULL_ACCESS"] == "1"

    @pytest.mark.asyncio
    async def test_start_cli_process_success(
        self, session_manager, mock_persistence_manager
    ):
        """Test starting CLI process for session."""
        session_manager.persistence = mock_persistence_manager

        # Create session first
        session_id = await session_manager.create_session("claude", "cli")

        with patch.object(
            session_manager.sessions[session_id], "start_process"
        ) as mock_start:
            mock_start.return_value = None  # async function, no return

            result = await session_manager.start_cli_process(
                session_id, full_access=False
            )

            assert result is True
            mock_start.assert_called_once()

            # Verify command and env passed correctly
            call_args = mock_start.call_args
            command = call_args[0][0]
            env = call_args[0][1]

            assert command == ["claude"]
            assert "REPO_ROOT" in env

    @pytest.mark.asyncio
    async def test_start_cli_process_failure(
        self, session_manager, mock_persistence_manager
    ):
        """Test CLI process start failure."""
        session_manager.persistence = mock_persistence_manager

        session_id = await session_manager.create_session("claude", "cli")

        with patch.object(
            session_manager.sessions[session_id], "start_process"
        ) as mock_start:
            mock_start.side_effect = Exception("Start failed")

            result = await session_manager.start_cli_process(
                session_id, full_access=False
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_start_cli_process_nonexistent_session(self, session_manager):
        """Test starting process for non-existent session."""
        result = await session_manager.start_cli_process("nonexistent-session")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_input_to_session_success(
        self, session_manager, mock_persistence_manager
    ):
        """Test sending input to CLI session."""
        session_manager.persistence = mock_persistence_manager

        session_id = await session_manager.create_session("claude", "cli")

        with patch.object(
            session_manager.sessions[session_id], "send_input"
        ) as mock_send:
            mock_send.return_value = None  # async function

            result = await session_manager.send_input_to_session(
                session_id, "test command"
            )

            assert result is True
            mock_send.assert_called_once_with("test command")

            # Verify message stored in persistence
            mock_persistence_manager.add_message.assert_called_once()
            call_args = mock_persistence_manager.add_message.call_args
            assert call_args[0][0] == session_id  # session_id
            message = call_args[0][1]  # Message object
            assert message.content == "test command"
            assert message.type == "command"
            assert message.direction == "input"

    @pytest.mark.asyncio
    async def test_send_input_to_session_failure(
        self, session_manager, mock_persistence_manager
    ):
        """Test handling input send failure."""
        session_manager.persistence = mock_persistence_manager

        session_id = await session_manager.create_session("claude", "cli")

        with patch.object(
            session_manager.sessions[session_id], "send_input"
        ) as mock_send:
            mock_send.side_effect = Exception("Send failed")

            result = await session_manager.send_input_to_session(
                session_id, "test command"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_terminate_session_success(
        self, session_manager, mock_persistence_manager
    ):
        """Test successful session termination."""
        session_manager.persistence = mock_persistence_manager

        session_id = await session_manager.create_session("claude", "cli")

        # Add a WebSocket callback to verify cleanup
        callback = MagicMock()
        session_manager.register_websocket_callback(session_id, callback)

        with patch.object(
            session_manager.sessions[session_id], "terminate"
        ) as mock_terminate:
            mock_terminate.return_value = None  # async function

            result = await session_manager.terminate_session(
                session_id, "Test termination"
            )

            assert result is True

            # Verify cleanup
            mock_persistence_manager.terminate_session.assert_called_once_with(
                session_id, "Test termination"
            )
            mock_terminate.assert_called_once()
            assert session_id not in session_manager.sessions
            assert session_id not in session_manager.session_info
            assert session_id not in session_manager.websocket_callbacks

    @pytest.mark.asyncio
    async def test_terminate_session_nonexistent(self, session_manager):
        """Test terminating non-existent session."""
        result = await session_manager.terminate_session("nonexistent-session")
        assert result is False

    def test_get_session_info(self, session_manager, mock_persistence_manager):
        """Test getting session information."""
        session_manager.persistence = mock_persistence_manager

        # Create session
        session_id = asyncio.run(session_manager.create_session("claude", "cli"))

        # Get session info
        session_info = session_manager.get_session_info(session_id)
        assert session_info is not None
        assert session_info.session_id == session_id

        # Test non-existent session
        assert session_manager.get_session_info("nonexistent") is None

    def test_list_sessions(self, session_manager, mock_persistence_manager):
        """Test listing all sessions."""
        session_manager.persistence = mock_persistence_manager

        # Initially empty
        sessions = session_manager.list_sessions()
        assert len(sessions) == 0

        # Create some sessions
        session_ids = []
        for i in range(3):
            mock_persistence_manager.create_session.return_value.id = f"session-{i}"
            session_id = asyncio.run(session_manager.create_session(f"tool-{i}", "cli"))
            session_ids.append(session_id)

        sessions = session_manager.list_sessions()
        assert len(sessions) == 3

        # Verify all sessions present
        listed_ids = [s.session_id for s in sessions]
        for session_id in session_ids:
            assert session_id in listed_ids

    @pytest.mark.asyncio
    async def test_cleanup_inactive_sessions(
        self, session_manager, mock_persistence_manager
    ):
        """Test cleanup of inactive sessions."""
        session_manager.persistence = mock_persistence_manager

        # Create sessions with different activity times
        session_ids = []
        for i in range(3):
            mock_persistence_manager.create_session.return_value.id = f"session-{i}"
            session_id = await session_manager.create_session(f"tool-{i}", "cli")
            session_ids.append(session_id)

        # Set different last activity times
        current_time = time.time()
        session_manager.session_info[session_ids[0]].last_activity = (
            current_time - 1800
        )  # 30 min ago
        session_manager.session_info[session_ids[1]].last_activity = (
            current_time - 7200
        )  # 2 hours ago
        session_manager.session_info[session_ids[2]].last_activity = (
            current_time - 14400
        )  # 4 hours ago

        with patch.object(session_manager, "terminate_session") as mock_terminate:
            mock_terminate.return_value = True

            # Cleanup sessions older than 1 hour
            await session_manager.cleanup_inactive_sessions(max_age=3600)

            # Only the 2 oldest sessions should be terminated
            assert mock_terminate.call_count == 2

            # Verify which sessions were terminated
            terminated_sessions = [call[0][0] for call in mock_terminate.call_args_list]
            assert session_ids[1] in terminated_sessions
            assert session_ids[2] in terminated_sessions
            assert session_ids[0] not in terminated_sessions

        # Verify persistence cleanup was called
        mock_persistence_manager.cleanup_expired_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_recover_sessions(self, session_manager, mock_persistence_manager):
        """Test session recovery from persistence."""
        session_manager.persistence = mock_persistence_manager

        # Mock recovered persistent sessions
        mock_sessions = []
        for i in range(2):
            mock_session = MagicMock()
            mock_session.id = f"recovered-session-{i}"
            mock_session.provider = "claude"
            mock_session.working_directory = "/tmp"
            mock_session.metadata = {"mode": "cli", "cli_tool": "claude"}
            mock_sessions.append(mock_session)

        mock_persistence_manager.recover_sessions.return_value = mock_sessions

        recovered_ids = await session_manager.recover_sessions()

        assert len(recovered_ids) == 2
        assert "recovered-session-0" in recovered_ids
        assert "recovered-session-1" in recovered_ids

        # Verify sessions added to in-memory tracking
        for session_id in recovered_ids:
            assert session_id in session_manager.session_info
            session_info = session_manager.session_info[session_id]
            assert session_info.cli_tool == "claude"
            assert (
                session_info.state == CLISessionState.ERROR
            )  # Should be marked as error until recovery

    def test_get_session_metrics(self, session_manager, mock_persistence_manager):
        """Test session metrics collection."""
        session_manager.persistence = mock_persistence_manager

        # Mock persistence metrics
        mock_persistence_manager.get_session_metrics.return_value = {
            "total_persistent_sessions": 10,
            "active_persistent_sessions": 5,
        }

        # Create some WebSocket sessions
        for i in range(3):
            mock_persistence_manager.create_session.return_value.id = f"ws-session-{i}"
            asyncio.run(session_manager.create_session("claude", "cli"))

        # Add some WebSocket callbacks
        session_manager.register_websocket_callback("ws-session-0", MagicMock())
        session_manager.register_websocket_callback("ws-session-1", MagicMock())

        metrics = session_manager.get_session_metrics()

        # Verify combined metrics
        assert metrics["total_persistent_sessions"] == 10
        assert metrics["active_persistent_sessions"] == 5
        assert metrics["active_websocket_sessions"] == 3
        assert metrics["websocket_callbacks_registered"] == 2
        assert (
            metrics["sessions_with_active_processes"] == 3
        )  # All sessions are in INITIALIZING state

    def test_get_persistent_session(self, session_manager, mock_persistence_manager):
        """Test getting persistent session data."""
        session_manager.persistence = mock_persistence_manager

        mock_session = MagicMock()
        mock_persistence_manager.get_session.return_value = mock_session

        result = session_manager.get_persistent_session("test-session")

        assert result == mock_session
        mock_persistence_manager.get_session.assert_called_once_with("test-session")

    def test_get_session_history(self, session_manager, mock_persistence_manager):
        """Test getting session history."""
        session_manager.persistence = mock_persistence_manager

        mock_messages = [MagicMock(), MagicMock()]
        mock_persistence_manager.get_session_history.return_value = mock_messages

        result = session_manager.get_session_history(
            "test-session", limit=10, message_type="command"
        )

        assert result == mock_messages
        mock_persistence_manager.get_session_history.assert_called_once_with(
            "test-session", 10, "command"
        )


class TestSingletonManager:
    """Test singleton manager functionality."""

    def test_get_cli_session_manager_singleton(self):
        """Test singleton pattern for session manager."""
        manager1 = get_cli_session_manager()
        manager2 = get_cli_session_manager()

        assert manager1 is manager2
        assert isinstance(manager1, CLISessionManager)

    def test_singleton_state_preservation(self):
        """Test that singleton preserves state across calls."""
        manager1 = get_cli_session_manager()

        # Add some state
        manager1.websocket_callbacks["test"] = MagicMock()

        manager2 = get_cli_session_manager()
        assert "test" in manager2.websocket_callbacks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
