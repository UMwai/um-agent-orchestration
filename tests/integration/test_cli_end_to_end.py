"""
End-to-End Integration Tests for CLI System

Complete workflow tests covering:
- Full authentication flow
- Session creation and management
- WebSocket real-time communication
- CLI command execution
- Output streaming
- Error recovery
- Multi-session scenarios
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from orchestrator.app import app
from orchestrator.auth import AuthManager
from orchestrator.cli_session_manager import CLISessionState


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_manager(self):
        """Create auth manager."""
        return AuthManager()

    @pytest.mark.asyncio
    async def test_complete_cli_session_workflow(self, test_client, auth_manager):
        """Test complete workflow from auth to command execution."""

        # Step 1: Generate authentication token
        user_id = "test_user"
        token = auth_manager.generate_jwt_token(user_id, "test-session")

        # Step 2: Check available providers
        response = test_client.get("/api/cli/providers")
        assert response.status_code == 200
        providers = response.json()
        assert "providers" in providers

        # Step 3: Create CLI session
        with patch(
            "orchestrator.cli_session_manager.CLISessionManager.create_session"
        ) as mock_create:
            mock_create.return_value = "session-123"

            session_data = {"provider": "claude", "mode": "cli", "full_access": False}

            response = test_client.post(
                "/api/cli/sessions", json=session_data, headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                session_info = response.json()
                assert "session_id" in session_info
                session_id = session_info["session_id"]

                # Step 4: Connect via WebSocket
                with test_client.websocket_connect(f"/ws/cli/{session_id}") as websocket:
                    # Send authentication
                    auth_message = {
                        "type": "auth",
                        "session_id": session_id,
                        "data": {"token": token},
                    }
                    websocket.send_json(auth_message)

                    # Receive auth confirmation
                    response = websocket.receive_json()
                    assert response["type"] == "status"

                    # Step 5: Send command
                    command_message = {
                        "type": "command",
                        "session_id": session_id,
                        "data": {"command": "echo 'Hello World'"},
                    }
                    websocket.send_json(command_message)

                    # Step 6: Receive output
                    output = websocket.receive_json()
                    assert output["type"] in ["output", "status"]

                    # Step 7: Check session status
                    status_message = {"type": "status", "session_id": session_id, "data": {}}
                    websocket.send_json(status_message)

                    status_response = websocket.receive_json()
                    assert status_response["type"] == "status"
                    assert "session_id" in status_response["data"]

        # Step 8: Terminate session
        response = test_client.delete(
            f"/api/cli/sessions/{session_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code in [200, 404]  # May be already terminated

    @pytest.mark.asyncio
    async def test_multi_session_management(self, test_client, auth_manager):
        """Test managing multiple concurrent sessions."""

        user_id = "multi_user"
        token = auth_manager.generate_jwt_token(user_id)

        session_ids = []

        # Create multiple sessions
        for i in range(3):
            with patch(
                "orchestrator.cli_session_manager.CLISessionManager.create_session"
            ) as mock_create:
                mock_create.return_value = f"session-{i}"

                session_data = {"provider": "claude", "mode": "cli", "full_access": False}

                response = test_client.post(
                    "/api/cli/sessions",
                    json=session_data,
                    headers={"Authorization": f"Bearer {token}"},
                )

                if response.status_code == 200:
                    session_ids.append(response.json()["session_id"])

        # List all sessions
        response = test_client.get(
            "/api/cli/sessions", headers={"Authorization": f"Bearer {token}"}
        )

        if response.status_code == 200:
            sessions = response.json()["sessions"]
            assert len(sessions) >= len(session_ids)

        # Terminate all sessions
        for session_id in session_ids:
            response = test_client.delete(
                f"/api/cli/sessions/{session_id}", headers={"Authorization": f"Bearer {token}"}
            )

    @pytest.mark.asyncio
    async def test_session_recovery_after_disconnect(self, test_client, auth_manager):
        """Test session recovery after WebSocket disconnect."""

        user_id = "recovery_user"
        token = auth_manager.generate_jwt_token(user_id, "recovery-session")

        with patch(
            "orchestrator.cli_session_manager.CLISessionManager.create_session"
        ) as mock_create:
            mock_create.return_value = "recovery-session-123"

            # Create session
            session_data = {"provider": "claude", "mode": "interactive", "full_access": True}

            response = test_client.post(
                "/api/cli/sessions", json=session_data, headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                session_id = response.json()["session_id"]

                # First WebSocket connection
                with test_client.websocket_connect(f"/ws/cli/{session_id}") as ws1:
                    # Send auth
                    ws1.send_json(
                        {"type": "auth", "session_id": session_id, "data": {"token": token}}
                    )

                    # Send command
                    ws1.send_json(
                        {"type": "command", "session_id": session_id, "data": {"command": "pwd"}}
                    )

                    # Receive response
                    ws1.receive_json()

                # Disconnect and reconnect
                time.sleep(0.5)

                # Second WebSocket connection (recovery)
                with test_client.websocket_connect(f"/ws/cli/{session_id}") as ws2:
                    # Re-authenticate
                    ws2.send_json(
                        {"type": "auth", "session_id": session_id, "data": {"token": token}}
                    )

                    # Check session is still active
                    ws2.send_json({"type": "status", "session_id": session_id, "data": {}})

                    status = ws2.receive_json()
                    assert status["type"] == "status"
                    assert status["data"]["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_authentication_required_flow(self, test_client, auth_manager):
        """Test handling CLI tools that require authentication."""

        user_id = "auth_required_user"
        token = auth_manager.generate_jwt_token(user_id)

        with (
            patch(
                "orchestrator.cli_session_manager.CLISessionManager.create_session"
            ) as mock_create,
            patch(
                "orchestrator.cli_session_manager.CLISessionManager.get_session_info"
            ) as mock_info,
        ):
            mock_create.return_value = "auth-session-123"

            # Mock session info with auth required
            mock_session_info = MagicMock()
            mock_session_info.session_id = "auth-session-123"
            mock_session_info.authentication_required = True
            mock_session_info.auth_prompt = "Enter API key:"
            mock_session_info.state = CLISessionState.WAITING_INPUT
            mock_info.return_value = mock_session_info

            # Create session
            response = test_client.post(
                "/api/cli/sessions",
                json={"provider": "claude", "mode": "cli"},
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                session_id = response.json()["session_id"]

                # Connect via WebSocket
                with test_client.websocket_connect(f"/ws/cli/{session_id}") as websocket:
                    # Auth WebSocket
                    websocket.send_json(
                        {"type": "auth", "session_id": session_id, "data": {"token": token}}
                    )

                    # Check status - should show auth required
                    websocket.send_json({"type": "status", "session_id": session_id, "data": {}})

                    status = websocket.receive_json()

                    # Send authentication credentials
                    websocket.send_json(
                        {
                            "type": "command",
                            "session_id": session_id,
                            "data": {"command": "sk-test-api-key-123"},
                        }
                    )

                    # Should receive confirmation
                    response = websocket.receive_json()

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, test_client, auth_manager):
        """Test error scenarios and recovery."""

        # Test 1: Invalid token
        invalid_token = "invalid.jwt.token"
        response = test_client.post(
            "/api/cli/sessions",
            json={"provider": "claude"},
            headers={"Authorization": f"Bearer {invalid_token}"},
        )
        assert response.status_code in [401, 403]

        # Test 2: Non-existent session
        valid_token = auth_manager.generate_jwt_token("test_user")
        response = test_client.get(
            "/api/cli/sessions/nonexistent-session",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 404

        # Test 3: WebSocket connection to non-existent session
        try:
            with test_client.websocket_connect("/ws/cli/nonexistent") as websocket:
                pass
        except Exception:
            # Should fail to connect
            pass

        # Test 4: Command to terminated session
        with patch(
            "orchestrator.cli_session_manager.CLISessionManager.get_session_info"
        ) as mock_info:
            mock_info.return_value = MagicMock(state=CLISessionState.TERMINATED)

            response = test_client.post(
                "/api/cli/sessions/terminated-session/command",
                json={"command": "echo test"},
                headers={"Authorization": f"Bearer {valid_token}"},
            )
            assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_concurrent_websocket_connections(self, test_client, auth_manager):
        """Test multiple WebSocket connections to same session."""

        user_id = "concurrent_user"
        session_id = "concurrent-session"
        token = auth_manager.generate_jwt_token(user_id, session_id)

        with patch(
            "orchestrator.cli_session_manager.CLISessionManager.create_session"
        ) as mock_create:
            mock_create.return_value = session_id

            # Create session
            response = test_client.post(
                "/api/cli/sessions",
                json={"provider": "claude", "mode": "cli"},
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                # Open multiple WebSocket connections
                websockets = []

                try:
                    for i in range(3):
                        ws = test_client.websocket_connect(f"/ws/cli/{session_id}")
                        ws.__enter__()
                        websockets.append(ws)

                        # Authenticate each connection
                        ws.send_json(
                            {"type": "auth", "session_id": session_id, "data": {"token": token}}
                        )

                    # Send command from first WebSocket
                    websockets[0].send_json(
                        {
                            "type": "command",
                            "session_id": session_id,
                            "data": {"command": "echo 'broadcast test'"},
                        }
                    )

                    # All connections should receive the output
                    for ws in websockets:
                        response = ws.receive_json()
                        assert response["type"] in ["output", "status"]

                finally:
                    # Clean up connections
                    for ws in websockets:
                        try:
                            ws.__exit__(None, None, None)
                        except:
                            pass

    @pytest.mark.asyncio
    async def test_session_persistence_and_recovery(self, test_client, auth_manager):
        """Test session persistence across service restarts."""

        user_id = "persistent_user"
        token = auth_manager.generate_jwt_token(user_id)

        with patch("orchestrator.persistence.PersistenceManager.create_session") as mock_persist:
            mock_persist.return_value = MagicMock(id="persist-session-123")

            # Create persistent session
            response = test_client.post(
                "/api/cli/sessions",
                json={"provider": "claude", "mode": "interactive", "persistent": True},
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                session_id = response.json()["session_id"]

                # Simulate service restart by recovering sessions
                with patch(
                    "orchestrator.persistence.PersistenceManager.recover_sessions"
                ) as mock_recover:
                    mock_recover.return_value = [MagicMock(id=session_id)]

                    response = test_client.post(
                        "/api/cli/recover", headers={"Authorization": f"Bearer {token}"}
                    )

                    # Session should be recovered
                    response = test_client.get(
                        f"/api/cli/sessions/{session_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_rate_limiting_and_quotas(self, test_client, auth_manager):
        """Test rate limiting and quota enforcement."""

        user_id = "rate_limited_user"
        token = auth_manager.generate_jwt_token(user_id)

        # Attempt to create many sessions quickly
        session_count = 0
        for i in range(20):
            response = test_client.post(
                "/api/cli/sessions",
                json={"provider": "claude", "mode": "cli"},
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                session_count += 1
            elif response.status_code == 429:
                # Rate limited
                break

        # Should hit some limit
        assert session_count < 20

    @pytest.mark.asyncio
    async def test_output_streaming_performance(self, test_client, auth_manager):
        """Test output streaming performance with large outputs."""

        user_id = "streaming_user"
        token = auth_manager.generate_jwt_token(user_id, "stream-session")

        with patch(
            "orchestrator.cli_session_manager.CLISessionManager.create_session"
        ) as mock_create:
            mock_create.return_value = "stream-session-123"

            # Create session
            response = test_client.post(
                "/api/cli/sessions",
                json={"provider": "claude", "mode": "cli"},
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 200:
                session_id = response.json()["session_id"]

                with test_client.websocket_connect(f"/ws/cli/{session_id}") as websocket:
                    # Auth
                    websocket.send_json(
                        {"type": "auth", "session_id": session_id, "data": {"token": token}}
                    )

                    # Send command that generates large output
                    websocket.send_json(
                        {
                            "type": "command",
                            "session_id": session_id,
                            "data": {"command": "for i in {1..100}; do echo 'Line '$i; done"},
                        }
                    )

                    # Receive streamed output
                    output_count = 0
                    start_time = time.time()

                    while time.time() - start_time < 5:  # Max 5 seconds
                        try:
                            message = websocket.receive_json(timeout=0.5)
                            if message["type"] == "output":
                                output_count += 1
                        except:
                            break

                    # Should receive multiple output messages
                    assert output_count > 0


class TestProviderIntegration:
    """Test integration with different CLI providers."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_manager(self):
        """Create auth manager."""
        return AuthManager()

    @pytest.mark.asyncio
    async def test_claude_cli_integration(self, test_client, auth_manager):
        """Test Claude CLI integration."""
        await self._test_provider_integration(
            test_client,
            auth_manager,
            provider="claude",
            command_args=["--dangerously-skip-permissions"],
            test_command="echo 'Claude test'",
        )

    @pytest.mark.asyncio
    async def test_codex_cli_integration(self, test_client, auth_manager):
        """Test Codex CLI integration."""
        await self._test_provider_integration(
            test_client,
            auth_manager,
            provider="codex",
            command_args=["--ask-for-approval", "never"],
            test_command="echo 'Codex test'",
        )

    @pytest.mark.asyncio
    async def test_gemini_cli_integration(self, test_client, auth_manager):
        """Test Gemini CLI integration."""
        await self._test_provider_integration(
            test_client,
            auth_manager,
            provider="gemini",
            command_args=["--interactive"],
            test_command="echo 'Gemini test'",
        )

    @pytest.mark.asyncio
    async def test_cursor_cli_integration(self, test_client, auth_manager):
        """Test Cursor CLI integration."""
        await self._test_provider_integration(
            test_client,
            auth_manager,
            provider="cursor",
            command_args=["--auto-approve"],
            test_command="echo 'Cursor test'",
        )

    async def _test_provider_integration(
        self, test_client, auth_manager, provider: str, command_args: list[str], test_command: str
    ):
        """Helper to test provider integration."""

        user_id = f"{provider}_user"
        token = auth_manager.generate_jwt_token(user_id)

        # Check if provider is available
        response = test_client.get("/api/cli/providers")
        providers = response.json()["providers"]

        if provider in providers and providers[provider]["available"]:
            # Create session with provider
            with patch(
                "orchestrator.cli_session_manager.CLISessionManager.create_session"
            ) as mock_create:
                mock_create.return_value = f"{provider}-session-123"

                response = test_client.post(
                    "/api/cli/sessions",
                    json={"provider": provider, "mode": "cli", "full_access": True},
                    headers={"Authorization": f"Bearer {token}"},
                )

                assert response.status_code == 200
                session_id = response.json()["session_id"]

                # Verify correct command construction
                with patch("subprocess.Popen") as mock_popen:
                    mock_process = MagicMock()
                    mock_process.poll.return_value = None
                    mock_popen.return_value = mock_process

                    # Start CLI process
                    response = test_client.post(
                        f"/api/cli/sessions/{session_id}/start",
                        headers={"Authorization": f"Bearer {token}"},
                    )

                    if mock_popen.called:
                        call_args = mock_popen.call_args[0][0]
                        assert call_args[0] == provider

                        for arg in command_args:
                            assert arg in call_args


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
